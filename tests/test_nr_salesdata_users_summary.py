from __future__ import annotations

"""
Test de non-régression — salesdata `users_summary` (ventes par vendeur d'une archive)

    GET {base}/api/salesdata/v2/{INSTALLATION_ID}/users_summary?sequential_id=<seq>

LECTURE SEULE. Périmètre : les 12 dernières archives du BO.

| Test | Règle |
|---|---|
| test_01 | enveloppe v2.17 ; `id` et dates = ceux d'`archives` |
| test_02 | `total_sales` = `total_sales` de `sales_summary` (TTC, HT, tickets, couverts) |
| test_03 | Σ des lignes par vendeur = `total_sales` |
| test_04 | vendeurs de `users_summary` = propriétaires (`owner`) des tickets non annulés d'`archive_content`, avec le même CA chacun |
| test_05 | erreurs d'entrée : `AnyRequired`, `NumberBase`, archive inconnue → 400 |
| test_06 | mauvais token → 404 |

⚠️ Archive inconnue : 400 « internal communication error » avec la stack trace du serveur
(`sales_summary` dit « Archive not found ») — relevé le 2026-10-02, non figé.
Sur le staging, un seul vendeur (« Administrateur ») sur tout le périmètre : test_04 ne
discrimine pas plusieurs vendeurs. Observé VERT le 2026-10-02 (412 → 423).
"""

import collections

import pytest
from dotenv import load_dotenv

load_dotenv()

from _salesdata import assert_input_errors, assert_wrong_token_refused, by_seq, data, scope

FIELDS = ("sales_incl_taxes", "sales_excl_taxes", "nb_receipts", "nb_seats")


@pytest.fixture(scope="module")
def summaries() -> dict[int, dict]:
    return {seq: data("users_summary", sequential_id=seq) for seq in scope()}


def test_01_archive_matches_the_list(summaries):
    listed = by_seq()
    diffs = [seq for seq, s in summaries.items()
             if (s.get("id"), s.get("range_begin_date"), s.get("range_end_date"))
             != (listed[seq]["id"], listed[seq]["range_begin_date"], listed[seq]["range_end_date"])]
    assert not diffs, f"users_summary ≠ archives sur {diffs}"


def test_02_total_matches_sales_summary(summaries):
    diffs = []
    for seq, s in summaries.items():
        sales = data("sales_summary", sequential_id=seq)["total_sales"]
        got, expected = tuple(s["total_sales"].get(f) for f in FIELDS), tuple(sales.get(f) for f in FIELDS)
        if got != expected:
            diffs.append(f"{seq} : {FIELDS} {got} ≠ sales_summary {expected}")
    assert not diffs, "\n".join(diffs)


def test_03_users_add_up_to_the_total(summaries):
    diffs = []
    for seq, s in summaries.items():
        for field in FIELDS:
            lines = sum(u.get(field) or 0 for u in s.get("sales") or [])
            if lines != s["total_sales"].get(field):
                diffs.append(f"{seq} : {field} Σ vendeurs {lines} ≠ total {s['total_sales'].get(field)}")
    assert not diffs, "\n".join(diffs)


def test_04_users_are_the_receipt_owners(summaries):
    diffs = []
    for seq, s in summaries.items():
        owners = collections.Counter()
        for r in data("archive_content", sequential_id=seq).get("receipts") or []:
            if not r.get("cancelled"):
                owners[(r.get("owner") or {}).get("id", "").lower()] += r["total_with_taxes"]
        users = {(u.get("user") or {}).get("id", "").lower(): u["sales_incl_taxes"] for u in s.get("sales") or []}
        if users != dict(owners):
            diffs.append(f"{seq} : vendeurs {users} ≠ propriétaires des tickets {dict(owners)}")
    assert not diffs, "\n".join(diffs)


def test_05_input_errors():
    assert_input_errors("users_summary", unknown_message=None)


def test_06_wrong_token_is_refused():
    assert_wrong_token_refused("users_summary", sequential_id=scope()[-1])
