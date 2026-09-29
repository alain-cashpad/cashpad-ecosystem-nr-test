from __future__ import annotations

"""
Test de non-régression généré par /cp-test — ticket BOV2KABAN-2223
[BACK] Expose receipt delivery_id in archive_content and check payloads

Fige le comportement OBSERVÉ et VALIDÉ le 2026-09-29 sur le staging
(host allowlisté : staging.cashpad.app), partenaire obypay / site cashpad-8007 :

    GET {STAGING_BASE_URL}/api/salesdata/v2/{INSTALLATION_ID}/archive_content?sequential_id={N}
    GET {STAGING_BASE_URL}/api/payments/v2/{INSTALLATION_ID}/check?sequential_id={N}
    GET {STAGING_BASE_URL}/api/payments/v2/{INSTALLATION_ID}/check?receipt_id={UUID}

Auth = apiuser_email / apiuser_token (schéma des endpoints partner legacy).

## Ce que ce fichier garde

Le ticket a connu un défaut précis : `archive_content` exposait `delivery_id` mais
`check` non (`getRpcReceiptByIdOrUuid()` de digested-data ne sélectionnait pas la
colonne). Constaté les 2026-09-16 et 2026-09-24, corrigé au plus tard le 2026-09-29.
Le test compare donc **les deux endpoints sur le même ticket** : c'est l'écart entre
eux qui a cassé, pas chacun isolément.

Le cas négatif (ticket POS) est vérifié sur `check` aussi : avant le correctif la clé
était absente PARTOUT, donc le négatif était non discriminant ; il ne le devient que
parce que le positif passe.

## Critères volontairement non figés

* **check par `table` sur ticket ouvert** — aucun ticket ouvert sur le site
  (tables 0→12 → HTTP 422 `Receipt with table not found`).
* **`version` inchangée** — non mesurée le 2026-09-29 (le script de sonde déballe
  l'enveloppe) ; valeurs relevées le 2026-09-16 : archive_content 2.15, check 2.3.
* **Documentation Partner API** — hors périmètre d'un test API.

## Fixtures (staging cashpad-8007)

* archive 411 : 12 tickets Ordering API (seq 3186…), tous porteurs de `delivery_id`.
* archive 400 : 1 ticket POS (seq 3167), sans `delivery_id`.

Lecture seule : que des GET.

Lancer :
    uv run --with pytest --with httpx --with python-dotenv \
      pytest tests/test_bov2kaban_2223_receipt_delivery_id.py -v
"""

import os

import httpx
import pytest
from dotenv import load_dotenv

load_dotenv()


from _target import partner_env

ORDERING_ARCHIVE_SEQ = 411
POS_ARCHIVE_SEQ = 400

# Tickets figés à la vérification du 2026-09-29.
ORDERING_RECEIPT_SEQ = 3196
ORDERING_RECEIPT_ID = "b6531a35-af80-4554-afe7-310b76a13717"
ORDERING_RECEIPT_DELIVERY_ID = "a5c207ee-b661-11f1-b2c5-0e055cfdc60e"
ORDERING_RECEIPT_2_SEQ = 3186
ORDERING_RECEIPT_2_DELIVERY_ID = "obypay_b898da29-d815-49a4-8fce-b5e0b259fa3e"
POS_RECEIPT_SEQ = 3167


def get_env() -> dict:
    """Cible, alias et couple partenaire — cf. `_target.py` (NR_TARGET)."""
    env = partner_env()
    return env


def _get(env: dict, path: str, **params) -> dict:
    response = httpx.get(
        f"{env['base_url'].rstrip('/')}/api/{path.format(id=env['installation_id'])}",
        params={
            "apiuser_email": env["apiuser_email"],
            "apiuser_token": env["apiuser_token"],
            **params,
        },
        timeout=60,
    )
    assert response.status_code == 200, f"{path} {params} : {response.status_code}\n{response.text[:300]}"
    body = response.json()
    # Enveloppe {succeeded, version, data} ; on tolère un corps déjà déballé.
    return body.get("data", body) if isinstance(body.get("data"), dict) else body


def archive_receipts(env: dict, seq: int) -> list[dict]:
    return _get(env, "salesdata/v2/{id}/archive_content", sequential_id=seq)["receipts"]


def check(env: dict, **selector) -> dict:
    return _get(env, "payments/v2/{id}/check", **selector)


@pytest.fixture(scope="module")
def env() -> dict:
    return get_env()


def test_01_archive_content_ordering_receipts_carry_delivery_id(env):
    receipts = archive_receipts(env, ORDERING_ARCHIVE_SEQ)
    assert receipts, f"archive {ORDERING_ARCHIVE_SEQ} vide"
    missing = [r["sequential_id"] for r in receipts if not r.get("delivery_id")]
    assert not missing, f"tickets Ordering API sans delivery_id : {missing}"
    by_seq = {r["sequential_id"]: r["delivery_id"] for r in receipts}
    assert by_seq[ORDERING_RECEIPT_SEQ] == ORDERING_RECEIPT_DELIVERY_ID
    assert by_seq[ORDERING_RECEIPT_2_SEQ] == ORDERING_RECEIPT_2_DELIVERY_ID


def test_02_archive_content_pos_receipt_omits_delivery_id(env):
    receipts = archive_receipts(env, POS_ARCHIVE_SEQ)
    assert receipts, f"archive {POS_ARCHIVE_SEQ} vide"
    assert all("delivery_id" not in r for r in receipts)


def test_03_check_by_sequential_id_returns_delivery_id(env):
    for seq, expected in (
        (ORDERING_RECEIPT_SEQ, ORDERING_RECEIPT_DELIVERY_ID),
        (ORDERING_RECEIPT_2_SEQ, ORDERING_RECEIPT_2_DELIVERY_ID),
    ):
        assert check(env, sequential_id=seq).get("delivery_id") == expected, f"seq {seq}"


def test_04_check_by_receipt_id_returns_delivery_id(env):
    assert check(env, receipt_id=ORDERING_RECEIPT_ID).get("delivery_id") == ORDERING_RECEIPT_DELIVERY_ID


def test_05_check_pos_receipt_omits_delivery_id(env):
    assert "delivery_id" not in check(env, sequential_id=POS_RECEIPT_SEQ)


def test_06_check_and_archive_content_agree_on_delivery_id(env):
    """Le défaut d'origine : archive_content la servait, check non."""
    for receipt in archive_receipts(env, ORDERING_ARCHIVE_SEQ):
        seq = receipt["sequential_id"]
        assert check(env, sequential_id=seq).get("delivery_id") == receipt["delivery_id"], f"seq {seq}"
