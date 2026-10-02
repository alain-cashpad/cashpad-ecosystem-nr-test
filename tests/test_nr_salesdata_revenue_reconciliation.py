from __future__ import annotations

"""
Test de non-régression — chaîne caisse → back-office → analytics, archive par archive

Le chemin des chiffres que voient les clients : l'archive fiscale de la caisse est
synchronisée dans le BO (worker-sync), puis digérée pour l'analytics (worker-digested-data,
le service en cause le 2026-10-01). Les trois niveaux partagent le `sequential_id` entier
de l'archive :

    caisse      GET http://<CASHPAD_ID>.vpn.osilia.com:9091/reports/get_archives?updated_since_version=0
                GET …/reports/get_archive_content?id=<seq>                     salesInclTaxes / salesExclTaxes
    BO          GET {base}/api/salesdata/v2/{INSTALLATION_ID}/archives
                GET {base}/api/salesdata/v2/{INSTALLATION_ID}/sales_summary?sequential_id=<seq>   total_sales
    analytics   GET {base}/p/digested-data/public/1/site/<site>/orders?…archiveRanges…&customAggregate[0]=archive
                GET {base}/p/digested-data/public/1/site/<site>/taxes?…archiveRanges…&priceType=withTax

LECTURE SEULE : que des GET, aucun ticket. Repris du skill bov2-revenue-reconciliation
(mêmes sources, mêmes échelles, mêmes tolérances).

## Ce qui est comparé (périmètre : les ARCHIVE_COUNT dernières archives du BO)

| Test | Règle | Ce qu'il attrape |
|---|---|---|
| test_01 | les dernières archives de la caisse sont toutes dans le BO | synchro des archives arrêtée |
| test_02 | caisse = BO (TTC, HT, nb de tickets non annulés) | archive mal synchronisée |
| test_03 | toute archive du BO avec des tickets est dans l'analytics | digest jamais exécuté |
| test_04 | BO = analytics (TTC, HT, nb de tickets) | digest faux ou partiel |
| test_05 | TVA par taux, BO = analytics, sur tout le périmètre | ventilation TVA fausse |

Échelles : caisse et BO en MILLIÈMES d'euro (7 € → 7000), analytics en euros décimaux.
C'est l'analytics, source indépendante, qui a révélé l'échelle (le skill lisait ×100 :
BO = 10 × analytics sur 10 archives sur 10). Un écart d'un facteur rond entre niveaux
est une échelle avant d'être un bug de synchro.
Tolérances : 0,01 € TTC et 0,02 € HT par archive (l'analytics recalcule le HT), 0,05 €
de TVA par taux sur le périmètre.

test_01 et test_02 exigent le VPN (skip sinon). L'analytics exige le jeton public
`envs.<cible>.token` de ~/.config/cashpad/digested-data.json (celui du skill
bov2-digested-data ; skip sinon).

Observé VERT le 2026-10-02 sur le staging (site 4652, archives 412 → 423, 2 352,01 € et
63 tickets sur les trois niveaux, TVA 10 % et 20 % alignées). Le même jour, plus tôt, le
skill avait trouvé les archives 422 et 423 absentes du BO (synchro du site arrêtée depuis
le 30/09 16:56) : test_01 aurait échoué.

Lancer :
    uv run --with pytest --with httpx --with python-dotenv \
      pytest tests/test_nr_salesdata_revenue_reconciliation.py -v
"""

import collections
import json
from pathlib import Path

import httpx
import pytest
from dotenv import load_dotenv

load_dotenv()

from _nr import TIMEOUT_S, device_base, partner_call, site
from _target import partner_env, target

ARCHIVE_COUNT = 12
MONEY = 1000  # millièmes d'euro, caisse et BO
TAX_RATE = 10  # dixièmes de % côté BO (100 → 10 %)
TOL_TTC, TOL_HT, TOL_VAT = 0.01, 0.02, 0.05
DD_CONFIG = Path.home() / ".config" / "cashpad" / "digested-data.json"


# ── BO (Partner API salesdata) ──

def bo_data(action: str, **params):
    status, payload = partner_call("salesdata", 2, action, params=params or None)
    assert status == 200, f"salesdata {action} {params} : HTTP {status} — {str(payload)[:300]}"
    return payload.get("data", payload) if isinstance(payload, dict) else payload


@pytest.fixture(scope="module")
def scope() -> list[int]:
    seqs = sorted(a["sequential_id"] for a in bo_data("archives") or [] if a.get("sequential_id") is not None)
    assert seqs, "aucune archive dans le BO"
    return seqs[-ARCHIVE_COUNT:]


@pytest.fixture(scope="module")
def bo(scope) -> dict:
    out = {}
    for seq in scope:
        t = (bo_data("sales_summary", sequential_id=seq) or {}).get("total_sales") or {}
        out[seq] = {
            "ttc": (t.get("sales_incl_taxes") or 0) / MONEY,
            "ht": (t.get("sales_excl_taxes") or 0) / MONEY,
            "receipts": t.get("nb_receipts") or 0,
            "taxes": {round((x.get("rate") or 0) / TAX_RATE, 1): {"ttc": (x.get("total_with_taxes") or 0) / MONEY,
                                                                 "vat": (x.get("amount") or 0) / MONEY}
                      for x in t.get("taxes") or []},
        }
    return out


# ── Caisse (VPN) ──

def device_get(path: str) -> dict:
    try:
        response = httpx.get(f"{device_base()}/{path}", timeout=TIMEOUT_S)
    except httpx.TransportError as exc:
        pytest.skip(f"caisse injoignable ({exc.__class__.__name__}) : VPN ?")
    assert response.status_code == 200, f"caisse {path} : HTTP {response.status_code}"
    return response.json()


@pytest.fixture(scope="module")
def pos_list() -> list[int]:
    archives = device_get("reports/get_archives?updated_since_version=0").get("archives") or []
    return sorted(a["sequentialId"] for a in archives if a.get("sequentialId") is not None)


@pytest.fixture(scope="module")
def pos(scope, pos_list) -> dict:
    out = {}
    for seq in (s for s in scope if s in pos_list):
        a = device_get(f"reports/get_archive_content?id={seq}").get("archive") or {}
        out[seq] = {"ttc": (a.get("salesInclTaxes") or 0) / MONEY, "ht": (a.get("salesExclTaxes") or 0) / MONEY,
                    "receipts": sum(1 for r in a.get("receipts") or [] if not r.get("cancelled"))}
    return out


# ── Analytics (digested-data public) ──

def dd_get(resource: str, lo: int, hi: int, extra: list[tuple[str, str]]) -> list[dict]:
    if not DD_CONFIG.exists():
        pytest.skip(f"{DD_CONFIG} absent — analytics non lisible")
    token = ((json.loads(DD_CONFIG.read_text()).get("envs") or {}).get(target()) or {}).get("token", "").strip()
    if not token:
        pytest.skip(f"pas de `envs.{target()}.token` dans {DD_CONFIG}")
    params = [("computedTimeRanges[cpType]", "archiveRanges"), ("computedTimeRanges[timezone]", "Europe/Paris"),
              ("computedTimeRanges[cpFrom]", str(lo)), ("computedTimeRanges[cpTo]", str(hi))] + extra
    url = f"{partner_env()['base_url']}/p/digested-data/public/1/site/{site()['site_id']}/{resource}"
    response = httpx.get(url, params=params, headers={"Authorization": f"Bearer {token.removeprefix('Bearer ')}"},
                         timeout=TIMEOUT_S)
    assert response.status_code == 200, f"digested-data {resource} : HTTP {response.status_code} — {response.text[:300]}"
    payload = response.json()
    return payload if isinstance(payload, list) else payload.get("data") or []


@pytest.fixture(scope="module")
def analytics(scope) -> dict:
    # customAggregate=archive ignore limit/skip : une page rend tout le périmètre (skill, 2026-10-02).
    rows = dd_get("orders", scope[0], scope[-1], [("customAggregate[0]", "archive"), ("limit", "50")])
    return {int(r["archiveSequentialId"]): {"ttc": float(r.get("finalAmountWithTax") or 0),
                                            "ht": float(r.get("finalAmountWithoutTax") or 0),
                                            "receipts": int(float(r.get("ordersCount") or 0))}
            for r in rows if r.get("archiveSequentialId") is not None}


def gaps(left: dict, right: dict, names: tuple[str, str]) -> list[str]:
    out = []
    for seq in sorted(set(left) & set(right)):
        a, b = left[seq], right[seq]
        if abs(a["ttc"] - b["ttc"]) > TOL_TTC:
            out.append(f"archive {seq} : TTC {names[0]} {a['ttc']:.2f} ≠ {names[1]} {b['ttc']:.2f}")
        elif abs(a["ht"] - b["ht"]) > TOL_HT:
            out.append(f"archive {seq} : HT {names[0]} {a['ht']:.2f} ≠ {names[1]} {b['ht']:.2f}")
        if a["receipts"] != b["receipts"]:
            out.append(f"archive {seq} : tickets {names[0]} {a['receipts']} ≠ {names[1]} {b['receipts']}")
    return out


def test_01_latest_pos_archives_are_synced_to_the_bo(pos_list, scope):
    latest = pos_list[-ARCHIVE_COUNT:]
    bo_seqs = set(s for a in bo_data("archives", start_sequential_id=latest[0]) or []
                  if (s := a.get("sequential_id")) is not None)
    missing = [s for s in latest if s not in bo_seqs]
    assert not missing, (
        f"archives de la caisse absentes du BO : {missing} (dernière du BO : {scope[-1]}) — synchro des archives "
        "arrêtée ? chercher `triggerPull` du site dans les logs sync-manager"
    )


def test_02_pos_and_bo_agree(pos, bo):
    assert pos, "aucune archive du périmètre n'est listée par la caisse"
    diffs = gaps(pos, bo, ("caisse", "BO"))
    assert not diffs, "\n".join(diffs)


def test_03_every_bo_archive_with_receipts_is_digested(bo, analytics):
    missing = [s for s, b in bo.items() if b["receipts"] and s not in analytics]
    assert not missing, f"archives du BO avec des tickets, absentes de l'analytics (digest jamais fait ?) : {missing}"


def test_04_bo_and_analytics_agree_per_archive(bo, analytics):
    diffs = gaps(bo, analytics, ("BO", "analytics"))
    assert not diffs, "\n".join(diffs)


def test_05_vat_per_rate_agrees(scope, bo):
    rows = dd_get("taxes", scope[0], scope[-1], [("priceType", "withTax"), ("limit", "50")])
    dd = collections.defaultdict(lambda: {"ttc": 0.0, "vat": 0.0})
    for r in rows:
        rate = round(float(r.get("percent") or 0), 1)
        dd[rate]["ttc"] += float(r.get("sumAmountTotal") or 0)
        dd[rate]["vat"] += float(r.get("sumAmountTaxes") or 0)
    bo_tax = collections.defaultdict(lambda: {"ttc": 0.0, "vat": 0.0})
    for archive in bo.values():
        for rate, t in archive["taxes"].items():
            bo_tax[rate]["ttc"] += t["ttc"]
            bo_tax[rate]["vat"] += t["vat"]
    diffs = []
    for rate in sorted(set(bo_tax) | set(dd)):
        b, d = bo_tax.get(rate), dd.get(rate)
        if not b or not d:
            diffs.append(f"TVA {rate} % : présente d'un seul côté (BO {b}, analytics {d})")
        elif abs(b["ttc"] - d["ttc"]) > TOL_TTC * len(bo) or abs(b["vat"] - d["vat"]) > TOL_VAT:
            diffs.append(f"TVA {rate} % : BO {b['ttc']:.2f} / {b['vat']:.2f} ≠ analytics {d['ttc']:.2f} / {d['vat']:.2f}")
    assert not diffs, "\n".join(diffs)
