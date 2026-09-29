from __future__ import annotations

"""
Test de non-régression porté — `cashpad-bov2-non-reg-partners-api`
(src/tests/orders/test_order.py, test_installation_id_mapping.py) et
`cashpad-bov2-non-reg-deliverect` (tests/partners/orders/test_partner_order.py)

    POST {base}/api/orders/v1/{INSTALLATION_ID}/cashpad/push_order_sync
        ?apiuser_email=...&apiuser_token=...
    body: {"customer": {}, "order": {..., 4 produits dont 2 avec options, payé}}

⚠️ CRÉE UN TICKET PAYÉ sur la caisse à chaque run (`tickets_guard`, NR_ALLOW_WRITES=1).

Observé le 2026-09-29 (staging et préprod, cashpad-8007, obypay) : push accepté en
200 `{succeeded, receipt_id, receipt_sequential_id, receipt_period_id}`, sans
enveloppe `data` (doc « Order sending »). Montants en float euros TTC, date en
epoch secondes.

OBSERVÉ le 2026-09-29 au run staging (NR_ALLOW_WRITES=1, ticket 3226), tous verts :
  - test_02 : la commande figure dans la liste du connecteur, rattachée au bon
    connector-config et au bon ticket — c'est ce que vérifiait
    `test_installation_id_mapping` (jamais exécuté dans l'ancien repo : sa méthode
    n'avait pas le préfixe `test_`) ;
  - test_03/04 : le ticket lu sur la caisse porte `deliveryId` = `order.id`, les
    quantités et prix unitaires ×1000, et le montant payé.

Lancer :
    NR_ALLOW_WRITES=1 uv run --with pytest --with httpx --with python-dotenv \
      pytest tests/test_nr_partners_order_simple.py -v
"""

import time

import pytest
from dotenv import load_dotenv

load_dotenv()

from _nr import (assert_pushed, connector_order, device_receipt, push_order,
                 receipt_addon, receipt_item, site, tickets_guard, unique_order_id)

pytestmark = tickets_guard()

ITEMS = [
    {"pos_id": "24DEF339-1C09-4682-A130-8C0EFA9FD31A", "price": 13.5, "quantity": 1, "production_level": None},
    {"pos_id": "E08D3A4B-4C24-4AE5-8A76-87E111F7ED80", "price": 14.9, "quantity": 1, "production_level": 0,
     "extras": [{"pos_id": "D437F6FC-D997-4BD4-BDEC-1034E77AFD86", "price": 0, "quantity": 1},
                {"pos_id": "BE1BD607-53AE-47BF-B5D7-7B640EF8847A", "price": 0, "quantity": 1}]},
    {"pos_id": "4A5BCE72-65DC-4BE3-A1F8-57ED2A2911C4", "price": 5.5, "quantity": 1, "production_level": 1,
     "extras": [{"pos_id": "CC4CF91B-B06D-41D3-91DB-8EACB702D0F4", "price": 0, "quantity": 1},
                {"pos_id": "5ACF2DAE-E47B-44B6-BE2A-ACA4D73CCCE6", "price": 0, "quantity": 1},
                {"pos_id": "C27008AF-76AE-4F2B-8CD8-26C5FCB392AA", "price": 0, "quantity": 1}]},
    {"pos_id": "63C933A1-8DB5-4BD5-84FC-932A67586E1A", "price": 7.5, "quantity": 1, "production_level": 2},
]
AMOUNT_PAID = 56.4  # 41,40 € de produits + 5 € de livraison + 10 € de service


@pytest.fixture(scope="module")
def order():
    order_id = unique_order_id("nr-order-simple")
    body = {"customer": {}, "order": {
        "id": order_id, "date_order": int(time.time()), "channel": "CHANNEL",
        "amount_paid": AMOUNT_PAID, "delivery_fee": 5.0, "service_charge": 10.0,
        "nb_eaters": 1, "type": 2, "comment": "NR order simple", "table_number": 1,
        "items": ITEMS,
        "payments": [{"amount": AMOUNT_PAID, "method": "cash", "transaction_id": order_id[-12:]}],
    }}
    status, payload = push_order(body)
    return body, status, payload


def test_01_push_is_accepted(order):
    _, status, payload = order
    assert_pushed(status, payload)


def test_02_order_is_linked_to_the_connector_and_the_receipt(order):
    body, status, payload = order
    assert_pushed(status, payload)
    listed = connector_order("obypay", body["order"]["id"], done=lambda o: bool(o.get("receiptId")))
    assert listed["externalId"] == body["order"]["id"], f"externalId : {listed!r}"
    assert listed["connectorConfigId"] == site()["connectors"]["obypay"], f"connectorConfigId : {listed!r}"
    assert listed["receiptId"] == str(payload["receipt_sequential_id"]), f"receiptId : {listed!r}"
    assert listed["receiptPeriodId"] == payload["receipt_period_id"], f"receiptPeriodId : {listed!r}"


def test_03_device_receipt_carries_the_order(order):
    body, status, payload = order
    assert_pushed(status, payload)
    receipt = device_receipt(payload["receipt_sequential_id"])
    assert receipt["deliveryId"] == body["order"]["id"], f"deliveryId : {receipt.get('deliveryId')!r}"
    assert receipt["note"] == body["order"]["comment"], f"note : {receipt.get('note')!r}"
    assert receipt["amountPaid"] == round(AMOUNT_PAID * 1000), f"amountPaid (millièmes) : {receipt.get('amountPaid')!r}"


@pytest.mark.parametrize("item", ITEMS, ids=lambda i: i["pos_id"][:8])
def test_04_device_receipt_items_quantities_and_prices(order, item):
    _, status, payload = order
    assert_pushed(status, payload)
    receipt = device_receipt(payload["receipt_sequential_id"])
    line = receipt_item(receipt, item["pos_id"])
    assert line["qty"] == item["quantity"] * 1000, f"qty (millièmes) : {line!r}"
    assert line["priceInclTaxes"] == round(item["price"] * 1000), f"priceInclTaxes (millièmes) : {line!r}"
    for extra in item.get("extras") or []:
        receipt_addon(receipt, extra["pos_id"])
