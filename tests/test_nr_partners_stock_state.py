from __future__ import annotations

"""
Test de non-régression — état des stocks servi aux partenaires, et son usage au precheck

    GET  {base}/api/stocks/v1/{INSTALLATION_ID}/state
    GET  http://<CASHPAD_ID>.vpn.osilia.com:9091/orders/get_products_states      (caisse, VPN)
    POST {base}/api/orders/v1/{INSTALLATION_ID}/cashpad/precheck_order[?check_stocks=true]

LECTURE SEULE : `precheck_order` valide une commande SANS créer de ticket.

## Ce que fait BOV2

`stocks/v1/state` ne calcule rien : partners relaie la route caisse
`orders/get_products_states` (via vpn-proxy, `cashpad.api.ts`) et y ajoute
l'`external_id` du référentiel produits (static-model). La caisse est donc l'oracle.

| Test | Règle |
|---|---|
| test_01 | produits et options de `state` = ceux de la caisse, avec le même `enabled` (VPN, skip sinon) |
| test_02 | precheck `check_stocks=true` d'un produit disponible → 200, `checks.stocks.succeeded` |
| test_03 | precheck `check_stocks=true` d'un produit DÉSACTIVÉ → 422 « No stock » sur ce produit |
| test_04 | le même precheck SANS `check_stocks` → 200 : le stock n'est contrôlé qu'à la demande |

Observé le 2026-10-02 sur le staging (cashpad-8007) : 158 produits (8 désactivés) et 2
options, identiques à la caisse ; 3 produits seulement portent un `external_id`
(EXT_1010, EXT_ID_AM, EXT_3), non vérifiés faute de seconde source (le `full_menu` ne
l'expose pas). Les produits désactivés sont ABSENTS du `full_menu` : test_03 prend leur
id dans `state`, avec un prix quelconque, le stock étant contrôlé avant le prix. Sur un
refus de stock, `checks.connection.succeeded` vaut aussi false : non expliqué, non figé.

Lancer :
    uv run --with pytest --with httpx --with python-dotenv \
      pytest tests/test_nr_partners_stock_state.py -v
"""

import time

import httpx
import pytest
from dotenv import load_dotenv

load_dotenv()

from _nr import TIMEOUT_S, device_base, partner_call, unique_order_id

AVAILABLE = "12ac180d-9ec1-4741-89ab-9cfb3eb7d81e"  # « Poutine Vladimir tsar », 7 €


@pytest.fixture(scope="module")
def state() -> dict:
    status, payload = partner_call("stocks", 1, "state")
    assert status == 200 and (payload or {}).get("succeeded") is True, f"stocks state : HTTP {status} — {str(payload)[:300]}"
    return payload["state"]


@pytest.fixture(scope="module")
def disabled(state) -> str:
    ids = [p["product"] for p in state.get("products") or [] if not p.get("enabled")]
    if not ids:
        pytest.skip("aucun produit désactivé sur le site : test_03/04 sans objet")
    return ids[0]


def precheck(product: str, price: float, check_stocks: bool):
    body = {"customer": {}, "order": {
        "id": unique_order_id("nr-precheck-stock"), "date_order": int(time.time()), "channel": "CHANNEL",
        "nb_eaters": 1, "table_number": 3,
        "items": [{"pos_id": product, "price": price, "quantity": 1, "production_level": 0}], "payments": [],
    }}
    return partner_call("orders", 1, "precheck_order", verb="POST", body=body,
                        params={"check_stocks": "true"} if check_stocks else None)


def test_01_state_is_the_pos_state(state):
    try:
        response = httpx.get(f"{device_base()}/orders/get_products_states", timeout=TIMEOUT_S)
    except httpx.TransportError as exc:
        pytest.skip(f"caisse injoignable ({exc.__class__.__name__}) : VPN ?")
    pos = response.json()
    assert response.status_code == 200 and pos.get("succeeded") is True, f"caisse : HTTP {response.status_code}"
    for label, bo_rows, bo_key, pos_rows, pos_key in (
        ("produits", state.get("products"), "product", pos.get("products"), "product"),
        ("options", state.get("options"), "option", pos.get("productOptions"), "productOption"),
    ):
        bo = {r[bo_key].upper(): r["enabled"] for r in bo_rows or []}
        device = {r[pos_key].upper(): r["enabled"] for r in pos_rows or []}
        assert bo, f"aucun {label} dans stocks state"
        only_bo, only_pos = sorted(set(bo) - set(device)), sorted(set(device) - set(bo))
        flipped = sorted(k for k in set(bo) & set(device) if bo[k] != device[k])
        assert not (only_bo or only_pos or flipped), (
            f"{label} : seulement BO {only_bo[:5]}, seulement caisse {only_pos[:5]}, enabled différent {flipped[:5]}"
        )


def test_02_precheck_accepts_an_available_product():
    status, payload = precheck(AVAILABLE, 7.0, check_stocks=True)
    assert status == 200, f"precheck : HTTP {status} — {str(payload)[:300]}"
    assert ((payload.get("checks") or {}).get("stocks") or {}).get("succeeded") is True, f"checks : {payload.get('checks')!r}"


def test_03_precheck_refuses_a_disabled_product(disabled):
    status, payload = precheck(disabled, 1.0, check_stocks=True)
    assert status == 422, f"produit désactivé {disabled} : attendu 422, reçu {status} — {str(payload)[:300]}"
    errors = ((payload.get("checks") or {}).get("stocks") or {}).get("errors") or []
    hits = [e for e in errors if str(e.get("product", "")).upper() == disabled.upper()]
    assert hits and hits[0].get("msg") == "No stock", f"erreur de stock attendue sur {disabled} : {errors!r}"


def test_04_precheck_without_check_stocks_ignores_the_stock(disabled):
    status, payload = precheck(disabled, 1.0, check_stocks=False)
    assert status == 200, f"sans check_stocks, attendu 200, reçu {status} — {str(payload)[:300]}"
