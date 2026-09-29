from __future__ import annotations

"""
Test de non-régression porté — `cashpad-bov2-non-reg-deliverect`,
tests/partners/orders/test_partner_course_request.py

    POST {base}/api/orders/v1/{INSTALLATION_ID}/cashpad/push_order_sync   (ticket non payé)
    POST {base}/api/orders/v1/{INSTALLATION_ID}/cashpad/request_course    body {"receipt": <receipt_id>}

⚠️ CRÉE UN TICKET NON PAYÉ sur la caisse à chaque run (`tickets_guard`,
NR_ALLOW_WRITES=1). Il reste ouvert : la suite ne l'encaisse pas.

Observé le 2026-09-29 (staging, ticket 3219 ; préprod, ticket 3220), produit unique
à emporter : `request_course` → `{succeeded: true, receipt: {id, current_level: 1}}`.
L'ancien test attendait `current_level == 2` sur une commande multi-niveaux : le
niveau dépend des `production_level` des produits. Ce test fige donc la SÉMANTIQUE
(le ticket visé est celui du push, le niveau est un entier ≥ 1), pas une valeur.

Code HTTP de succès : l'ancien test attendait 201 (POST → `create` Feathers) ; 200 et
201 sont acceptés. Vert au run staging du 2026-09-29 (ticket 3224).

Lancer :
    NR_ALLOW_WRITES=1 uv run --with pytest --with httpx --with python-dotenv \
      pytest tests/test_nr_partners_course_request.py -v
"""

import time

import pytest
from dotenv import load_dotenv

load_dotenv()

from _nr import assert_pushed, partner_call, push_order, tickets_guard, unique_order_id

pytestmark = tickets_guard()


@pytest.fixture(scope="module")
def course():
    body = {"customer": {}, "order": {
        "id": unique_order_id("nr-course"), "date_order": int(time.time()), "channel": "CHANNEL",
        "nb_eaters": 1, "comment": "NR course request", "table_number": 1,
        "items": [{"pos_id": "12ac180d-9ec1-4741-89ab-9cfb3eb7d81e", "price": 7.0, "quantity": 1, "production_level": 0}],
        "payments": [],
    }}
    pushed = assert_pushed(*push_order(body))
    status, payload = partner_call("orders", 1, "request_course", verb="POST", body={"receipt": pushed["receipt_id"]})
    return pushed, status, payload


def test_01_request_course_is_accepted(course):
    _, status, payload = course
    assert status in (200, 201), f"attendu 200/201, reçu {status} — {payload!r}"
    assert payload.get("succeeded") is True, f"succeeded attendu : {payload!r}"


def test_02_targets_the_pushed_receipt_and_returns_its_level(course):
    pushed, _, payload = course
    receipt = payload.get("receipt") or {}
    assert receipt.get("id") == pushed["receipt_id"], f"receipt.id {receipt.get('id')!r} ≠ {pushed['receipt_id']!r}"
    level = receipt.get("current_level")
    assert isinstance(level, int) and level >= 1, f"current_level entier ≥ 1 attendu : {receipt!r}"
