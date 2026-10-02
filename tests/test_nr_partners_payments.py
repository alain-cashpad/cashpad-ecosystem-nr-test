from __future__ import annotations

"""
Test de non-régression porté — `cashpad-bov2-non-reg-partners-api`,
src/tests/payments/test_inject_single_payment.py,
test_inject_single_negative_payment.py, test_inject_multiple_payments.py

Chaque test pousse SA commande non payée (1 × « Poutine Vladimir tsar », 7 €,
table 1), puis injecte un paiement sur ce ticket ouvert et relit la caisse :

    PUT  {base}/api/payments/v2/{INSTALLATION_ID}/inject_payment
        ?apiuser_email=...&apiuser_token=...&receipt_id=...&amount=...&method=...&transaction_id=...
    POST {base}/api/payments/v2/{INSTALLATION_ID}/inject_payments
        body: {receipt_id, transaction_id, payments[], tip, discount_amount}

Routes et verbes de la doc Notion « Payment » : `inject_payment` en PUT, TOUT en
query (montant compris) ; `inject_payments` en POST avec corps. Montants en float
euros ; la caisse les stocke ×1000 ; `transaction_id` y devient le `voucher` du
paiement. `method` = mot-clé (`cash`, `creditcard`, `tip`).

⚠️ CRÉE TROIS TICKETS sur la caisse à chaque run (`tickets_guard`, NR_ALLOW_WRITES=1).

## Vert sur le staging le 2026-10-02 — rouge du 2026-09-29 au 2026-10-01

Pour un ticket non archivé, BOV2 lit le ticket EN DIRECT sur la caisse via
worker-digested-data (`findReceiptForExport` → `getLiveReceipt`) ; `inject_payment`
en dépend depuis BOV2KABAN-1732 (2025-10-13).

Rouge le 2026-09-29 sur le staging (ticket 3219) : `inject_payment` et
`inject_payments` → 400 `internal communication error` (errorCode 5), et
`check?receipt_id=` → 422 `Could not find receipt`, sur un ticket ouvert que la
caisse connaît (`request_course` OK). Cause : le worker staging tournait sur
BOV2KABAN-2195 (`CustomerId` NullUuid sans `MarshalJSON`) : `getLiveReceipt`
répondait sans `items`. C'est le défaut parti en PROD le 2026-10-01 (08:30 → 10:14,
paiement à table Sunday / Flunch cassé, cf. test_nr_partners_check_live_receipt).
La préprod était verte le 2026-09-29 (ticket 3220) parce que 2195 n'y était pas
encore (arrivé sur la branche le 2026-09-30 16:53).

Corrigé par BOV2KABAN-2344 (`NullUuid.MarshalJSON`), déployé sur le staging le
2026-10-01 14:35. Run vert du 2026-10-02 : 3/3, vouchers, montants ×1000,
`discountAmount` et pourboire négatif d'`inject_payments` relus sur la caisse.
Choix maintenu : ce fichier échoue franchement si le défaut revient (pas de xfail).

Lancer :
    NR_ALLOW_WRITES=1 uv run --with pytest --with httpx --with python-dotenv \
      pytest tests/test_nr_partners_payments.py -v
"""

import time
import uuid

import pytest
from dotenv import load_dotenv

load_dotenv()

from _nr import assert_pushed, device_receipt, partner_call, push_order, tickets_guard, unique_order_id

pytestmark = tickets_guard()

PRODUCT = "12ac180d-9ec1-4741-89ab-9cfb3eb7d81e"  # « Poutine Vladimir tsar », 7 €


def open_ticket() -> dict:
    body = {"customer": {}, "order": {
        "id": unique_order_id("nr-payment"), "date_order": int(time.time()), "channel": "CHANNEL",
        "nb_eaters": 1, "comment": "NR payment", "table_number": 1,
        "items": [{"pos_id": PRODUCT, "price": 7.0, "quantity": 1, "production_level": 0}],
        "payments": [],
    }}
    return assert_pushed(*push_order(body))


def tid(label: str) -> str:
    return f"NR-{label}-{uuid.uuid4().hex[:8]}"


def assert_injected(status, payload):
    assert status == 200, f"attendu 200, reçu {status} — {payload!r}"
    assert isinstance(payload, dict) and payload.get("succeeded") is True, f"injection refusée : {payload!r}"
    assert payload.get("version") == "2.3", f"version : {payload.get('version')!r}"


def payments_by_voucher(receipt: dict) -> dict:
    out: dict = {}
    for p in receipt.get("payments") or []:
        out.setdefault(p.get("voucher"), []).append(p)
    return out


def test_01_single_payment_with_tip_and_discount():
    ticket = open_ticket()
    transaction = tid("SINGLE")
    status, payload = partner_call("payments", 2, "inject_payment", verb="PUT", params={
        "receipt_id": ticket["receipt_id"], "amount": 5, "method": "creditcard",
        "transaction_id": transaction, "tip_amount": 2, "discount_amount": 2,
    })
    assert_injected(status, payload)

    receipt = device_receipt(ticket["receipt_sequential_id"])
    amounts = [p.get("amount") for p in payments_by_voucher(receipt).get(transaction, [])]
    assert 7000 in amounts, f"paiement 5 € + 2 € de pourboire (7000) attendu sous le voucher {transaction} : {amounts!r}"
    assert receipt.get("discountAmount") == 2000, f"discountAmount (millièmes) : {receipt.get('discountAmount')!r}"


def test_02_single_negative_payment():
    ticket = open_ticket()
    transaction = tid("NEGATIVE")
    status, payload = partner_call("payments", 2, "inject_payment", verb="PUT", params={
        "receipt_id": ticket["receipt_id"], "amount": -2.0, "method": "cash", "transaction_id": transaction,
    })
    assert_injected(status, payload)

    receipt = device_receipt(ticket["receipt_sequential_id"])
    amounts = [p.get("amount") for p in payments_by_voucher(receipt).get(transaction, [])]
    assert amounts == [-2000], f"un paiement de -2000 attendu sous le voucher {transaction} : {amounts!r}"


def test_03_multiple_payments_with_tip_and_discount():
    ticket = open_ticket()
    payments = [
        {"amount": 6.0, "method": "cash", "transaction_id": tid("CASH")},
        {"amount": 1.0, "method": "creditcard", "transaction_id": tid("CB")},
        {"amount": -1.0, "method": "cash", "transaction_id": tid("NEGATIVE")},
    ]
    tip = {"amount": 1.0, "method": "tip", "transaction_id": tid("TIP")}
    status, payload = partner_call("payments", 2, "inject_payments", verb="POST", body={
        "receipt_id": ticket["receipt_id"], "transaction_id": tid("MAIN"),
        "discount_amount": 1.0, "payments": payments, "tip": tip,
    })
    assert_injected(status, payload)

    receipt = device_receipt(ticket["receipt_sequential_id"])
    by_voucher = payments_by_voucher(receipt)
    # Parité BOV1 (api/v2/payments_controller.rb, inject_payments l. 252-257) : le `tip` objet est
    # ajouté aux paiements en NÉGATIF. Le `tip_amount` du paiement simple (test_01) reste positif.
    for p in payments + [{**tip, "amount": -tip["amount"]}]:
        amounts = [x.get("amount") for x in by_voucher.get(p["transaction_id"], [])]
        assert round(p["amount"] * 1000) in amounts, (
            f"{p['method']} {p['amount']} € attendu en {round(p['amount'] * 1000)} sous le voucher "
            f"{p['transaction_id']} : {amounts!r}"
        )
    assert receipt.get("discountAmount") == 1000, f"discountAmount (millièmes) : {receipt.get('discountAmount')!r}"
