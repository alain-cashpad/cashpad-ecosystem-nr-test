from __future__ import annotations

"""
Test de non-régression — salesdata `cashcontainers` (fonds de caisse d'une archive)

    GET {base}/api/salesdata/v2/{INSTALLATION_ID}/cashcontainers?sequential_id=<seq>

LECTURE SEULE. Périmètre : les 12 dernières archives du BO.

| Test | Règle |
|---|---|
| test_01 | enveloppe v2.17 ; `archive.id` / `archive.sequential_id` = ceux d'`archives` |
| test_02 | chaque session : `amount_total` = Σ de son `summary` par moyen de paiement |
| test_03 | Σ `summary` par moyen (toutes sessions) = paiements des tickets non annulés + mouvements de caisse (`cashmovements`) d'`archive_content` |
| test_04 | mouvements des sessions (`movements`) = `cashmovements` d'`archive_content`, par moyen |
| test_05 | erreurs d'entrée : `AnyRequired`, `NumberBase`, archive inconnue → 400 |
| test_06 | mauvais token → 404 |

Mesuré le 2026-10-02 (archive 420) : CB 691,60 € = 661,60 € de paiements + 30,00 € de
mouvements ; TR 5,00 € = mouvement seul ; TIP -6,00 €.
⚠️ Archive inconnue : 400 « internal communication error » avec la stack trace du serveur
— relevé le 2026-10-02, non figé. Observé VERT le 2026-10-02 sur le staging (412 → 423).
"""

import collections

import pytest
from dotenv import load_dotenv

load_dotenv()

from _salesdata import assert_input_errors, assert_wrong_token_refused, by_seq, data, scope


@pytest.fixture(scope="module")
def containers() -> dict[int, dict]:
    return {seq: data("cashcontainers", sequential_id=seq) for seq in scope()}


def sessions(c: dict) -> list[dict]:
    return [s for container in c.get("cashcontainers") or [] for s in container.get("sessions") or []]


def per_method(rows, amount="amount_total") -> dict[str, int]:
    out = collections.Counter()
    for r in rows:
        out[(r.get("method") or r.get("paymentmethod"))["id"].upper()] += r.get(amount) or 0
    return {k: v for k, v in out.items() if v}


def test_01_archive_matches_the_list(containers):
    listed = by_seq()
    diffs = [seq for seq, c in containers.items()
             if ((c.get("archive") or {}).get("id"), (c.get("archive") or {}).get("sequential_id"))
             != (listed[seq]["id"], seq)]
    assert not diffs, f"cashcontainers ≠ archives sur {diffs}"


def test_02_session_total_is_its_summary(containers):
    diffs = [f"{seq} session {s.get('date_opened')} : amount_total {s['amount_total']} ≠ Σ summary "
             f"{sum(x['amount_total'] for x in s.get('summary') or [])}"
             for seq, c in containers.items() for s in sessions(c)
             if s["amount_total"] != sum(x["amount_total"] for x in s.get("summary") or [])]
    assert not diffs, "\n".join(diffs)


def test_03_summary_is_payments_plus_movements(containers):
    diffs = []
    for seq, c in containers.items():
        content = data("archive_content", sequential_id=seq)
        expected = collections.Counter(per_method(
            [p for r in content.get("receipts") or [] if not r.get("cancelled") for p in r.get("payments") or []], "amount"))
        expected.update(per_method(content.get("cashmovements") or [], "amount"))
        got = per_method([x for s in sessions(c) for x in s.get("summary") or []])
        if got != {k: v for k, v in expected.items() if v}:
            diffs.append(f"{seq} : summary {got} ≠ paiements + mouvements {dict(expected)}")
    assert not diffs, "\n".join(diffs)


def test_04_movements_are_the_archive_cash_movements(containers):
    diffs = []
    for seq, c in containers.items():
        got = per_method([m for s in sessions(c) for m in s.get("movements") or []])
        expected = per_method(data("archive_content", sequential_id=seq).get("cashmovements") or [], "amount")
        if got != expected:
            diffs.append(f"{seq} : movements {got} ≠ cashmovements {expected}")
    assert not diffs, "\n".join(diffs)


def test_05_input_errors():
    assert_input_errors("cashcontainers", unknown_message=None)


def test_06_wrong_token_is_refused():
    assert_wrong_token_refused("cashcontainers", sequential_id=scope()[-1])
