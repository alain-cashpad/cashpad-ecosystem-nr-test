from __future__ import annotations

"""
Test de non-régression généré par /cp-test — ticket BOV2KABAN-2121
[BACK] Expose external_loyalty per receipt in salesdata archive_content

Fige le comportement OBSERVÉ et VALIDÉ le 2026-07-03 sur le staging
(host allowlisté : staging.cashpad.app), endpoint public partner salesdata :

    GET {STAGING_BASE_URL}/api/salesdata/v2/{INSTALLATION_ID}/archive_content
        ?apiuser_email=...&apiuser_token=...&sequential_id={SEQUENTIAL_ID}

Auth = credentials partner (apiuser_email / apiuser_token) — schéma propre à
cet endpoint public salesdata (pas le bearer BOV2_STAGING_TOKEN des services
digested-data/partners). Aligné sur test_cp_sales_data_archives_content_compare.py.

Golden ciblé : status_code + uniquement les champs de `observed` liés aux
acceptance criteria du ticket. Pas de snapshot complet de la réponse.
"""

import os
import pytest
import httpx
from dotenv import load_dotenv

load_dotenv()


# ── Ancre golden verbatim (criterion 3) ──
# Receipt archivé stable (archive immuable, période 582, ventes du 2025-04-01)
# capturé lors de la vérification /cp-test du 2026-07-03.
ANCHOR_SEQUENTIAL_ID = 565325
ANCHOR_EXTERNAL_LOYALTY = {
    "email": "claudefarge@mac.com",
    "phone": "0643514578",
    "lastName": "Farge",
    "provider": 4,
    "accountId": "7aa187f6-a48d-4da7-b256-724fd0d0e9e1",
    "firstName": "Claude",
    "fundsAvailable": 0,
    "pointsAvailable": 29,
    "saleTransactionId": "JofzY9AssZrYrnQBoyTyhADZoodgNP3en2hJFeavhFkw8",
}


def get_env() -> dict:
    """Charge les variables statiques depuis .env (mêmes noms que /cp-test + convention repo)."""
    required = [
        "staging_base_url",   # base staging (host allowlisté) — cf. /cp-test
        "installation_id",    # device / installation ciblé (ex. cashpad-8000-kkdf)
        "apiuser_email",      # auth partner salesdata
        "apiuser_token",      # auth partner salesdata
    ]
    env = {}
    missing = []
    for key in required:
        value = os.getenv(key.upper())
        if not value:
            missing.append(key.upper())
        else:
            env[key] = value
    if missing:
        raise EnvironmentError(f"Variables manquantes dans .env : {missing}")
    env["sequential_id"] = os.getenv("SEQUENTIAL_ID", "486")
    return env


@pytest.fixture(scope="module")
def archive_content() -> dict:
    """Appel réel unique de l'endpoint public partner archive_content, partagé entre les steps."""
    env = get_env()
    base = env["staging_base_url"].rstrip("/")
    url = (
        f"{base}/api/salesdata/v2/{env['installation_id']}/archive_content"
        f"?apiuser_email={env['apiuser_email']}"
        f"&apiuser_token={env['apiuser_token']}"
        f"&sequential_id={env['sequential_id']}"
    )
    response = httpx.get(url, timeout=60)
    assert response.status_code == 200, (
        f"Statut inattendu: {response.status_code}\n{response.text[:500]}"
    )
    data = response.json()
    assert data.get("succeeded") is True, f"succeeded != true : {data.get('succeeded')}"
    assert isinstance(data.get("data", {}).get("receipts"), list), "data.receipts absent ou non-liste"
    return data


def _receipts(archive_content: dict) -> list[dict]:
    return archive_content["data"]["receipts"]


def test_01_endpoint_reachable_and_ok(archive_content):
    """L'endpoint public partner répond 200 et renvoie une liste de receipts (criterion 6)."""
    receipts = _receipts(archive_content)
    assert len(receipts) > 0, "Aucun receipt dans l'archive"


def test_02_external_loyalty_present_for_receipts_with_loyalty(archive_content):
    """Au moins un receipt porte external_loyalty (criterion 1)."""
    with_el = [r for r in _receipts(archive_content) if "external_loyalty" in r]
    assert len(with_el) > 0, "Aucun receipt ne porte external_loyalty"


def test_03_external_loyalty_is_parsed_object_never_string(archive_content):
    """external_loyalty est un objet JSON parsé, jamais une string brute (criterion 2)."""
    values = [
        r["external_loyalty"]
        for r in _receipts(archive_content)
        if r.get("external_loyalty") is not None
    ]
    assert values, "Aucune valeur external_loyalty non-null à vérifier"
    assert all(isinstance(v, dict) for v in values), "external_loyalty non-objet détecté"
    assert not any(isinstance(v, str) for v in values), "external_loyalty string brute détectée"


def test_04_empty_handling_is_omission_not_null(archive_content):
    """Sans loyalty : clé omise, jamais null explicite (criterion 4 — décision omit)."""
    receipts = _receipts(archive_content)
    explicit_null = [
        r for r in receipts if "external_loyalty" in r and r["external_loyalty"] is None
    ]
    omitted = [r for r in receipts if "external_loyalty" not in r]
    assert not explicit_null, f"{len(explicit_null)} receipt(s) avec external_loyalty=null explicite"
    assert len(omitted) > 0, "Aucun receipt sans external_loyalty — omission non observée"


def test_05_external_loyalty_at_receipt_root_beside_siblings(archive_content):
    """external_loyalty est au niveau racine du receipt, sibling de payments/items/taxes (criterion 5)."""
    receipt = next(
        (r for r in _receipts(archive_content) if r.get("external_loyalty") is not None),
        None,
    )
    assert receipt is not None
    for sibling in ("payments", "items", "taxes"):
        assert sibling in receipt, f"clé sibling attendue absente au niveau receipt : {sibling}"
    assert "external_loyalty" in receipt


def test_06_verbatim_passthrough_golden_anchor(archive_content):
    """Passthrough verbatim : l'objet external_loyalty de l'ancre est reproduit à l'identique (criterion 3)."""
    anchor = next(
        (
            r
            for r in _receipts(archive_content)
            if r.get("sequential_id") == ANCHOR_SEQUENTIAL_ID
        ),
        None,
    )
    assert anchor is not None, f"Receipt ancre {ANCHOR_SEQUENTIAL_ID} introuvable dans l'archive"
    assert anchor.get("external_loyalty") == ANCHOR_EXTERNAL_LOYALTY, (
        "external_loyalty de l'ancre diffère du golden (passthrough non verbatim)\n"
        f"observé : {anchor.get('external_loyalty')}"
    )
