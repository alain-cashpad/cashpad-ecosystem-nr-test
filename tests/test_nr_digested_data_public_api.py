from __future__ import annotations

"""
Test de non-régression — API analytics publique (digested-data), ce que voient les clients

Les chiffres de SUMBOARD et des dashboards, comparés à une source INDÉPENDANTE plutôt
que figés : le BO (Partner API salesdata), ou l'API elle-même interrogée autrement.

    analytics   GET {base}/p/digested-data/public/1/site/<site>/{sales|payments|orders}
    BO          GET {base}/api/salesdata/v2/{INSTALLATION_ID}/products_summary?sequential_id=<seq>
                GET {base}/api/salesdata/v2/{INSTALLATION_ID}/archive_content?sequential_id=<seq>

LECTURE SEULE : que des GET, aucun ticket. Le CA et la TVA par archive sont dans
test_nr_salesdata_revenue_reconciliation ; ici, le détail.

| Test | Règle |
|---|---|
| test_01 | ventes par produit (`sales`, customAggregate=product) = `products_summary` du BO : quantité et CA TTC |
| test_02 | paiements par moyen (`payments`, customAggregate=method) = paiements des tickets non annulés d'`archive_content` : nombre et montant |
| test_03 | `top=N` sur `sales` = les N premiers de la liste complète, par QUANTITÉ décroissante |
| test_04 | `samePeriodLastYear` sur une période = la même requête posée directement un an plus tôt (orders, payments, sales) |

## Convention des menus (test_01)

Le BO et l'analytics ne rangent pas le prix d'un menu au même endroit. Dans
`products_summary`, la ligne du menu (`Big Boss`) porte son prix dans `menu` mais PAS
dans `total`, et ses composants (Capri-sun, Glace Push Up…) en portent une part dans
`total` = `carte` + `menu`. L'analytics laisse tout le prix sur la ligne du menu, les
composants à 0 €. Règle : analytics = `carte` + `menu` si la ligne est un menu (son
`menu` n'est pas compté dans son `total`), sinon `carte`. Mesuré le 2026-10-02 sur le
staging, archives 412 → 423 : 34 produits sur 34, et les 10 composants du BO font
1 118,70 €, le prix du `Big Boss` côté analytics.

Flag du site : 4652 a `useMenuTaxDistribution: true` (`spaces.sites.config`). Dans le
code lu le 2026-10-02 (checkout local, pas forcément la version déployée), seul `check`
le lit (`partner-payment-serializer.ts`, champs « valeur du menu ») ; `products_summary`
répartit à partir de `finalTaxDistribution`, que worker-digested-data calcule toujours,
et l'analytics ne le lit pas. La règle ci-dessus ne devrait donc pas en dépendre : NON
vérifié avec le flag à false. Sur un autre site, relever ce flag avant de conclure.

## Périmètres figés (staging, cashpad-8007, site 4652)

- archives `ARCHIVES` (412 → 423, closes) : 34 produits, 5 moyens de paiement (CB 46 /
  1 893,01 €, Espèces 25 / 391,30 €, Carte TR, Deliveroo, TIP 4 / -6,00 €).
- septembre 2026 comparé à septembre 2025 (23 archives en 2025-09) : 398 tickets et
  5 322,75 € en 2025. Le libellé `filters.time` du service dit « du 1 sept. 2025 au
  29 sept. 2025 » pour un cpTo au 30 : non tranché (affichage ou borne exclusive ?), le
  test compare les données, pas le libellé.

Observé VERT le 2026-10-02 sur le staging. En préprod, les périmètres sont à revoir
(autre site_id, autres archives).

Lancer :
    uv run --with pytest --with httpx --with python-dotenv \
      pytest tests/test_nr_digested_data_public_api.py -v
"""

import collections

import pytest
from dotenv import load_dotenv

load_dotenv()

from _nr import archive_range, digested_data, salesdata

ARCHIVES = (412, 423)
MONEY = 1000  # millièmes d'euro côté BO
TOL = 0.011  # € : l'analytics stocke des décimales, le BO des entiers
TOP = 5
BASE_PERIOD = ("2026-09-01", "2026-09-30")
YEAR_BEFORE = ("2025-09-01", "2025-09-30")


def archives():
    return range(ARCHIVES[0], ARCHIVES[1] + 1)


def by_name(rows: list[dict], name: str, fields: tuple[str, ...], cast=float) -> dict:
    return {r[name].strip(): tuple(cast(r.get(f) or 0) for f in fields) for r in rows}


def time_range(period: tuple[str, str]) -> list[tuple[str, str]]:
    return [("computedTimeRanges[cpType]", "timeRanges"), ("computedTimeRanges[timezone]", "Europe/Paris"),
            ("computedTimeRanges[cpFrom]", period[0]), ("computedTimeRanges[cpTo]", period[1])]


def same_period_last_year(period: tuple[str, str]) -> list[tuple[str, str]]:
    # cpRelative porte la TRANSFORMATION, cpParent la période de base (skill bov2-digested-data :
    # dans l'autre sens, 500 « Cannot destructure property 'from' »).
    return [("computedTimeRanges[cpType]", "timeRanges"), ("computedTimeRanges[timezone]", "Europe/Paris"),
            ("computedTimeRanges[cpRelative]", "samePeriodLastYear"),
            ("computedTimeRanges[cpParent][cpFrom]", period[0]), ("computedTimeRanges[cpParent][cpTo]", period[1])]


def gaps(bo: dict, analytics: dict, labels: tuple[str, str], tolerances: tuple[float, float]) -> list[str]:
    out = []
    for key in sorted(set(bo) | set(analytics)):
        b, a = bo.get(key), analytics.get(key)
        if b is None or a is None:
            out.append(f"{key} : présent d'un seul côté (BO {b}, analytics {a})")
            continue
        for label, tol, x, y in zip(labels, tolerances, b, a):
            if abs(x - y) > tol:
                out.append(f"{key} : {label} BO {x:.2f} ≠ analytics {y:.2f}")
    return out


def test_01_sales_per_product_match_the_bo():
    bo = collections.defaultdict(lambda: [0.0, 0.0])
    for seq in archives():
        for p in (salesdata("products_summary", sequential_id=seq).get("total_sales") or {}).get("products") or []:
            total, menu, carte = p["total"], p["menu"], p["carte"]
            is_menu = total["sales_incl_taxes"] != carte["sales_incl_taxes"] + menu["sales_incl_taxes"]
            line = bo[p["product"]["name"].strip()]
            line[0] += total["quantity"] / MONEY
            line[1] += (carte["sales_incl_taxes"] + (menu["sales_incl_taxes"] if is_menu else 0)) / MONEY
    assert bo, f"aucun produit dans le BO sur les archives {ARCHIVES}"
    rows = digested_data("sales", archive_range(*ARCHIVES) + [("customAggregate[0]", "product"), ("limit", "50")])
    analytics = by_name(rows, "productName", ("totalItems", "finalAmountWithTax"))
    diffs = gaps({k: tuple(v) for k, v in bo.items()}, analytics, ("quantité", "CA TTC"), (1e-6, TOL))
    assert not diffs, "\n".join(diffs)


def test_02_payments_per_method_match_the_bo():
    bo = collections.defaultdict(lambda: [0, 0.0])
    for seq in archives():
        for receipt in salesdata("archive_content", sequential_id=seq).get("receipts") or []:
            if receipt.get("cancelled"):
                continue
            for payment in receipt.get("payments") or []:
                line = bo[payment["paymentmethod"]["name"].strip()]
                line[0] += 1
                line[1] += payment["amount"] / MONEY
    assert bo, f"aucun paiement dans le BO sur les archives {ARCHIVES}"
    rows = digested_data("payments", archive_range(*ARCHIVES) + [("customAggregate[0]", "method"), ("limit", "50")])
    analytics = by_name(rows, "paymentMethodName", ("totalPayments", "amountWithTax"))
    diffs = gaps({k: tuple(v) for k, v in bo.items()}, analytics, ("nombre", "montant"), (0, TOL))
    assert not diffs, "\n".join(diffs)


def test_03_top_products_are_the_best_sellers_by_quantity():
    params = archive_range(*ARCHIVES) + [("customAggregate[0]", "product"), ("limit", "50")]
    full = digested_data("sales", params)
    top = digested_data("sales", params + [("top", str(TOP))])
    expected = sorted(full, key=lambda r: -float(r["totalItems"]))[:TOP]
    quantities = [float(r["totalItems"]) for r in expected]
    assert len(set(quantities)) == TOP, f"ex aequo dans le top {TOP} ({quantities}) : périmètre à changer"
    assert [r["productName"] for r in top] == [r["productName"] for r in expected], (
        f"top {TOP} : {[(r['productName'], r['totalItems']) for r in top]}, "
        f"attendu {[(r['productName'], r['totalItems']) for r in expected]}"
    )


@pytest.mark.parametrize("resource, aggregate", [
    ("orders", [("customAggregate[0]", "site")]),
    ("payments", [("customAggregate[0]", "method"), ("limit", "50")]),
    ("sales", [("customAggregate[0]", "product"), ("limit", "50")]),
])
def test_04_same_period_last_year_equals_the_direct_query(resource, aggregate):
    direct = digested_data(resource, time_range(YEAR_BEFORE) + aggregate)
    compared = digested_data(resource, same_period_last_year(BASE_PERIOD) + aggregate)
    assert direct, f"{resource} : aucune donnée sur {YEAR_BEFORE}, la comparaison ne prouverait rien"
    assert compared == direct, (
        f"{resource} : samePeriodLastYear({BASE_PERIOD}) ≠ requête directe {YEAR_BEFORE} "
        f"({len(compared)} lignes contre {len(direct)})"
    )
