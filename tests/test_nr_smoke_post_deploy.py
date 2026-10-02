from __future__ import annotations

"""
Smoke test à lancer JUSTE APRÈS un déploiement BOV2 — lecture seule, ~15 s

Né de l'incident PROD du 2026-10-01 : la build 11 de worker-digested-data a cassé le
paiement à table (Sunday, Flunch) de 08:30 à 10:14, et rien n'a été vérifié juste après
la livraison. Chaque test vise un maillon qui a cassé ou failli casser ce jour-là.

| Test | Ce qu'il vérifie | Source |
|---|---|---|
| test_01 | chaque service instrumenté a au moins un pod `up`, et UNE seule build (pas de rollout coincé entre deux versions) | Prometheus (staging ; pas de monitoring en préprod) |
| test_02 | `check` d'un ticket OUVERT existant, par receipt_id et sequential_id : le chemin `getLiveReceipt` du 01/10 | Partner API |
| test_03 | `check` d'un ticket ARCHIVÉ de la dernière archive | Partner API |
| test_04 | la dernière archive avec des tickets est digérée, au même CA dans le BO et l'analytics | Partner API + digested-data |
| test_05 | aucune signature d'erreur de l'incident du 01/10 dans les logs depuis `SINCE_MIN` min | Elasticsearch |

LECTURE SEULE : aucun ticket créé (test_02 lit un ticket ouvert laissé par la suite ou
par la caisse, et skippe s'il n'y en a pas). Ce fichier ne vise PAS la prod : `_target.py`
l'exclut, choix maintenu le 2026-10-02 ; une exception éventuelle serait une décision à
part.

Les versions affichées par test_01 sont celles des labels `Version` (branche) et
`released` (build) des pods. Elles NE disent PAS si la préprod tourne avec ce qui partira
en prod : la préprod n'a pas de Prometheus, et le 2026-10-01 c'est précisément ce trou
qui a laissé passer BOV2KABAN-2195 (arrivé sur la branche préprod le 30/09 16:53, jamais
exercé). À vérifier à la main, ou via la CI, avant de livrer.

Observé VERT le 2026-10-02 sur le staging : 6 services up, une build chacun ; 0 des 5
signatures sur 24 h.

Lancer (juste après le déploiement, sur la plateforme déployée) :
    uv run --with pytest --with httpx --with python-dotenv \
      pytest tests/test_nr_smoke_post_deploy.py -v
"""

import collections
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest
from dotenv import load_dotenv

load_dotenv()

from _nr import TIMEOUT_S, archive_range, digested_data, es_search, partner_call, salesdata
from _target import target

# Services exposés à Prometheus (staging, 2026-10-02). digested-data, spaces, archives,
# customers et vpn-proxy ne le sont pas : ils ne figurent pas ici.
SERVICES = ("partners", "sync-manager", "static-model", "worker-sync", "worker-digested-data", "worker-partners")
GRAFANA_CONFIG = Path.home() / ".config" / "cashpad" / "grafana.json"
TABLES = range(1, 13)
SINCE_MIN = 15
# Signatures de l'incident du 2026-10-01 (digested-data et worker-digested-data), à 0 sur
# 24 h en staging le 2026-10-02 : une seule occurrence après un déploiement est suspecte.
SIGNATURES = (
    "Cannot read properties of undefined",  # items.reduce sur une réponse getLiveReceipt sans items
    "Could not find receipt",               # le 422 vu côté partenaire
    "ECONNREFUSED",                         # worker-digested-data qui refuse les connexions
    "out of shared memory",                 # base digested-data saturée
    "Database health check timed out",
)
TOL = 0.01


# ── Prometheus, via le proxy de datasource Grafana (clé du skill bov2-metrics) ──

def prometheus(query: str) -> list[dict]:
    if target() == "preprod":
        pytest.skip("pas de monitoring en préprod")
    if not GRAFANA_CONFIG.exists():
        pytest.skip(f"{GRAFANA_CONFIG} absent — Prometheus non lisible")
    conf = (json.loads(GRAFANA_CONFIG.read_text()).get("envs") or {}).get(target()) or {}
    if not conf.get("url") or not conf.get("token"):
        pytest.skip(f"pas d'url/token Grafana pour {target()} dans {GRAFANA_CONFIG}")
    base, headers = conf["url"].rstrip("/"), {"Authorization": f"Bearer {conf['token']}"}
    uid = conf.get("datasource_uid")
    if not uid:
        sources = httpx.get(f"{base}/api/datasources", headers=headers, timeout=TIMEOUT_S).json()
        proms = [d for d in sources if d.get("type") == "prometheus"]
        assert proms, "aucune datasource Prometheus dans Grafana"
        uid = next((d for d in proms if d.get("isDefault")), proms[0])["uid"]
    response = httpx.get(f"{base}/api/datasources/proxy/uid/{uid}/api/v1/query", params={"query": query},
                         headers=headers, timeout=TIMEOUT_S)
    assert response.status_code == 200, f"Prometheus : HTTP {response.status_code} — {response.text[:200]}"
    return response.json()["data"]["result"]


def test_01_services_are_up_on_a_single_build():
    rows = prometheus('count by (app_kubernetes_io_name, Version, released) (up{app_kubernetes_io_name=~"%s"} == 1)'
                      % "|".join(SERVICES))
    builds = collections.defaultdict(list)
    for r in rows:
        m = r["metric"]
        builds[m.get("app_kubernetes_io_name")].append(f"{m.get('Version')}#{m.get('released')} ×{r['value'][1]}")
    down = [s for s in SERVICES if s not in builds]
    mixed = {s: b for s, b in builds.items() if len(b) > 1}
    assert not down, f"services sans pod up : {down} — en place : {dict(builds)}"
    assert not mixed, f"plusieurs builds en même temps (rollout coincé ?) : {mixed}"


# ── Partner API ──

def check(**selector):
    return partner_call("payments", 2, "check", params=selector)


def assert_receipt(status, payload, selector):
    assert status == 200, (
        f"check {selector} : HTTP {status} — {str(payload)[:200]}. Un 422 « Could not find receipt » sur un "
        "ticket ouvert est le symptôme du 2026-10-01 (getLiveReceipt sans items)"
    )
    data = (payload or {}).get("data") or {}
    assert data.get("items"), f"check {selector} : ticket sans items — {str(data)[:200]}"
    return data


def test_02_check_an_open_receipt():
    for table in TABLES:
        status, payload = check(table=table)
        if status == 200:
            break
    else:
        pytest.skip(f"aucun ticket ouvert sur les tables {TABLES.start}–{TABLES.stop - 1} : rien à lire en direct")
    data = assert_receipt(status, payload, {"table": table})
    assert data.get("date_closed") is None, f"table {table} : ticket {data.get('sequential_id')} déjà clos"
    for selector in ({"receipt_id": data["id"]}, {"sequential_id": data["sequential_id"]}):
        assert_receipt(*check(**selector), selector)


@pytest.fixture(scope="module")
def last_archive() -> tuple[int, dict]:
    seqs = sorted(a["sequential_id"] for a in salesdata("archives") or [] if a.get("sequential_id") is not None)
    assert seqs, "aucune archive dans le BO"
    for seq in reversed(seqs[-10:]):
        total = (salesdata("sales_summary", sequential_id=seq) or {}).get("total_sales") or {}
        if total.get("nb_receipts"):
            return seq, total
    pytest.skip("aucune des 10 dernières archives n'a de ticket")


def test_03_check_an_archived_receipt(last_archive):
    seq, _ = last_archive
    receipts = [r for r in (salesdata("archive_content", sequential_id=seq) or {}).get("receipts") or []
                if not r.get("cancelled")]
    assert receipts, f"archive {seq} : aucun ticket dans archive_content"
    selector = {"sequential_id": receipts[0]["sequential_id"]}
    assert_receipt(*check(**selector), selector)


def test_04_last_archive_is_digested_with_the_bo_revenue(last_archive):
    seq, total = last_archive
    rows = digested_data("orders", archive_range(seq, seq) + [("customAggregate[0]", "archive")])
    row = next((r for r in rows if int(r.get("archiveSequentialId") or -1) == seq), None)
    assert row, f"archive {seq} absente de l'analytics : digest pas fait (worker-digested-data ?)"
    bo_ttc, an_ttc = (total.get("sales_incl_taxes") or 0) / 1000, float(row.get("finalAmountWithTax") or 0)
    assert abs(bo_ttc - an_ttc) <= TOL, f"archive {seq} : CA BO {bo_ttc:.2f} ≠ analytics {an_ttc:.2f}"


# ── Logs ──

@pytest.mark.parametrize("signature", SIGNATURES)
def test_05_no_incident_signature_in_recent_logs(signature):
    end = datetime.now(timezone.utc)
    rows = es_search(signature, start=end - timedelta(minutes=SINCE_MIN), end=end, limit=20)
    errors = [r for r in rows if r.get("log.level") == "error"]
    assert not errors, (
        f"« {signature} » ×{len(errors)} depuis {SINCE_MIN} min, ex. {errors[0]['@timestamp']} "
        f"{errors[0].get('event.dataset')} : {(errors[0].get('message') or '')[:160]}"
    )
