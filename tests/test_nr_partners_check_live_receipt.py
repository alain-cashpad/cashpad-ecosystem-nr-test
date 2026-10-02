from __future__ import annotations

"""
Test de non-régression — incident PROD du 2026-10-01 (paiement à table Sunday / Flunch)

Chaque run pousse DEUX tickets non payés (donc non archivés), puis lit leur note par
l'action `check` de la Partner API :

    POST {base}/api/orders/v1/{INSTALLATION_ID}/cashpad/push_order_sync
    GET  {base}/api/payments/v2/{INSTALLATION_ID}/check?receipt_id=<UUID>
    GET  {base}/api/payments/v2/{INSTALLATION_ID}/check?sequential_id=<N>

⚠️ CRÉE DEUX TICKETS NON PAYÉS sur la caisse à chaque run (`tickets_guard`,
NR_ALLOW_WRITES=1). Ils restent ouverts : la suite ne les encaisse pas.

## Le chemin gardé

Pour un ticket pas encore archivé (`archiveSequentialId` nul), digested-data ne lit
pas la base : `findReceiptForExport` (receipt-util.ts) appelle
`worker-digested-data.getLiveReceipt`, qui lit le ticket EN DIRECT sur la caisse
(data-source.go `GetLiveReceipt`, deux branches : par `ReceiptID` ou par
`SequentialID`), puis éclate `items` et leurs `addons` par `items.reduce(...)`.

Le 2026-10-01 à 08:29, après la livraison prod de digested-data + worker-digested-data,
`getLiveReceipt` a répondu SANS `items` : `Cannot read properties of undefined
(reading 'reduce')`, puis `Could not find receipt` (422) côté partenaire. Le paiement
à table Sunday et Flunch (`payment/check`) était cassé sur tous les sites ; l'arrivée
des commandes, qui ne passe pas par ce chemin, marchait. Rollback effectif à 10:14.

## Cause (relevée le 2026-10-02)

BOV2KABAN-2195 (worker-digested-data, `bf07373`) ajoute `CustomerId common.NullUuid`
au ticket sans `MarshalJSON` propre : le type hérite de celui de `pgtype.UUID` (v1),
qui refuse d'encoder un UUID jamais renseigné (statut Undefined), alors qu'un `NULL`
lu en base s'encode en `null`. Sur un ticket live, le champ n'est jamais renseigné :
la réponse de `getLiveReceipt` part sans `items`. Un ticket archivé n'est pas touché.
Correctif : BOV2KABAN-2344 (`52594c3`, 2026-10-01 15:41), `NullUuid.MarshalJSON` →
`null`. Le comportement de `pgtype` est rapporté, pas relu dans ses sources.

Chronologie (labels Prometheus `Version` / `released`, git, logs Elastic) :

    staging  worker BOV2KABAN-2195 (build 70) → 01/10 14:30   17 lectures live sur 19 en `reduce`
    staging  worker BOV2KABAN-2344 (build 71) depuis 14:35    4 sur 4 OK
    préprod  2195 sur la branche le 30/09 16:53 (pas de métriques : date de commit,
             pas de déploiement) ; 72 lectures live OK du 28/09 au 30/09 17:04, aucune
             depuis — la préprod n'a jamais exercé ce code
    prod     build 11 du 01/10 08:30 à 10:10 = la fenêtre de l'incident ; builds 10 et 12 OK

Le commit exact de la build prod 11 n'est pas visible (le `master` du worker ne contient
pas 2195 aujourd'hui) : l'attribution repose sur la fenêtre, exacte à la minute.
Règle qui en découle : 2195 ne part jamais sans 2344.

Un ticket archivé passe par la base et ne détecte RIEN de ce défaut : il est déjà
couvert par test_bov2kaban_2223 (`check` sur les archives 400 et 411). Ici, seulement
des tickets live, sur les deux branches de `GetLiveReceipt`, avec et sans addons
(les addons sont ce que le `reduce` éclate).

## Observé / non observé

Même symptôme sur le staging le 2026-09-29 (cf. test_nr_partners_payments, ticket
3219) : `check?receipt_id=` → 422 `Could not find receipt` sur un ticket ouvert ;
préprod verte le même jour (ticket 3220), mais AVANT l'arrivée de 2195 sur la préprod.
Ce test n'a de valeur en préprod qu'une fois 2195 + 2344 DÉPLOYÉS.

VERT sur le staging le 2026-10-02 (worker BOV2KABAN-2344, build 71), deux runs
(ticket à addons du 1er run : 3263) : forme de `data` observée sur ticket live, quantités et prix en millièmes, addons
imbriqués sous leur produit (`items[].addons[].addon.id`). Relu sur la caisse (3263) :
mêmes produit et addons ; la caisse compte la quantité d'un addon en UNITÉS (1), `check`
en millièmes (1000). Le `customer` {lastname, firstname} du push ne rattache AUCUN
client au ticket (`customer` nul sur la caisse) : un ticket live avec un vrai
`CustomerId` n'est pas couvert. Catalogue (burger et ses addons) : celui de
payloads/deliverect/order_with_options, même site cashpad-8007 ; non revérifié en
préprod.

En cas d'échec, chercher dans les logs digested-data de la cible, sur la fenêtre du
run : « reading 'reduce' », « Could not find receipt », « extractReceipt ».

Lancer :
    NR_ALLOW_WRITES=1 uv run --with pytest --with httpx --with python-dotenv \
      pytest tests/test_nr_partners_check_live_receipt.py -v
"""

import time

import pytest
from dotenv import load_dotenv

load_dotenv()

from _nr import assert_pushed, partner_call, push_order, tickets_guard, unique_order_id

pytestmark = tickets_guard()

POUTINE = {"pos_id": "12ac180d-9ec1-4741-89ab-9cfb3eb7d81e", "price": 7.0}  # « Poutine Vladimir tsar »
BURGER = {"pos_id": "C3719D2A-AC84-4102-BF50-24FD174AD0A8", "price": 18.6}  # « Burger Comté - XL »
ADDONS = [
    {"pos_id": "D437F6FC-D997-4BD4-BDEC-1034E77AFD86", "price": 0, "quantity": 1},    # « Bleu »
    {"pos_id": "23E8ED30-A389-499B-97F5-67774EE578CF", "price": 2.9, "quantity": 1},  # « Supp Frites »
]


def push_open_ticket(label: str, items: list[dict], customer: dict) -> dict:
    body = {"customer": customer, "order": {
        "id": unique_order_id(f"nr-check-{label}"), "date_order": int(time.time()), "channel": "CHANNEL",
        "nb_eaters": 1, "comment": f"NR check live {label}", "table_number": 1,
        "items": items, "payments": [],
    }}
    return assert_pushed(*push_order(body))


def check(**selector) -> dict:
    status, payload = partner_call("payments", 2, "check", params=selector)
    assert status == 200, (
        f"check {selector} : attendu 200, reçu {status} — {payload!r}. Sur un ticket live, un 422 "
        "« Could not find receipt » est le symptôme de l'incident du 2026-10-01 (getLiveReceipt)"
    )
    assert isinstance(payload, dict) and payload.get("succeeded") is True, f"check {selector} : {payload!r}"
    data = payload.get("data")
    assert isinstance(data, dict), f"check {selector} : `data` absent — {payload!r}"
    return data


def items_by_product(data: dict) -> dict:
    out: dict = {}
    for item in data.get("items") or []:
        out.setdefault(str((item.get("product") or {}).get("id", "")).upper(), []).append(item)
    return out


@pytest.fixture(scope="module")
def simple_ticket():
    return push_open_ticket("simple", [{**POUTINE, "quantity": 1, "production_level": 0}], {})


@pytest.fixture(scope="module")
def addons_ticket():
    return push_open_ticket(
        "addons",
        [{**BURGER, "quantity": 1, "production_level": 0, "extras": ADDONS}],
        {"lastname": "NR", "firstname": "check live"},
    )


def assert_is_ticket(data: dict, ticket: dict):
    assert data.get("id") == ticket["receipt_id"], f"id {data.get('id')!r} ≠ {ticket['receipt_id']!r}"
    assert data.get("sequential_id") == int(ticket["receipt_sequential_id"]), (
        f"sequential_id {data.get('sequential_id')!r} ≠ {ticket['receipt_sequential_id']!r}"
    )
    assert data.get("items"), f"ticket live sans `items` (défaut du 2026-10-01) : {data!r}"


def test_01_check_live_receipt_by_receipt_id(simple_ticket):
    data = check(receipt_id=simple_ticket["receipt_id"])
    assert_is_ticket(data, simple_ticket)
    lines = items_by_product(data).get(POUTINE["pos_id"].upper())
    assert lines, f"Poutine absente du ticket : {[i.get('product') for i in data['items']]}"
    assert lines[0].get("quantity") == 1000, f"quantité (millièmes) : {lines[0]!r}"
    assert lines[0].get("unit_price") == round(POUTINE["price"] * 1000), f"prix (millièmes) : {lines[0]!r}"


def test_02_check_live_receipt_by_sequential_id(simple_ticket):
    """Seconde branche de GetLiveReceipt (extractReceiptsContentBySeqId)."""
    data = check(sequential_id=simple_ticket["receipt_sequential_id"])
    assert_is_ticket(data, simple_ticket)
    assert items_by_product(data).get(POUTINE["pos_id"].upper()), f"Poutine absente : {data['items']!r}"


def test_03_check_live_receipt_with_addons(addons_ticket):
    """Les addons sont ce que `items.reduce(...)` éclate (parentProductId) ; `check` les
    rend ensuite IMBRIQUÉS sous leur produit : `items[].addons[].addon.id`, quantité en
    millièmes, `unit_price` absent pour un addon gratuit (observé le 2026-10-02, ticket 3263)."""
    data = check(receipt_id=addons_ticket["receipt_id"])
    assert_is_ticket(data, addons_ticket)
    lines = items_by_product(data).get(BURGER["pos_id"].upper())
    assert lines, f"burger absent : {[i.get('product') for i in data['items']]}"
    addons = {str((a.get("addon") or {}).get("id", "")).upper(): a for a in lines[0].get("addons") or []}
    for addon in ADDONS:
        got = addons.get(addon["pos_id"].upper())
        assert got, f"addon {addon['pos_id']} absent du burger : {list(addons)}"
        assert got.get("quantity") == addon["quantity"] * 1000, f"quantité addon (millièmes) : {got!r}"
        if addon["price"]:
            assert got.get("unit_price") == round(addon["price"] * 1000), f"prix addon (millièmes) : {got!r}"
    expected = round((BURGER["price"] + sum(a["price"] for a in ADDONS)) * 1000)
    assert lines[0].get("final_price") == expected, f"final_price {lines[0].get('final_price')!r}, attendu {expected}"
