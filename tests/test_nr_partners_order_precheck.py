from __future__ import annotations

"""
Test de non-régression porté — `cashpad-bov2-non-reg-partners-api`
(src/tests/orders/test_precheck.py) et `cashpad-bov2-non-reg-deliverect`
(tests/partners/orders/test_partner_order_precheck.py)

Fige le comportement OBSERVÉ le 2026-09-29 sur le staging ET la préprod
(cashpad-8007, partenaire obypay) :

    POST {base}/api/orders/v1/{INSTALLATION_ID}/cashpad/precheck_order
        ?apiuser_email=...&apiuser_token=...&check_stocks=<true|false>
    body: {"customer": {}, "order": {...}}

`precheck_order` valide une commande SANS créer de ticket (doc Notion « Order
pre-check »). Lecture seule de fait.

Observé :
  - « Armagnac test » (3107E6CB-…) × 2, `check_stocks=true` → 422
    `{succeeded: false, error: "Error", checks: {stocks: {succeeded: false,
    errors: [{msg: "No stock", product, qtyAvailable: 0, qtyRequested: 2000,
    type: 0}]}, connection: {succeeded: false}}}` — identique à l'ancien test.
    `qtyRequested` est en MILLIÈMES (2 → 2000).
  - même commande, `check_stocks=false` → 200 `{succeeded: true, checks: {}}` :
    sans contrôle de stock, rien n'est contrôlé.
  - `stock-state` ne liste PAS ce produit (liste vide) : la rupture vient de la
    caisse, pas de l'état de stock BOV2.

Écarts avec la doc, non figés (à requalifier s'ils changent) : les blocs
`checks.validity` et `checks.restaurant` annoncés par la doc sont absents ; la
réponse 422 expose une `backtrace` Node.

Lancer :
    uv run --with pytest --with httpx --with python-dotenv \
      pytest tests/test_nr_partners_order_precheck.py -v
"""

import time

import pytest
from dotenv import load_dotenv

load_dotenv()

from _nr import partner_call, unique_order_id

OUT_OF_STOCK_PRODUCT = "3107E6CB-4FE0-4F2F-B3D9-702495F868F3"  # « Armagnac test »
REQUESTED_QTY = 2


def order_body() -> dict:
    return {
        "customer": {},
        "order": {
            "id": unique_order_id("nr-precheck"),
            "date_order": int(time.time()),
            "channel": "CHANNEL",
            "nb_eaters": 1,
            "comment": "NR precheck",
            "table_number": 1,
            "items": [{"pos_id": OUT_OF_STOCK_PRODUCT, "price": 9.0,
                       "quantity": REQUESTED_QTY, "production_level": 0}],
            "payments": [],
        },
    }


def precheck(check_stocks: bool):
    return partner_call("orders", 1, "precheck_order", verb="POST",
                        params={"check_stocks": str(check_stocks).lower()}, body=order_body())


@pytest.fixture(scope="module")
def with_stocks():
    return precheck(True)


def test_01_out_of_stock_is_rejected_in_422(with_stocks):
    status, payload = with_stocks
    assert status == 422, f"attendu 422 (rupture), reçu {status} — {payload!r}"
    assert payload.get("succeeded") is False, f"succeeded=false attendu : {payload!r}"
    assert payload["checks"]["stocks"]["succeeded"] is False, f"checks.stocks : {payload['checks']!r}"


def test_02_stock_error_names_the_product_and_quantities(with_stocks):
    _, payload = with_stocks
    errors = [e for e in payload["checks"]["stocks"].get("errors") or []
              if e.get("product", "").upper() == OUT_OF_STOCK_PRODUCT]
    assert errors, f"aucune erreur de stock pour {OUT_OF_STOCK_PRODUCT} : {payload['checks']!r}"
    error = errors[0]
    assert error["msg"] == "No stock", f"msg : {error!r}"
    assert error["qtyAvailable"] == 0, f"qtyAvailable : {error!r}"
    assert error["qtyRequested"] == REQUESTED_QTY * 1000, f"qtyRequested en millièmes attendu : {error!r}"
    assert error["type"] == 0, f"type : {error!r}"


def test_03_without_stock_check_the_same_order_passes():
    status, payload = precheck(False)
    assert status == 200, f"attendu 200, reçu {status} — {payload!r}"
    assert payload.get("succeeded") is True, f"succeeded attendu : {payload!r}"
    assert payload.get("checks") == {}, f"aucun contrôle attendu sans check_stocks : {payload.get('checks')!r}"
