from __future__ import annotations

"""
Test de non-régression — salesdata `products_summary` (ventes par produit d'une archive)

    GET {base}/api/salesdata/v2/{INSTALLATION_ID}/products_summary?sequential_id=<seq>

LECTURE SEULE. Périmètre : les 12 dernières archives du BO. La comparaison avec
l'analytics (et la convention des menus) est dans test_nr_digested_data_public_api.

| Test | Règle |
|---|---|
| test_00 | structure : aucun champ figé (`schemas/salesdata/products_summary.json`) ne disparaît ni ne change de type ; un champ nouveau est seulement affiché |
| test_01 | enveloppe v2.17 ; `id` et dates = ceux d'`archives` |
| test_02 | `total_incl_taxes` / `total_excl_taxes` = TTC / HT de `sales_summary` |
| test_03 | Σ des `total` produits = `total_incl_taxes`, à `TOL` près (arrondis de la répartition des menus : 5 millièmes au plus) |
| test_04 | `nb_products` = Σ des quantités (millièmes) |
| test_05 | chaque produit : quantité `total` = `carte` + `menu` ; CA `total` = `carte` + `menu`, sauf la ligne d'un menu (`total` = `carte`, le prix du menu étant réparti sur ses composants) |
| test_06 | erreurs d'entrée : `AnyRequired`, `NumberBase`, archive inconnue → 400 « Archive not found » |
| test_07 | mauvais token → 404 |

Observé VERT le 2026-10-02 sur le staging (412 → 423).
"""

import pytest
from dotenv import load_dotenv

load_dotenv()

from _salesdata import TOL, assert_fields, assert_input_errors, assert_wrong_token_refused, by_seq, data, scope


@pytest.fixture(scope="module")
def summaries() -> dict[int, dict]:
    return {seq: data("products_summary", sequential_id=seq) for seq in scope()}


def test_00_fields():
    assert_fields("products_summary")


def test_01_archive_matches_the_list(summaries):
    listed = by_seq()
    diffs = [seq for seq, s in summaries.items()
             if (s.get("id"), s.get("range_begin_date"), s.get("range_end_date"))
             != (listed[seq]["id"], listed[seq]["range_begin_date"], listed[seq]["range_end_date"])]
    assert not diffs, f"products_summary ≠ archives sur {diffs}"


def test_02_total_matches_sales_summary(summaries):
    diffs = []
    for seq, s in summaries.items():
        sales = data("sales_summary", sequential_id=seq)["total_sales"]
        got = (s["total_sales"]["total_incl_taxes"], s["total_sales"]["total_excl_taxes"])
        if got != (sales["sales_incl_taxes"], sales["sales_excl_taxes"]):
            diffs.append(f"{seq} : (TTC, HT) {got} ≠ sales_summary {(sales['sales_incl_taxes'], sales['sales_excl_taxes'])}")
    assert not diffs, "\n".join(diffs)


def test_03_products_add_up_to_the_total(summaries):
    diffs = []
    for seq, s in summaries.items():
        lines = sum(p["total"]["sales_incl_taxes"] for p in s["total_sales"].get("products") or [])
        if abs(lines - s["total_sales"]["total_incl_taxes"]) > TOL:
            diffs.append(f"{seq} : Σ produits {lines} ≠ total {s['total_sales']['total_incl_taxes']}")
    assert not diffs, "\n".join(diffs)


def test_04_nb_products_is_the_sum_of_quantities(summaries):
    diffs = [f"{seq} : nb_products {s['total_sales']['nb_products']} ≠ Σ quantités "
             f"{sum(p['total']['quantity'] for p in s['total_sales'].get('products') or [])}"
             for seq, s in summaries.items()
             if s["total_sales"]["nb_products"] != sum(p["total"]["quantity"] for p in s["total_sales"].get("products") or [])]
    assert not diffs, "\n".join(diffs)


def test_05_total_is_carte_plus_menu(summaries):
    diffs = []
    for seq, s in summaries.items():
        for p in s["total_sales"].get("products") or []:
            total, carte, menu, name = p["total"], p["carte"], p["menu"], p["product"]["name"]
            if total["quantity"] != carte["quantity"] + menu["quantity"]:
                diffs.append(f"{seq} {name} : quantité {total['quantity']} ≠ carte {carte['quantity']} + menu {menu['quantity']}")
            if total["sales_incl_taxes"] not in (carte["sales_incl_taxes"] + menu["sales_incl_taxes"], carte["sales_incl_taxes"]):
                diffs.append(f"{seq} {name} : CA {total['sales_incl_taxes']} ni carte + menu "
                             f"({carte['sales_incl_taxes']} + {menu['sales_incl_taxes']}) ni carte")
    assert not diffs, "\n".join(diffs[:10])


def test_06_input_errors():
    assert_input_errors("products_summary", unknown_message="Archive not found")


def test_07_wrong_token_is_refused():
    assert_wrong_token_refused("products_summary", sequential_id=scope()[-1])
