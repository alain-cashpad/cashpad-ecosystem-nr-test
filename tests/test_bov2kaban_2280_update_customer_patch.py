from __future__ import annotations

"""
Test de non-régression généré par /cp-test — ticket BOV2KABAN-2280
[BACK] update_customer wipes every field not transmitted (data-loss risk for partners)

Fige le comportement OBSERVÉ et VALIDÉ le 2026-09-28 sur le staging
(host allowlisté : staging.cashpad.app), endpoint partner customers :

    POST {STAGING_BASE_URL}/api/customers/v1/{INSTALLATION_ID}/update_customer
        ?apiuser_email=...&apiuser_token=...
    body JSON : {"id": <uuid>, <champ>: <valeur>}

Décision produit : `update_customer` est un PATCH — seuls les champs transmis
sont appliqués, les autres restent intacts. C'est ce que garde ce fichier (AC2
de 2280). Historique des écarts qu'il verrouille :
  - 2026-09-03 : remplacement arbitraire (3 champs survivants sur 11) ;
  - 2026-09-24 : PATCH, mais `lastName` atterrissait dans `name` — corrigé par
    le commit `cf807fa` du service `customers` (2026-09-28) → `test_03`.

`email` N'EST PAS modifiable via `update_customer`, par choix produit : la
requête répond 201 `succeeded: true` sans effet. `test_04` fige ce contrat.

⚠️ ÉCRITURE sur staging. Chaque run crée un client jetable (`create_customer`),
le met à jour champ par champ, puis le soft-delete (`delete_customer`) en
teardown. Aucune fixture partagée n'est touchée.

Mesure faite avant synchro device (`version` = 0) : le comportement après
synchro avec la caisse n'est pas couvert.

Golden ciblé : status_code + `succeeded` + valeur des champs relus via
`get_customer`. Pas de snapshot complet.
"""

import os
import uuid

import httpx
import pytest
from dotenv import load_dotenv

load_dotenv()


from _target import partner_env, writes_guard

# Module en écriture : skippé hors staging sans NR_ALLOW_WRITES=1.
pytestmark = writes_guard()

# Champs documentés relus via get_customer. `name` n'est pas renseigné
# distinctement à la création (il prend la valeur de `lastName`) : il n'est
# comparé qu'après update.
TAG = uuid.uuid4().hex[:6]
INITIAL = dict(
    firstName=f"Fn{TAG}", lastName=f"Ln{TAG}", company=f"Co{TAG}", street=f"1 rue {TAG}",
    zipCode="75001", city="Paris", country="FR", code=f"CP2280{TAG}", phone="0600000000",
    email=f"nr2280-{TAG}@example.com", externalId=f"ext{TAG}",
)
UPDATABLE = dict(
    firstName="FN2", lastName="LN2", name="NM2", company="CO2", street="2 av X",
    zipCode="69001", city="Lyon", country="BE", code=f"CP2280b{TAG}", phone="0611111111",
    externalId=f"ext2{TAG}",
)
CHECKED_FIELDS = list(UPDATABLE)


def get_env() -> dict:
    """Cible, alias et couple partenaire — cf. `_target.py` (NR_TARGET)."""
    env = partner_env()
    return env


def call(method: str, action: str, *, body=None, **query):
    """Appel partner customers. Renvoie (status_code, payload). Auth en query string."""
    env = get_env()
    url = f"{env['base_url'].rstrip('/')}/api/customers/v1/{env['installation_id']}/{action}"
    params = {"apiuser_email": env["apiuser_email"], "apiuser_token": env["apiuser_token"], **query}
    response = httpx.request(method, url, params=params, json=body, timeout=60)
    try:
        return response.status_code, response.json()
    except ValueError:
        return response.status_code, None


def read_customer(customer_id: str) -> dict:
    status, payload = call("GET", "get_customer", id=customer_id)
    assert status == 200, f"get_customer en échec : {status} {payload}"
    return payload["customers"]  # objet unique, pas de tableau ni d'enveloppe `data`


def update(customer_id: str, **fields) -> None:
    status, payload = call("POST", "update_customer", body={"id": customer_id, **fields})
    assert status == 201, f"update_customer {fields} : attendu 201, reçu {status} : {payload}"
    assert payload["succeeded"] is True


@pytest.fixture(scope="module")
def customer_id():
    status, payload = call("POST", "create_customer", body=INITIAL)
    assert status == 201, f"create_customer : attendu 201, reçu {status} : {payload}"
    cid = payload["customerId"]
    yield cid
    call("DELETE", "delete_customer", id=cid)


def test_01_created_customer_holds_all_fields(customer_id):
    """Pré-condition : les 11 champs transmis à la création sont relus tels quels."""
    customer = read_customer(customer_id)
    diff = {k: (v, customer.get(k)) for k, v in INITIAL.items() if customer.get(k) != v}
    assert not diff, f"Champs non persistés à la création : {diff}"


# `lastName` retiré le 2026-09-29 : le modifier modifie aussi `name` (correspondance
# `lastName` → `name` connue, cf. test_03), ce que ce test comptait comme un champ
# écrasé. Le cas ne correspondait plus au comportement actuel.
@pytest.mark.parametrize("field", [f for f in CHECKED_FIELDS if f != "lastName"])
def test_02_single_field_update_is_a_patch(customer_id, field):
    """AC2 : un update à un seul champ applique ce champ et laisse TOUS les autres intacts.

    Régression gardée : le 2026-09-03, 7 champs sur 11 étaient remis à null.
    Indépendant de l'ordre d'exécution : l'état de référence est relu juste avant.
    """
    before = read_customer(customer_id)
    update(customer_id, **{field: UPDATABLE[field]})
    after = read_customer(customer_id)

    assert after.get(field) == UPDATABLE[field], (
        f"`{field}` non appliqué : attendu {UPDATABLE[field]!r}, relu {after.get(field)!r}"
    )
    wiped = {
        k: (before.get(k), after.get(k))
        for k in CHECKED_FIELDS + ["email"]
        if k != field and after.get(k) != before.get(k)
    }
    assert not wiped, f"Update de `{field}` a modifié d'autres champs (avant, après) : {wiped}"


def test_03_last_name_is_distinct_from_name(customer_id):
    """AC2 : `lastName` et `name` sont deux champs indépendants.

    Régression gardée : le 2026-09-24, `lastName` était écrit dans `name` et
    la colonne `last_name` jamais mise à jour (corrigé par `cf807fa`).
    """
    update(customer_id, lastName=f"LN3{TAG}", name=f"NM3{TAG}")
    customer = read_customer(customer_id)
    assert customer.get("lastName") == f"LN3{TAG}"
    assert customer.get("name") == f"NM3{TAG}"


def test_04_email_is_not_updatable(customer_id):
    """Contrat produit : `email` n'est pas modifiable via update_customer.

    La requête est acceptée (201, `succeeded: true`) mais sans effet. Si ce test
    casse, l'email est devenu modifiable : confirmer la décision produit avant
    de mettre à jour le golden.
    """
    before = read_customer(customer_id)["email"]
    update(customer_id, email=f"changed-{TAG}@example.com")
    assert read_customer(customer_id)["email"] == before
