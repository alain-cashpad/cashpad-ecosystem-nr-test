from __future__ import annotations

"""
Test de non-régression — salesdata `sales_summary` (CA d'une archive)

    GET {base}/api/salesdata/v2/{INSTALLATION_ID}/sales_summary?sequential_id=<seq>
    GET http://<CASHPAD_ID>.vpn.osilia.com:9091/reports/get_archive_content?id=<seq>   (oracle)

LECTURE SEULE. Périmètre : les 12 dernières archives du BO. La comparaison avec
l'analytics est dans test_nr_salesdata_revenue_reconciliation.

| Test | Règle |
|---|---|
| test_01 | enveloppe v2.17 ; `id` et dates = ceux d'`archives` |
| test_02 | `total_sales` = Σ des lignes `sales` (TTC, HT, tickets, couverts) |
| test_03 | TVA : Σ `total_with_taxes` = TTC, Σ `total_without_taxes` = HT, Σ `amount` = TTC − HT |
| test_04 | TTC et nb de tickets = ceux d'`archive_content` |
| test_05 | TTC et HT = `salesInclTaxes` / `salesExclTaxes` de la caisse (VPN) |
| test_06 | erreurs d'entrée : `AnyRequired`, `NumberBase`, archive inconnue → 400 « Archive not found » |
| test_07 | mauvais token → 404 |

`nb_products` est une CHAÎNE (`"1.0"`), pas des millièmes (skill bov2-partners-api) : non
comparé. Observé VERT le 2026-10-02 sur le staging (412 → 423).
"""

import pytest
from dotenv import load_dotenv

load_dotenv()

from _salesdata import TOL, assert_input_errors, assert_wrong_token_refused, by_seq, data, device, scope

FIELDS = ("sales_incl_taxes", "sales_excl_taxes", "nb_receipts", "nb_seats")


@pytest.fixture(scope="module")
def summaries() -> dict[int, dict]:
    return {seq: data("sales_summary", sequential_id=seq) for seq in scope()}


def test_01_archive_matches_the_list(summaries):
    listed = by_seq()
    diffs = [seq for seq, s in summaries.items()
             if (s.get("id"), s.get("range_begin_date"), s.get("range_end_date"))
             != (listed[seq]["id"], listed[seq]["range_begin_date"], listed[seq]["range_end_date"])]
    assert not diffs, f"sales_summary ≠ archives sur {diffs}"


def test_02_total_is_the_sum_of_the_lines(summaries):
    diffs = []
    for seq, s in summaries.items():
        total = s["total_sales"]
        for field in FIELDS:
            lines = sum(row.get(field) or 0 for row in s.get("sales") or [])
            if lines != total.get(field):
                diffs.append(f"{seq} : {field} total {total.get(field)} ≠ Σ lignes {lines}")
    assert not diffs, "\n".join(diffs)


def test_03_vat_adds_up(summaries):
    diffs = []
    for seq, s in summaries.items():
        t = s["total_sales"]
        taxes = t.get("taxes") or []
        ttc, ht = sum(x["total_with_taxes"] for x in taxes), sum(x["total_without_taxes"] for x in taxes)
        vat = sum(x["amount"] for x in taxes)
        if abs(ttc - t["sales_incl_taxes"]) > TOL or abs(ht - t["sales_excl_taxes"]) > TOL \
                or abs(vat - (t["sales_incl_taxes"] - t["sales_excl_taxes"])) > TOL:
            diffs.append(f"{seq} : TVA Σ TTC {ttc} / HT {ht} / TVA {vat} ≠ total {t['sales_incl_taxes']} / {t['sales_excl_taxes']}")
    assert not diffs, "\n".join(diffs)


def test_04_matches_archive_content(summaries):
    diffs = []
    for seq, s in summaries.items():
        total = data("archive_content", sequential_id=seq)["total"]
        got = (s["total_sales"]["sales_incl_taxes"], s["total_sales"]["nb_receipts"])
        if got != (total["total_with_taxes"], total["nb_receipts"]):
            diffs.append(f"{seq} : (TTC, tickets) {got} ≠ archive_content {(total['total_with_taxes'], total['nb_receipts'])}")
    assert not diffs, "\n".join(diffs)


def test_05_matches_the_pos(summaries):
    diffs = []
    for seq, s in summaries.items():
        pos = device(f"reports/get_archive_content?id={seq}").get("archive") or {}
        got = (s["total_sales"]["sales_incl_taxes"], s["total_sales"]["sales_excl_taxes"])
        if got != (pos.get("salesInclTaxes"), pos.get("salesExclTaxes")):
            diffs.append(f"{seq} : (TTC, HT) BO {got} ≠ caisse {(pos.get('salesInclTaxes'), pos.get('salesExclTaxes'))}")
    assert not diffs, "\n".join(diffs)


def test_06_input_errors():
    assert_input_errors("sales_summary", unknown_message="Archive not found")


def test_07_wrong_token_is_refused():
    assert_wrong_token_refused("sales_summary", sequential_id=scope()[-1])
