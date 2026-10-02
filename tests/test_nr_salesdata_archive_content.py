from __future__ import annotations

"""
Test de non-régression — salesdata `archive_content` (contenu complet d'une archive)

    GET {base}/api/salesdata/v2/{INSTALLATION_ID}/archive_content?sequential_id=<seq>
    GET http://<CASHPAD_ID>.vpn.osilia.com:9091/reports/get_archive_content?id=<seq>   (oracle)

LECTURE SEULE. Périmètre : les 12 dernières archives du BO. Les champs propres à un
ticket (loyalty, customer, delivery_id) ont leurs tests : 2121, 2203, 2223.

| Test | Règle |
|---|---|
| test_01 | enveloppe v2.15 (une version derrière les autres actions) ; `id` et dates = ceux d'`archives` |
| test_02 | `total` (TTC, nb_receipts, nb_cancelled_receipts) = somme des tickets |
| test_03 | chaque ticket non annulé : Σ paiements = `total_with_taxes` |
| test_04 | `payments` de l'archive (par moyen, nb_operations) = paiements des tickets non annulés |
| test_05 | tickets du BO = tickets de la caisse : mêmes id, sequential_id, montant, annulation (VPN) |
| test_06 | erreurs d'entrée : sans sequential_id, non entier, archive inconnue → 400 (jamais 500) |
| test_07 | mauvais token → 404 |

⚠️ Relevé le 2026-10-02, non figé (le test ne fige que le 400) : archive_content ne valide
AUCUN paramètre — absent, non entier ou inconnu, tout répond 400 « internal communication
error », avec la stack trace du serveur dans `data.backtrace` ; les autres actions
répondent `AnyRequired` / `NumberBase`.
Observé VERT le 2026-10-02 sur le staging (412 → 423).
"""

import collections

import pytest
from dotenv import load_dotenv

load_dotenv()

from _salesdata import assert_input_errors, assert_wrong_token_refused, by_seq, data, device, scope


@pytest.fixture(scope="module")
def contents() -> dict[int, dict]:
    return {seq: data("archive_content", sequential_id=seq) for seq in scope()}


def kept(content: dict) -> list[dict]:
    return [r for r in content.get("receipts") or [] if not r.get("cancelled")]


def test_01_archive_matches_the_list(contents):
    listed = by_seq()
    diffs = [f"{seq} : {c.get('id')} {c.get('range_begin_date')}→{c.get('range_end_date')}"
             for seq, c in contents.items()
             if (c.get("sequential_id"), c.get("id"), c.get("range_begin_date"), c.get("range_end_date"))
             != (seq, listed[seq]["id"], listed[seq]["range_begin_date"], listed[seq]["range_end_date"])]
    assert not diffs, "archive_content ≠ archives :\n" + "\n".join(diffs)


def test_02_total_is_the_sum_of_receipts(contents):
    diffs = []
    for seq, c in contents.items():
        total = c.get("total") or {}
        cancelled = sum(1 for r in c.get("receipts") or [] if r.get("cancelled"))
        got = (total.get("total_with_taxes"), total.get("nb_receipts"), total.get("nb_cancelled_receipts"))
        expected = (sum(r["total_with_taxes"] for r in kept(c)), len(kept(c)), cancelled)
        if got != expected:
            diffs.append(f"{seq} : total (TTC, tickets, annulés) {got} ≠ Σ tickets {expected}")
    assert not diffs, "\n".join(diffs)


def test_03_each_receipt_is_fully_paid(contents):
    diffs = [f"{seq} ticket {r['sequential_id']} : Σ paiements {sum(p['amount'] for p in r.get('payments') or [])} "
             f"≠ total {r['total_with_taxes']}"
             for seq, c in contents.items() for r in kept(c)
             if sum(p["amount"] for p in r.get("payments") or []) != r["total_with_taxes"]]
    assert not diffs, "\n".join(diffs[:10])


def test_04_archive_payments_are_the_receipt_payments(contents):
    diffs = []
    for seq, c in contents.items():
        expected = collections.defaultdict(lambda: [0, 0])
        for r in kept(c):
            for p in r.get("payments") or []:
                line = expected[p["paymentmethod"]["id"].upper()]
                line[0] += p["amount"]
                line[1] += 1
        got = {p["paymentmethod"]["id"].upper(): [p["amount"], p["nb_operations"]] for p in c.get("payments") or []}
        if got != dict(expected):
            diffs.append(f"{seq} : payments {got} ≠ paiements des tickets {dict(expected)}")
    assert not diffs, "\n".join(diffs)


def test_05_receipts_match_the_pos(contents):
    diffs = []
    for seq, c in contents.items():
        pos = (device(f"reports/get_archive_content?id={seq}").get("archive") or {}).get("receipts") or []
        bo = {r["id"].lower(): (r["sequential_id"], r["total_with_taxes"], bool(r.get("cancelled")))
              for r in c.get("receipts") or []}
        device_rows = {r["id"].lower(): (r["sequentialId"], r["amountTotal"], bool(r.get("cancelled"))) for r in pos}
        if bo != device_rows:
            only = sorted(set(bo) ^ set(device_rows))[:3]
            changed = [k for k in set(bo) & set(device_rows) if bo[k] != device_rows[k]][:3]
            diffs.append(f"{seq} : {len(bo)} tickets BO / {len(device_rows)} caisse, d'un seul côté {only}, "
                         f"différents {[(k, bo[k], device_rows[k]) for k in changed]}")
    assert not diffs, "\n".join(diffs)


def test_06_input_errors():
    assert_input_errors("archive_content", unknown_message=None, validates_input=False)


def test_07_wrong_token_is_refused():
    assert_wrong_token_refused("archive_content", sequential_id=scope()[-1])
