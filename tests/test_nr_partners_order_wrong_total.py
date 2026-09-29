from __future__ import annotations

"""
Test de non-régression porté — `cashpad-bov2-non-reg-deliverect`,
tests/partners/orders/test_partner_order_wrong_total_amount.py

Fige le comportement OBSERVÉ le 2026-09-29 sur le staging (cashpad-8007, obypay) :

    POST {base}/api/orders/v1/{INSTALLATION_ID}/cashpad/push_order_sync
        ?apiuser_email=...&apiuser_token=...
    body: commande à 4 produits (56,40 € avec frais), `amount_paid: 3300`

Observé : 400 `Payments inconsistency - amount_paid value (3300) differs from
payments_detail sum (56.4)` (`data.code: 103`). La commande est rejetée AVANT le
push caisse : aucun ticket créé — d'où l'absence de garde. L'ancien test notait
« currently ERROR 500 » : c'était un 500, c'est devenu un 400.

Résidu assumé : une ligne `Orders` en échec par run, dans la liste des commandes
du connecteur (cf. test_02).

`test_02` (statut `failed` dans la liste des commandes du connecteur, route BO,
JWT du front) : OBSERVÉ le 2026-09-29, en base (`orders`, connector 1123,
`display_id` = `order.id`, `status: failed`, `receipt_id` vide) puis par la route BO
(`data[].displayId`).

Lancer :
    uv run --with pytest --with httpx --with python-dotenv \
      pytest tests/test_nr_partners_order_wrong_total.py -v
"""

import time

import pytest
from dotenv import load_dotenv

load_dotenv()

from _nr import connector_order, push_order, unique_order_id

WRONG_AMOUNT_PAID = 3300


@pytest.fixture(scope="module")
def pushed():
    order_id = unique_order_id("nr-wrong-total")
    body = {
        "customer": {},
        "order": {
            "id": order_id, "date_order": int(time.time()), "channel": "CHANNEL",
            "amount_paid": WRONG_AMOUNT_PAID, "delivery_fee": 5.0, "service_charge": 10.0,
            "nb_eaters": 1, "type": 2, "comment": "", "table_number": 1,
            "items": [
                {"pos_id": "24DEF339-1C09-4682-A130-8C0EFA9FD31A", "price": 13.5, "quantity": 1},
                {"pos_id": "E08D3A4B-4C24-4AE5-8A76-87E111F7ED80", "price": 14.9, "quantity": 1},
                {"pos_id": "4A5BCE72-65DC-4BE3-A1F8-57ED2A2911C4", "price": 5.5, "quantity": 1},
                {"pos_id": "63C933A1-8DB5-4BD5-84FC-932A67586E1A", "price": 7.5, "quantity": 1},
            ],
            "payments": [{"amount": 56.4, "method": "cash", "transaction_id": "NR-WRONG-TOTAL"}],
        },
    }
    status, payload = push_order(body)
    return order_id, status, payload


def test_01_inconsistent_amount_paid_is_rejected_before_the_device(pushed):
    _, status, payload = pushed
    assert status == 400, f"attendu 400, reçu {status} — {payload!r}"
    message = (payload or {}).get("message") or ""
    assert "Payments inconsistency" in message and f"({WRONG_AMOUNT_PAID})" in message, (
        f"message inattendu : {message!r}"
    )
    assert (payload.get("data") or {}).get("code") == 103, f"data.code : {payload!r}"


def test_02_order_is_listed_as_failed_for_the_connector(pushed):
    order_id, _, _ = pushed
    order = connector_order("obypay", order_id, done=lambda o: o.get("status") == "failed")
    assert order["status"] == "failed", f"statut : {order!r}"
