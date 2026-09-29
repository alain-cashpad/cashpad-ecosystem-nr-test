from __future__ import annotations

"""
Test de non-régression généré par /cp-test — ticket BOV2KABAN-2193
[BACK] Expose partner API to delete a customer

Fige le comportement OBSERVÉ et VALIDÉ le 2026-09-04 sur le staging
(host allowlisté : staging.cashpad.app) :

    DELETE {STAGING_BASE_URL}/api/customers/v1/{INSTALLATION_ID}/delete_customer
        ?apiuser_email=...&apiuser_token=...&id=<uuid>

⚠️ L'ENDPOINT N'EST PAS CELUI DU TICKET. La section Solution de 2193 (et la doc
partenaire, et l'entité KB `features/partner-api-customers`) annoncent
`DELETE .../update_customer`. C'est une erreur de doc, établie par la matrice
des verbes relevée sur BOV1 preprod le 2026-09-04 :

    verbe      BOV1 delete_customer             BOV1 update_customer
    GET        "Please use DELETE HTTP method"   "Unknown customer"
    POST       "Please use DELETE HTTP method"   "Unknown customer"
    PUT        "Please use DELETE HTTP method"   "Unknown customer"
    PATCH      "Please use DELETE HTTP method"   "Unknown customer"
    DELETE     "Customer not found"              "Unknown customer"

`delete_customer` est l'action de suppression et BOV1 impose DELETE dessus.
`update_customer` n'a aucun garde-verbe : les cinq verbes tombent sur le handler
d'update. Donc `DELETE .../update_customer` n'a JAMAIS supprimé, ni sur BOV1 ni
sur BOV2 — c'est un update à corps vide. Il écrasait les champs perso (ce qui
ressemblait à une anonymisation) ; depuis que `update_customer` est un PATCH
(BOV2KABAN-2280), il ne touche plus rien — l'assertion « champs écrasés » a été
retirée le 2026-09-29. L'étape 2 du cycle de vie garde l'essentiel : cette route
ne supprime pas.

⚠️ SEUL FICHIER DESTRUCTIF DU REPO. Vérifier qu'une suppression supprime exige
un client réel : chaque run crée UN `CPTEST2193` puis le supprime. Coût par
exécution = un client soft-deleted de plus sur l'installation ciblée. Aucun
client préexistant n'est jamais touché.

**Pourquoi un seul test couvre tout le cycle** — chaque écriture est
synchronisée en différé vers le device, et la file décroche sous charge :
mesuré le 2026-09-04, une création isolée se synchronise en ~3 s, mais trois
cycles create+delete enchaînés laissent la 3ᵉ création bloquée à `version: 0`
au-delà de 60 s. Trois fixtures indépendantes rendaient donc la suite rouge par
intermittence, sur un défaut de banc et non de produit. Un seul client par run
supprime la cause. La granularité perdue est compensée par des messages
d'assertion qui nomment l'AC concernée.

Le code HTTP de succès dépend du VERBE, pas de l'action (mapping Feathers) :
`DELETE .../delete_customer` → 200, `POST .../delete_customer` → 201. Les deux
suppriment.

Ne JAMAIS ajouter d'appel à `add_credit_operation` dans ce repo : c'est un GET
qui ÉCRIT (il crédite un compte client). Sur cette surface le verbe HTTP ne
protège rien — cf. le dernier test.
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

UNKNOWN_CUSTOMER_ID = "00000000-0000-4000-8000-000000000000"

# Convergence de la synchro device observée à ~3 s pour une écriture isolée.
# Budget large pour absorber une file déjà chargée par une autre activité sur
# l'installation, sans revenir aux minutes qu'exigeaient trois fixtures.
SYNC_POLL_ATTEMPTS = 16
SYNC_POLL_DELAY_S = 2.5

# Champs envoyés à la création, tous conservés après synchro.
# `externalId` est traité à part : cf. l'étape 1 du cycle de vie.
FIXTURE_FIELDS = {
    "firstName": "CPTEST2193",
    "lastName": "DeleteRoute",
    "company": "CPTEST",
    "street": "1 rue du Test",
    "zipCode": "69001",
    "city": "Lyon",
    "country": "FR",
    "code": "CPT2193",
    "phone": "0400000000",
}


def get_env() -> dict:
    """Cible, alias et couple partenaire — cf. `_target.py` (NR_TARGET)."""
    env = partner_env()
    return env


def call(action: str, *, verb="POST", body=None, authenticated=True, email=None, token=None, **query):
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


def read_customer(customer_id: str):
    """Cherche un client dans get_customers. Renvoie son dict, ou None s'il n'y est pas.

    `get_customers` filtre les clients soft-deleted (BOV2KABAN-2190) : une
    absence signifie donc soit "jamais créé / pas encore synchronisé", soit
    "supprimé". L'ordre des étapes du cycle lève l'ambiguïté.
    """
    status, payload = call("get_customers", verb="GET")
    assert status == 200, f"HTTP {status} sur get_customers : {payload}"
    assert payload["succeeded"] is True
    hits = [c for c in payload["customers"] if c["id"] == customer_id]
    return hits[0] if hits else None


def wait_until_synced(customer_id: str, *, after_version=0) -> dict:
    """Attend la fin de la synchro device, pas la simple présence dans la liste.

    Un client créé par l'API apparaît AVANT sa synchro, avec `version: 0` et un
    état transitoire. Attendre une version STRICTEMENT supérieure à
    `after_version` est la seule façon d'observer un état stable : se contenter
    de la présence produit des lectures non déterministes, et se contenter de
    `version > 0` ne détecte pas la fin d'une écriture ultérieure.
    """
    last = "jamais lu"
    for _ in range(SYNC_POLL_ATTEMPTS):
        customer = read_customer(customer_id)
        if customer is not None and customer["version"] > after_version:
            return customer
        last = "absent de get_customers" if customer is None else f"version={customer['version']}"
        time.sleep(SYNC_POLL_DELAY_S)
    raise AssertionError(
        f"Synchro non convergée après {SYNC_POLL_ATTEMPTS * SYNC_POLL_DELAY_S:.0f} s : "
        f"client {customer_id}, version attendue > {after_version} — dernier état lu : {last}"
    )


def wait_until_absent(customer_id: str) -> None:
    """Attend que le client ne soit plus listé par get_customers."""
    for _ in range(SYNC_POLL_ATTEMPTS):
        if read_customer(customer_id) is None:
            return
        time.sleep(SYNC_POLL_DELAY_S)
    raise AssertionError(
        f"Client {customer_id} toujours listé après "
        f"{SYNC_POLL_ATTEMPTS * SYNC_POLL_DELAY_S:.0f} s"
    )


@pytest.fixture
def throwaway_customer():
    """Crée un client jetable et garantit sa suppression, même en cas d'échec.

    Le teardown est idempotent : si le test a déjà supprimé le client, le second
    appel tombe sur "Customer not found" et n'est pas une erreur. On ne laisse
    jamais un CPTEST actif derrière soi.
    """
    body = dict(FIXTURE_FIELDS, externalId=f"cptest-2193-{uuid.uuid4().hex[:8]}")
    status, payload = call("create_customer", body=body)
    assert status == 201, f"Création du client jetable impossible : HTTP {status} — {payload}"
    assert payload["succeeded"] is True
    customer_id = payload["customerId"]

    try:
        yield customer_id
    finally:
        call("delete_customer", verb="DELETE", id=customer_id)


def test_01_customer_lifecycle_read_then_documented_route_then_real_delete(throwaway_customer):
    """Cycle de vie complet sur un client jetable — couvre AC1 et AC2.

    Étape 1 — le client créé est lisible et actif (prérequis : sans lui, une
    absence en fin de cycle pourrait signifier "jamais apparu" au lieu de
    "supprimé").
    Étape 2 — `DELETE .../update_customer`, la route ÉCRITE DANS LE TICKET, ne
    supprime pas. (Elle écrasait aussi les champs perso ; assertion retirée le
    2026-09-29 : `update_customer` est un PATCH depuis BOV2KABAN-2280, un corps
    vide ne touche plus rien.)
    Étape 3 — `DELETE .../delete_customer`, la route RÉELLE, applique le soft
    delete et le client sort des lectures.
    """
    # ── Étape 1 : état initial synchronisé ────────────────────────────────
    created = wait_until_synced(throwaway_customer)

    assert created["deleted"] is False
    for field, value in FIXTURE_FIELDS.items():
        assert created[field] == value, (
            f"Champ {field} non conservé à la création : attendu {value!r}, lu {created[field]!r}"
        )
    # `externalId` est envoyé à la création et PERDU au round-trip device :
    # renvoyé tel quel tant que `version == 0` (état transitoire), puis `null`
    # en version définitive. Plus précis que l'« open point » du ticket : le
    # champ est accepté et renvoyé un court instant avant d'être perdu, si bien
    # qu'un partenaire qui relit aussitôt croit sa réconciliation en place.
    # Seul l'état stable est assené — l'état transitoire est une course.
    assert created["externalId"] is None, (
        "`externalId` survit désormais à la synchro device — l'open point du ticket a bougé, "
        f"lu {created['externalId']!r}. Mettre à jour 2193 plutôt que ce test."
    )

    # ── Étape 2 : la route documentée est un update, pas une suppression ──
    status, payload = call("update_customer", verb="DELETE", id=throwaway_customer)
    assert status == 200, f"Attendu 200 sur DELETE update_customer, reçu {status} : {payload}"
    assert payload["succeeded"] is True

    updated = wait_until_synced(throwaway_customer, after_version=created["version"])
    assert updated["deleted"] is False, (
        "`deleted` posé par update_customer — la route documentée supprime désormais. "
        "Comportement CHANGÉ : mettre à jour BOV2KABAN-2193 et ce test."
    )

    # ── Étape 3 : AC1 + AC2 sur la route réelle ───────────────────────────
    status, payload = call("delete_customer", verb="DELETE", id=throwaway_customer)
    assert status == 200, (
        f"AC1 — attendu 200 sur DELETE delete_customer, reçu {status} : {payload}"
    )
    assert payload["succeeded"] is True
    assert payload["customerId"] == throwaway_customer

    # AC2 : plus listé du tout — le filtre soft-delete de BOV2KABAN-2190 le masque.
    wait_until_absent(throwaway_customer)


def test_02_deleting_an_unknown_customer_returns_a_business_error():
    """Chemin d'erreur de la suppression, non destructif."""
    status, payload = call("delete_customer", verb="DELETE", id=UNKNOWN_CUSTOMER_ID)

    assert status == 422, f"Attendu 422 sur client inconnu, reçu {status} : {payload}"
    assert payload["succeeded"] is False
    assert payload["error"] == "Customer not found", (
        f"Erreur métier attendue 'Customer not found', reçu {payload.get('error')!r}"
    )


def test_03_unauthorized_partner_is_rejected():
    """AC3 : capability absente → 403 ; identifiants invalides → 404. Non destructif."""
    status, payload = call(
        "delete_customer", verb="DELETE", id=UNKNOWN_CUSTOMER_ID, authenticated=False
    )
    assert status == 403, f"Attendu 403 sans identifiants, reçu {status} : {payload}"
    assert "capability" in payload.get("message", "").lower()

    status, payload = call(
        "delete_customer",
        verb="DELETE",
        id=UNKNOWN_CUSTOMER_ID,
        email="nobody@example.invalid",
        token="00000000-0000-0000-0000-000000000000",
    )
    assert status == 404, f"Attendu 404 sur identifiants invalides, reçu {status} : {payload}"


@pytest.mark.xfail(
    reason="BOV2KABAN-2193 : aucun garde-verbe sur delete_customer — GET/POST/PUT suppriment, "
    "là où BOV1 répond 'Please use DELETE HTTP method'. Un GET qui détruit des données "
    "client sur une surface partenaire. XPASS = le garde-verbe a été posé, retirer ce marqueur.",
    strict=False,
)
@pytest.mark.parametrize("verb", ["GET", "POST", "PUT"])
def test_04_delete_customer_rejects_verbs_other_than_delete(verb):
    """Attendu (parité BOV1) : seul DELETE est accepté sur `delete_customer`.

    Non destructif : la sonde porte sur un UUID inexistant. On observe donc quel
    contrôle intervient EN PREMIER — le verbe (attendu) ou le lookup (constaté).
    Un `Customer not found` prouve que la requête a atteint le handler de
    suppression : sur un id réel, elle aurait supprimé.
    """
    status, payload = call("delete_customer", verb=verb, id=UNKNOWN_CUSTOMER_ID)
    error = (payload or {}).get("error", "")

    assert "DELETE HTTP method" in error, (
        f"{verb} sur delete_customer atteint le handler de suppression "
        f"(HTTP {status}, error={error!r}) au lieu d'être rejeté sur le verbe"
    )
