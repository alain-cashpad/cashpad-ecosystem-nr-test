from __future__ import annotations

"""
Test de non-régression généré par /cp-test — ticket BOV2KABAN-2191
[BACK] Expose partner API to create a customer

Fige le comportement OBSERVÉ et VALIDÉ le 2026-09-09 sur le staging
(host allowlisté : staging.cashpad.app) :

    POST {STAGING_BASE_URL}/api/customers/v1/{INSTALLATION_ID}/create_customer
        ?apiuser_email=...&apiuser_token=...
    → 201 {"succeeded": true, "customerId": "<uuid>",
           "message": "Created, will be synchronized soon"}

⚠️ FICHIER ÉCRIVAIN. Vérifier qu'une création crée exige de créer : chaque run
crée UN client `CPTEST2191` puis le supprime en teardown. Aucun client
préexistant n'est jamais touché. (Le fichier 2193 se présente comme le seul
fichier destructif du repo — ce n'est plus exact depuis celui-ci.)

**Un seul client par run, délibérément** — leçon payée sur 2193 : chaque écriture
est synchronisée en différé vers le device et la file décroche sous charge. Une
création isolée converge en ~3 s ; plusieurs cycles enchaînés laissent la dernière
bloquée à `version: 0` au-delà de 60 s. Multiplier les fixtures rendrait la suite
rouge par intermittence, sur un défaut de banc et non de produit.

## Lecture de contrôle : `get_customer`, pas `get_customers`

La relecture champ à champ passe par `get_customer?id=<uuid>`, qui renvoie l'objet
sous la clé **`customers`** (singulier trompeur). Ce choix n'est pas cosmétique :
`country` est absent de la projection BO (`/p/customers/api/1/...`) et — au
2026-09-09 — c'est `get_customer` qui prouve qu'il est bien **persisté**. Se fier
à la seule projection BO ferait conclure à tort à un champ perdu.

`get_customer` n'est ni dans la KB ni dans la skill `bov2-partners-api` (qui donne
la capability `customer` pour un stub) : sa joignabilité en GET est un fait mesuré
le 2026-09-09, pas une promesse de doc. Il accepte `id` ou `code` ; `customerId`
et `email` sont refusés en 400 `form errors`.

## AC3 : trois rejets distincts, à ne pas confondre

Mesuré le 2026-09-09 — le code dépend de *ce qui manque* :

    aucun apiuser_*        → 403 Forbidden, "The capability \"customer\" is not
                             supported. Supported capabilities are: payment, stock, menu."
    token invalide         → 404 NotFound (le findOne (alias,email,token) échoue)
    email inconnu          → 404 NotFound

Le 403 est le **garde de capability**, le 404 la **résolution du partenaire**. Un
test qui n'exercerait que le 404 ne dirait rien du contrôle de permission — d'où
les trois cas. Le quatrième (partenaire réellement installé mais sans la
capability) reste optionnel : cf. `NOCAP_APIUSER_*`, convention déjà en place sur
`test_bov2kaban_2190`.

Ne JAMAIS ajouter d'appel à `add_credit_operation` dans ce repo : c'est un GET qui
ÉCRIT (il crédite un compte client).

Lancer :
    uv run --with pytest --with httpx --with python-dotenv \
      pytest tests/test_bov2kaban_2191_create_customer.py -v
"""

import os
import time
import uuid

import httpx
import pytest
from dotenv import load_dotenv

load_dotenv()


from _target import partner_env, writes_guard

# Module en écriture : skippé hors staging sans NR_ALLOW_WRITES=1.
pytestmark = writes_guard()

# Convergence de la synchro device observée à ~3 s pour une écriture isolée.
SYNC_POLL_ATTEMPTS = 16
SYNC_POLL_DELAY_S = 2.5

# Les dix champs du corps documenté par la section Solution du ticket.
# Tous relus à l'identique après synchro le 2026-09-09.
DOCUMENTED_FIELDS = (
    "firstName", "lastName", "company", "street", "zipCode",
    "city", "country", "code", "email", "phone",
)


def get_env() -> dict:
    """Cible, alias et couple partenaire — cf. `_target.py` (NR_TARGET)."""
    env = partner_env()
    return env


def call(action: str, *, verb="POST", body=None, authenticated=True,
         email=None, token=None, **query):
    """Appelle une action customers de la Partner API. Renvoie (status_code, payload)."""
    env = get_env()
    url = f"{env['base_url'].rstrip('/')}/api/customers/v1/{env['installation_id']}/{action}"
    params = dict(query)
    if authenticated:
        params["apiuser_email"] = env["apiuser_email"] if email is None else email
        params["apiuser_token"] = env["apiuser_token"] if token is None else token

    response = httpx.request(verb, url, params=params, json=body, timeout=60)
    try:
        return response.status_code, response.json()
    except ValueError:
        return response.status_code, None


def fixture_payload() -> dict:
    """Corps de création, marqué et unique — traçable si un teardown échoue."""
    tag = f"{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
    return {
        "firstName": "CPTEST2191",
        "lastName": f"CreateRoute [{tag}]",
        "company": "CPTEST",
        "street": "1 rue de la Verification",
        "zipCode": "75002",
        "city": "Paris",
        "country": "FR",
        "code": f"CPT2191{tag.replace('-', '')}",
        "email": f"cptest-2191-{tag}@cashpad.fr",
        "phone": "0102030405",
    }


def read_customer(customer_id: str) -> dict | None:
    """Relit un client par son id. `None` s'il n'est pas (encore) lisible.

    Renvoie l'objet servi sous la clé `customers` — singulier trompeur, c'est bien
    un objet et non une liste (contrairement à `get_customers`).
    """
    status, payload = call("get_customer", verb="GET", id=customer_id)
    if status != 200 or not payload or not payload.get("succeeded"):
        return None
    customer = payload.get("customers")
    return customer if isinstance(customer, dict) and customer.get("id") else None


def wait_until_synced(customer_id: str) -> dict:
    """Attend la fin de la synchro device, pas la simple présence.

    Un client créé par l'API est lisible AVANT sa synchro, avec `version: 0` et un
    état transitoire. Se contenter de la présence produit des lectures non
    déterministes.
    """
    last = "jamais lu"
    for _ in range(SYNC_POLL_ATTEMPTS):
        customer = read_customer(customer_id)
        if customer is not None and customer.get("version", 0) > 0:
            return customer
        last = "illisible" if customer is None else f"version={customer.get('version')}"
        time.sleep(SYNC_POLL_DELAY_S)
    raise AssertionError(
        f"Synchro non convergée après {SYNC_POLL_ATTEMPTS * SYNC_POLL_DELAY_S:.0f} s : "
        f"client {customer_id} — dernier état lu : {last}"
    )


@pytest.fixture(scope="module")
def created_customer():
    """Crée UN client et garantit sa suppression, même en cas d'échec d'un step.

    Portée module : un seul client par run (cf. l'en-tête sur la file de synchro).
    Le teardown est idempotent — si le client a déjà disparu, l'appel retombe sur
    « Customer not found », ce n'est pas une erreur.
    """
    sent = fixture_payload()
    status, payload = call("create_customer", body=sent)
    assert status == 201, f"Création impossible : HTTP {status} — {payload}"
    assert payload.get("succeeded") is True, f"succeeded != true : {payload}"
    customer_id = payload.get("customerId")
    assert customer_id, f"Aucun customerId dans la réponse : {payload}"

    try:
        yield {"id": customer_id, "sent": sent, "response": payload, "status": status}
    finally:
        call("delete_customer", verb="DELETE", id=customer_id)


def test_01_creation_returns_201_and_the_internal_customer_id(created_customer):
    """AC2 : la réponse renvoie l'id interne du client.

    Le `customerId` doit être un vrai UUID : une chaîne quelconque satisferait
    « un id est renvoyé » sans rien prouver. Sa qualité d'id INTERNE est établie
    par `test_02`, qui relit le client avec.
    """
    assert created_customer["status"] == 201
    assert created_customer["response"]["succeeded"] is True

    customer_id = created_customer["id"]
    parsed = uuid.UUID(customer_id)  # lève si ce n'est pas un UUID
    assert str(parsed) == customer_id, f"customerId non canonique : {customer_id!r}"


def test_02_every_documented_field_persists_on_the_target_site(created_customer):
    """AC1 : la création persiste le client sur le site, avec tous les champs documentés.

    `name` est vérifié en plus des dix champs du corps : il n'est pas envoyé mais
    doit refléter `lastName`. C'est là qu'était passée la régression du
    2026-09-03 (`lastName` et `name` silencieusement perdus), corrigée depuis.
    """
    stored = wait_until_synced(created_customer["id"])
    sent = created_customer["sent"]

    diffs = [
        (field, sent[field], stored.get(field))
        for field in DOCUMENTED_FIELDS
        if stored.get(field) != sent[field]
    ]
    assert not diffs, f"Champ(s) non persisté(s) à l'identique : {diffs}"

    assert stored.get("name") == sent["lastName"], (
        f"`name` = {stored.get('name')!r} ne reflète pas `lastName` = {sent['lastName']!r} "
        "— régression du drop lastName/name (2026-09-03)"
    )
    assert stored.get("deleted") is False, "Client créé déjà marqué supprimé"


def test_03_missing_credentials_are_rejected_by_the_capability_guard():
    """AC3 : sans `apiuser_*`, c'est le contrôle de capability qui rejette → 403.

    Distinct du 404 de `test_04` : ici le partenaire n'est pas résolu du tout, et
    la capability `customer` n'est pas dans le jeu par défaut. C'est le seul cas
    qui prouve que la permission est réellement contrôlée sur cette route.
    """
    probe = fixture_payload()
    status, payload = call("create_customer", body=probe, authenticated=False)

    assert status == 403, f"Attendu 403 sans identifiants, reçu {status} : {payload}"
    message = (payload or {}).get("message", "")
    assert "capability" in message.lower(), (
        f"403 obtenu mais pas du garde de capability : {message!r}"
    )
    assert read_customer_by_code(probe["code"]) is None, (
        "Un appel rejeté en 403 a tout de même créé un client"
    )


@pytest.mark.parametrize(
    "label,overrides",
    [
        ("token invalide", {"token": "00000000-0000-0000-0000-000000000000"}),
        ("email inconnu", {"email": "not-a-partner@cashpad.fr"}),
    ],
)
def test_04_unknown_partner_credentials_are_rejected(label, overrides):
    """AC3 : un couple partenaire non résolu est rejeté en 404, sans effet de bord.

    404 et non 403 : le backend fait un `findOne` sur (alias, email, token) et
    ne trouve pas la ligne — il ne va jamais jusqu'au contrôle de capability.
    """
    probe = fixture_payload()
    status, payload = call("create_customer", body=probe, **overrides)

    assert status == 404, f"[{label}] attendu 404, reçu {status} : {payload}"
    assert read_customer_by_code(probe["code"]) is None, (
        f"[{label}] un appel rejeté a tout de même créé un client"
    )


def test_05_installed_partner_without_the_capability_is_rejected():
    """AC3, variante : partenaire installé sur le site mais SANS la capability → 403.

    Optionnel — demande un second couple partenaire, que tout le monde n'a pas.
    Même convention de nommage que `test_bov2kaban_2190`.
    """
    email = os.getenv("NOCAP_APIUSER_EMAIL")
    token = os.getenv("NOCAP_APIUSER_TOKEN")
    if not (email and token):
        pytest.skip("NOCAP_APIUSER_EMAIL / NOCAP_APIUSER_TOKEN absents de .env")

    probe = fixture_payload()
    status, payload = call("create_customer", body=probe, email=email, token=token)

    assert status == 403, f"Attendu 403 sur capability absente, reçu {status} : {payload}"
    assert read_customer_by_code(probe["code"]) is None, (
        "Un appel rejeté en 403 a tout de même créé un client"
    )


def read_customer_by_code(code: str) -> dict | None:
    """Relit un client par son `code`.

    Sert de contrôle d'effet de bord sur les appels rejetés : chaque sonde porte un
    `code` unique, donc une lecture non vide signifierait qu'un rejet a quand même
    écrit. `get_customer` accepte `id` ou `code` — pas `email`, qui part en 400.
    """
    status, payload = call("get_customer", verb="GET", code=code)
    if status != 200 or not payload or not payload.get("succeeded"):
        return None
    customer = payload.get("customers")
    return customer if isinstance(customer, dict) and customer.get("id") else None
