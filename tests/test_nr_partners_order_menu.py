from __future__ import annotations

"""
Test de non-régression porté — `cashpad-bov2-non-reg-deliverect`,
tests/partners/orders/test_partner_order_with_menu.py

    POST {base}/api/orders/v1/{INSTALLATION_ID}/cashpad/push_order_sync
        ?apiuser_email=...&apiuser_token=...
    body: 3 × menu « Big Boss » (80D7F8CF-…, 9,90 €) et ses 3 composants en `children`

⚠️ CRÉE UN TICKET PAYÉ sur la caisse à chaque run (`tickets_guard`, NR_ALLOW_WRITES=1).

L'ancien test passait par la route native `/p/partners/public/1/obypay/cashpad-8007/
order/push-order-sync` (non documentée) ; ici la route de la doc Notion.

Catalogue vérifié le 2026-09-29 (staging et préprod) : le menu et ses composants
existent. Ticket caisse (test_02) OBSERVÉ au run staging du 2026-09-29 (ticket 3225) :
chaque composant apparaît comme une ligne produit, quantité = quantité du composant
× quantité du menu, en millièmes.

Lancer :
    NR_ALLOW_WRITES=1 uv run --with pytest --with httpx --with python-dotenv \
      pytest tests/test_nr_partners_order_menu.py -v
"""

import time

import pytest
from dotenv import load_dotenv

load_dotenv()

from _nr import assert_pushed, device_receipt, push_order, receipt_item, tickets_guard, unique_order_id

pytestmark = tickets_guard()

MENU = {
    "name": "Menu", "pos_id": "80D7F8CF-0A4C-4374-96EA-A74978CD1011", "price": 9.9, "quantity": 3, "extras": None,
    "children": [
        {"name": "Poulet Croustillant 6", "pos_id": "0722CF14-01B6-454D-B43A-E65632B76FD2", "price": 0, "quantity": 1, "production_level": 0, "extras": []},
        {"name": "Capri-sun", "pos_id": "501E9C4B-EBCD-4636-B6D6-E475D69F7E78", "price": 0, "quantity": 1, "production_level": 0, "extras": []},
        {"name": "Glace Push Up", "pos_id": "B3AF71F7-C292-4BC3-A0C3-EBEC10315C96", "price": 0, "quantity": 1, "production_level": 0, "extras": []},
    ],
}
AMOUNT_PAID = 44.7  # 3 × 9,90 € + 5 € de livraison + 10 € de service


@pytest.fixture(scope="module")
def order():
    now = int(time.time())
    order_id = unique_order_id("nr-order-menu")
    body = {"customer": {"lastname": "NR", "firstname": "menu"}, "order": {
        "id": order_id, "type": 2, "channel": "CHANNEL", "comment": "", "nb_eaters": 0,
        "date_order": now, "date_create": now, "table_number": 1,
        "discount_amount": 0, "delivery_fee": 5.0, "service_charge": 10.0, "amount_paid": AMOUNT_PAID,
        "items": [MENU],
        "payments": [{"amount": AMOUNT_PAID, "method": "cash", "transaction_id": order_id[-12:]}],
    }}
    status, payload = push_order(body)
    return body, status, payload


def test_01_push_is_accepted(order):
    _, status, payload = order
    assert_pushed(status, payload)


def test_02_device_receipt_expands_the_menu(order):
    _, status, payload = order
    assert_pushed(status, payload)
    receipt = device_receipt(payload["receipt_sequential_id"])
    menu_line = receipt_item(receipt, MENU["pos_id"])
    assert menu_line["qty"] == MENU["quantity"] * 1000, f"qty du menu (millièmes) : {menu_line!r}"
    assert menu_line["priceInclTaxes"] == round(MENU["price"] * 1000), f"prix du menu (millièmes) : {menu_line!r}"
    for child in MENU["children"]:
        line = receipt_item(receipt, child["pos_id"])
        expected = child["quantity"] * MENU["quantity"] * 1000
        assert line["qty"] == expected, f"{child['name']} : qty {line.get('qty')!r}, attendu {expected}"
