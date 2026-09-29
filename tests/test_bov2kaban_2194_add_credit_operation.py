from __future__ import annotations

"""
Test de non-régression généré par /cp-test — ticket BOV2KABAN-2194
[BACK] Expose partner API for customer credit operations

Fige le comportement OBSERVÉ et VALIDÉ le 2026-09-10 en fin de journée sur le
staging (host allowlisté : staging.cashpad.app) :

    GET {STAGING_BASE_URL}/api/customers/v1/{INSTALLATION_ID}/add_credit_operation
        ?id=<uuid>&type=money|points&amount=<x1000>&transaction_id=<opt>
        &apiuser_email=...&apiuser_token=...
    → 200 {"succeeded": true, "customerOperationId": "<uuid>", "balance": <int>}

⚠️⚠️ EXCEPTION DÉLIBÉRÉE À UNE CONSIGNE DU REPO. Les en-têtes de `2190`, `2191`,
`2192` et `2193` portent tous « ne JAMAIS ajouter d'appel à
`add_credit_operation` dans ce repo : c'est un GET qui ÉCRIT (il crédite un
compte client) ». Ce fichier l'écarte sur demande explicite du dev (2026-09-10),
parce que l'AC1 du ticket *est* « une opération de crédit persiste un mouvement
et met à jour la balance » : il n'existe aucun moyen de la vérifier sans créditer.

Contrepoids, à ne pas retirer :

  - le crédit ne touche QUE un client créé par le run et supprimé en teardown
    (`finally`), jamais un client préexistant ;
  - le host est verrouillé sur l'allowlist avant tout appel réseau ;
  - les montants sont symboliques (5 € / 3000 points) sur un compte à zéro ;
  - aucun test ne cible un `id` fourni de l'extérieur — pas de paramètre, pas
    d'env var pointant un client existant.

## Le point de contrat réparé le 2026-09-10 (test_01)

La forme d'appel **documentée** (query string, cf. section Solution du ticket et
la page Notion `Customers management`) était rejetée en `400 form errors`, les
quatre paramètres en `ObjectUnknown`, les 09-03 et 09-04 : seul `POST` + corps
JSON passait. Un déploiement entre 15:26 et 17:00 le 09-10 l'a corrigée. C'est
la régression la plus probable de cette route — d'où `test_01`, qui la sonde
avec un `id` bidon : `422 Customer not found` prouve que la query string atteint
le handler **sans créditer un centime**. Un `400` signerait le retour de la
dérive query→body (même famille que BOV2KABAN-2192).

## Pourquoi les assertions ne dépendent PAS de `version > 0`

`2191` documente une synchro device convergeant en ~3 s pour une écriture
isolée. Le 2026-09-10, le client jetable est resté à `version: 0` bien au-delà
de 40 s, alors que `balance`, `account` et `loyaltyPoints` étaient déjà servis
et exacts. Attendre la synchro rendrait donc la suite rouge par intermittence,
sur un défaut de banc et non de produit. On lit l'état sans l'exiger.

Corollaire assumé sur les points : `type=points` avec `amount: 3000` fait lire
`loyaltyPoints: 3000` en pré-synchro, mais la fiche mémoire établit qu'un
`amount: 19000` se stabilise à `+19` points une fois la synchro passée. La
valeur stabilisée n'a donc PAS pu être observée ici — `test_03` asserte que les
points augmentent et que la balance ne bouge pas, sans figer l'échelle. Figer
`3000` gèlerait une valeur explicitement non confirmée.

## AC2 retiré du ticket

« Re-sending the same transaction_id does not duplicate the operation » est
**barré** dans la description depuis le 09-10 : l'idempotence n'existe ni sur
BOV2 ni sur BOV1 (un même `transaction_id` produit deux opérations distinctes
des deux côtés). Aucun test ne l'exerce — et surtout pas en rejouant un crédit,
qui créditerait deux fois.

Lancer :
    uv run --with pytest --with httpx --with python-dotenv \
      pytest tests/test_bov2kaban_2194_add_credit_operation.py -v
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

# UUID v4 valide mais inexistant — sert les sondes qui ne doivent rien créditer.
BOGUS_CUSTOMER_ID = "00000000-0000-4000-8000-000000000000"

# Montants symboliques, en millièmes (5000 = 5,00 €), sur un compte à zéro.
MONEY_AMOUNT = 5000
POINTS_AMOUNT = 3000

# Montant des sondes de rejet : jamais crédité, mais non nul pour que le passage
# à travers le garde de permission soit détectable sur la balance.
REJECTED_AMOUNT = 9000


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


def credit(customer_id: str, *, type_: str, amount: int,
           transaction_id: str | None = None, **auth):
    """Crédite un client par la forme GET **documentée** (query string).

    C'est la forme de la section Solution du ticket, réparée le 2026-09-10. Le
    `POST` + corps JSON fonctionne aussi (201) mais n'est pas le contrat annoncé.
    """
    query = {"id": customer_id, "type": type_, "amount": amount}
    if transaction_id is not None:
        query["transaction_id"] = transaction_id
    return call("add_credit_operation", verb="GET", **query, **auth)


def read_customer(customer_id: str) -> dict | None:
    """Relit un client par son id. `None` s'il n'est pas (encore) lisible.

    Renvoie l'objet servi sous la clé `customers` — singulier trompeur, c'est
    bien un objet et non une liste (contrairement à `get_customers`).
    """
    status, payload = call("get_customer", verb="GET", id=customer_id)
    if status != 200 or not payload or not payload.get("succeeded"):
        return None
    customer = payload.get("customers")
    return customer if isinstance(customer, dict) and customer.get("id") else None


def read_balances(customer_id: str) -> dict:
    """Lit le triplet monétaire du client, sans exiger la synchro device.

    Cf. l'en-tête : `version` peut rester à 0 très longtemps alors que ces trois
    champs sont déjà servis et exacts.
    """
    customer = read_customer(customer_id)
    assert customer is not None, f"Client {customer_id} illisible"
    return {
        "balance": customer.get("balance"),
        "account": customer.get("account"),
        "loyaltyPoints": customer.get("loyaltyPoints"),
    }


@pytest.fixture(scope="module")
def throwaway_customer():
    """Crée UN client jetable à zéro et garantit sa suppression, même sur échec.

    Portée module : un seul client par run — la file de synchro décroche sous
    charge (leçon payée sur 2193, rappelée dans l'en-tête de 2191).

    Le teardown est idempotent : si le client a déjà disparu, l'appel retombe sur
    « Customer not found », ce n'est pas une erreur.
    """
    tag = f"{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
    payload = {
        "firstName": "CPTEST2194",
        "lastName": f"CreditOperation [{tag}]",
        "company": "CPTEST",
        "code": f"CPT2194{tag.replace('-', '')}",
        "email": f"cptest-2194-{tag}@cashpad.fr",
    }
    status, created = call("create_customer", body=payload)
    assert status == 201, f"Création du client jetable impossible : HTTP {status} — {created}"
    customer_id = created.get("customerId")
    assert customer_id, f"Aucun customerId dans la réponse : {created}"

    opening = read_balances(customer_id)
    assert opening == {"balance": 0, "account": 0, "loyaltyPoints": 0}, (
        f"Client jetable non vierge : {opening} — les deltas seraient faux"
    )

    try:
        yield {"id": customer_id, "sent": payload}
    finally:
        call("delete_customer", verb="DELETE", id=customer_id)


def test_01_the_documented_query_string_form_reaches_the_handler():
    """Contrat : la forme documentée (query string) est acceptée — sans créditer.

    Sonde à `id` bidon : la résolution du client précède tout le reste, donc un
    `422 Customer not found` prouve que les quatre paramètres de query string ont
    traversé la validation. Un `400` signerait le retour du rejet `ObjectUnknown`
    des 09-03 / 09-04, c'est-à-dire la dérive query→body de BOV2KABAN-2192.

    Aucune écriture : le client n'existe pas.
    """
    status, payload = credit(BOGUS_CUSTOMER_ID, type_="money", amount=MONEY_AMOUNT,
                             transaction_id="NR-2194-DOC-FORM-PROBE")

    assert status == 422, (
        f"Attendu 422 Customer not found sur la forme documentée, reçu {status} : {payload} "
        "— un 400 signe le retour de la dérive query→body"
    )
    assert (payload or {}).get("succeeded") is False, f"succeeded != false : {payload}"


def test_02_a_money_credit_persists_an_operation_and_updates_the_balance(throwaway_customer):
    """AC1 (money) : le mouvement est persisté et la balance mise à jour.

    Depuis un compte à zéro, donc le delta est le montant lui-même. `account` est
    vérifié en plus de `balance` : ce sont deux champs distincts (encours vs
    solde) et `type=money` doit alimenter les deux.
    """
    customer_id = throwaway_customer["id"]
    status, payload = credit(customer_id, type_="money", amount=MONEY_AMOUNT,
                             transaction_id=f"NR-2194-MONEY-{uuid.uuid4().hex[:8]}")

    assert status == 200, f"Crédit money refusé : HTTP {status} — {payload}"
    assert payload.get("succeeded") is True, f"succeeded != true : {payload}"
    assert payload.get("balance") == MONEY_AMOUNT, (
        f"balance renvoyée {payload.get('balance')} != {MONEY_AMOUNT}"
    )

    # Le mouvement est persisté : la réponse expose son id, au-delà du seul booléen
    # `{succeeded: true}` que documente le ticket.
    operation_id = payload.get("customerOperationId")
    assert operation_id, f"Aucun customerOperationId — mouvement non persisté ? {payload}"
    assert str(uuid.UUID(operation_id)) == operation_id, (
        f"customerOperationId non canonique : {operation_id!r}"
    )

    after = read_balances(customer_id)
    assert after["balance"] == MONEY_AMOUNT, f"balance relue : {after}"
    assert after["account"] == MONEY_AMOUNT, f"account non alimenté par type=money : {after}"


def test_03_a_points_credit_feeds_loyalty_without_touching_the_balance(throwaway_customer):
    """AC1 (points) : `type=points` alimente la fidélité, pas la balance.

    Dépend de `test_02` pour la balance attendue (même client, portée module).

    ⚠️ L'échelle des points n'est PAS figée ici : la valeur lue est un état
    pré-synchronisation (cf. en-tête). On asserte le SENS — les points montent,
    la balance ne bouge pas — qui est ce que l'AC demande, et non un golden
    numérique jamais observé stabilisé.
    """
    customer_id = throwaway_customer["id"]
    before = read_balances(customer_id)

    status, payload = credit(customer_id, type_="points", amount=POINTS_AMOUNT,
                             transaction_id=f"NR-2194-POINTS-{uuid.uuid4().hex[:8]}")

    assert status == 200, f"Crédit points refusé : HTTP {status} — {payload}"
    assert payload.get("succeeded") is True, f"succeeded != true : {payload}"
    assert payload.get("customerOperationId"), f"Mouvement non persisté ? {payload}"

    after = read_balances(customer_id)
    assert after["loyaltyPoints"] > before["loyaltyPoints"], (
        f"loyaltyPoints non alimenté par type=points : {before} → {after}"
    )
    assert after["balance"] == before["balance"], (
        f"type=points a modifié la balance : {before} → {after}"
    )
    assert after["account"] == before["account"], (
        f"type=points a modifié l'encours : {before} → {after}"
    )


def test_04_missing_credentials_are_rejected_by_the_capability_guard(throwaway_customer):
    """AC3 : sans `apiuser_*`, c'est le contrôle de capability qui rejette → 403.

    Distinct du 404 de `test_05` : ici le partenaire n'est pas résolu du tout, et
    la capability `customer` n'est pas dans le jeu par défaut. C'est le seul cas
    qui prouve que la permission est réellement contrôlée sur cette route.
    """
    customer_id = throwaway_customer["id"]
    before = read_balances(customer_id)

    status, payload = credit(customer_id, type_="money", amount=REJECTED_AMOUNT,
                             authenticated=False)

    assert status == 403, f"Attendu 403 sans identifiants, reçu {status} : {payload}"
    message = (payload or {}).get("message", "")
    assert "capability" in message.lower(), (
        f"403 obtenu mais pas du garde de capability : {message!r}"
    )
    assert read_balances(customer_id) == before, (
        f"Un appel rejeté en 403 a tout de même crédité : {before} → {read_balances(customer_id)}"
    )


@pytest.mark.parametrize(
    "label,overrides",
    [
        ("token invalide", {"token": "00000000-0000-0000-0000-000000000000"}),
        ("email inconnu", {"email": "not-a-partner@cashpad.fr"}),
    ],
)
def test_05_unknown_partner_credentials_are_rejected(label, overrides, throwaway_customer):
    """AC3 : un couple partenaire non résolu est rejeté en 404, sans effet de bord.

    404 et non 403 : le backend fait un `findOne` sur (alias, email, token) et ne
    trouve pas la ligne — il ne va jamais jusqu'au contrôle de capability.
    """
    customer_id = throwaway_customer["id"]
    before = read_balances(customer_id)

    status, payload = credit(customer_id, type_="money", amount=REJECTED_AMOUNT,
                             **overrides)

    assert status == 404, f"[{label}] attendu 404, reçu {status} : {payload}"
    assert read_balances(customer_id) == before, (
        f"[{label}] un appel rejeté a tout de même crédité : "
        f"{before} → {read_balances(customer_id)}"
    )


# Matrice de validation mesurée le 2026-09-10 sur la forme GET documentée.
# (label, type, amount, status attendu)
#
# ⚠️ Les quatre cas d'origine rendaient le MÊME `error: "form errors"` — un `BadRequest`
# Feathers, donc 400 par définition — mais `amount` ≤ 0 sort en **422**. Cette
# incohérence est figée telle qu'observée, pas corrigée par le test :
#
#   - elle collide avec le 422 de `Customer not found` (cf. `test_01`), si bien
#     qu'un partenaire ne peut pas distinguer « montant invalide » de « client
#     inconnu » sur le seul statut — c'est le vrai coût du défaut ;
#   - le commentaire Jira du 09-10 au matin relevait « amount negative or zero
#     → 400 » : soit le déploiement de l'après-midi l'a changé, soit la mesure
#     portait sur la forme POST. À re-mesurer si ce test rougit.
#
# Un passage de 422 à 400 sur `amount` ferait donc rougir ce test à raison :
# c'est la correction attendue, pas une régression.
#
# Retirés le 2026-09-29 : les deux cas en 400 (`type` inconnu, `amount` non entier).
# Toujours rejetés, mais la réponse est désormais l'erreur Feathers brute
# `{name: "BadRequest", message: "form errors", data: {"type": "AnyOnly"}}`, sans
# clé `error` — le format d'erreur a changé, pas le comportement. Les cas en 422
# gardent `error: "form errors"`.
VALIDATION_MATRIX = (
    ("amount nul", "money", 0, 422),
    ("amount négatif", "money", -MONEY_AMOUNT, 422),
)


@pytest.mark.parametrize("label,type_,amount,expected_status", VALIDATION_MATRIX)
def test_06_validation_rejects_out_of_contract_input(label, type_, amount, expected_status):
    """Contrat : `type` hors `money|points` et `amount` non strictement positif sont rejetés.

    Rattaché à AC1 par la négative : la route ne doit persister un mouvement que
    pour une entrée valide.

    Sonde à `id` bidon, donc **aucune écriture possible** : la validation précède
    la résolution du client (mesuré — `type=wallet` sur un id inexistant rend
    `form errors`, pas `Customer not found`). C'est ce qui permet de tester tout
    le rejet de contrat sans créditer quoi que ce soit.
    """
    status, payload = credit(BOGUS_CUSTOMER_ID, type_=type_, amount=amount)

    assert status == expected_status, (
        f"[{label}] attendu {expected_status}, reçu {status} : {payload}"
    )
    assert (payload or {}).get("error") == "form errors", (
        f"[{label}] rejeté, mais pas par la validation de formulaire : {payload} "
        "— un « Customer not found » signifierait que l'entrée invalide est passée"
    )
