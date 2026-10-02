from __future__ import annotations

"""
Test de non-régression — contrats entre services BOV2 (appels internal-rpc)

Né du rollback PROD du 2026-10-01 : digested-data a été ramené à une version antérieure,
static-model non. digested-data appelait alors static-model avec un corps que la version
en place refusait, 357 fois en 5 min :

    static-model   warn  validateBodyHook validation failed {"dataError":{"siteId":"AnyRequired"},
                         "body":{"type":"paramsRaw",…},"uri":"static-model/internal/1/internal-rpc"}
    digested-data  error _postRequest http://static-model…/static-model/internal/1/internal-rpc,
                         {"type":"paramsRaw",…}, Request failed with status code 400

Aucune réponse publique ne le montrait directement : le libellé manquait, le reste
passait. Seuls les logs voient un contrat rompu entre deux services.

## Ce que fait le test

1. Il SOLLICITE les échanges internes par des appels publics en lecture : `check` d'un
   ticket archivé et d'un ticket ouvert (partners → digested-data → worker-digested-data,
   static-model, customers), `archive_content`, `sales_summary`, `products_summary`,
   `users_summary` (partners → archives, digested-data), `stocks state` et `full_menu`
   (partners → static-model, caisse), `get_customers` (partners → customers), et
   l'analytics `orders` / `sales` (digested-data → static-model pour les libellés).
2. Il cherche dans les logs de cette fenêtre les deux signatures, LIMITÉES à
   `internal-rpc` : un `validateBodyHook` hors internal-rpc est une entrée partenaire
   invalide (bruit normal, 12 sur 7 j en staging), pas un contrat rompu.

| Test | Règle |
|---|---|
| test_01 | chaque appel public de la sollicitation répond 200 |
| test_02 | aucun service appelé n'a refusé un corps internal-rpc (`validateBodyHook` + `internal-rpc`) |
| test_03 | aucun appelant n'a reçu d'erreur HTTP d'un internal-rpc (`_postRequest` + `internal-rpc` + `Request failed with status code`) |
| test_04 | la sollicitation a bien atteint static-model, archives et digested-data en internal-rpc (sinon 02/03 sont vides) |

URI internes : `internal-rpc` ET `internal/1/rpc` (digested-data), cf. `RPC_URIS`.

Bruit de fond mesuré le 2026-10-02 sur le staging (7 j) : 0 pour test_02, 2 pour test_03
(le 29/09, digested-data → worker-digested-data : le défaut `reduce` du 2026-10-01).
D'autres trafics de la plateforme peuvent tomber dans la fenêtre : le message d'échec
donne le service, l'URI et le corps pour trier.

Limites : seul digested-data logue ses appels sortants sous la forme `_postRequest` ; un
autre appelant qui logue autrement échappe à test_03 (test_02 le couvre côté appelé, si
l'appelé valide son corps). Pas de prod (`_target.py`).

Lancer :
    uv run --with pytest --with httpx --with python-dotenv \
      pytest tests/test_nr_internal_rpc_contracts.py -v
"""

import time
from datetime import datetime, timedelta, timezone

import pytest
from dotenv import load_dotenv

load_dotenv()

from _nr import archive_range, digested_data, es_search, partner_call, salesdata

LOG_WAIT_S = 20  # indexation Elasticsearch : quelques secondes mesurées, marge incluse
TABLES = range(1, 13)
# Deux formes d'URI interne : `<svc>/internal/1/internal-rpc` (static-model, archives,
# customers, worker-digested-data) et `<svc>/internal/1/rpc` (digested-data). Mesuré le
# 2026-10-02 : chercher la seule première ratait tout appel vers digested-data.
RPC_URIS = ("internal-rpc", "internal/1/rpc")
# Services que la sollicitation doit atteindre en internal-rpc (mesuré le 2026-10-02 :
# static-model 21 lignes, archives 9, digested-data 12), sinon test_02/03 ne prouvent rien.
REACHED = ("static-model", "archives", "digested-data")


def solicit() -> list[tuple[str, int]]:
    calls: list[tuple[str, int]] = []

    def call(label, capability, version, action, **params):
        status, payload = partner_call(capability, version, action, params=params or None)
        calls.append((label, status))
        return payload

    seqs = sorted(a["sequential_id"] for a in salesdata("archives") or [] if a.get("sequential_id") is not None)
    seq = seqs[-1]
    content = call("salesdata archive_content", "salesdata", 2, "archive_content", sequential_id=seq) or {}
    receipts = [r for r in (content.get("data") or {}).get("receipts") or [] if not r.get("cancelled")]
    if receipts:
        call("payments check (archivé)", "payments", 2, "check", sequential_id=receipts[0]["sequential_id"])
    for table in TABLES:  # ticket ouvert : le chemin getLiveReceipt
        status, _ = partner_call("payments", 2, "check", params={"table": table})
        if status == 200:
            calls.append((f"payments check (ouvert, table {table})", status))
            break
    for action in ("sales_summary", "products_summary", "users_summary"):
        call(f"salesdata {action}", "salesdata", 2, action, sequential_id=seq)
    call("stocks state", "stocks", 1, "state")
    call("menus full_menu", "menus", 2, "full_menu")
    call("customers get_customers", "customers", 1, "get_customers")
    for resource, aggregate in (("orders", "archive"), ("sales", "product")):
        digested_data(resource, archive_range(max(seqs[0], seq - 5), seq) + [("customAggregate[0]", aggregate), ("limit", "50")])
        calls.append((f"analytics {resource}", 200))  # digested_data() échoue lui-même sur un non-200
    return calls


@pytest.fixture(scope="module")
def run():
    start = datetime.now(timezone.utc) - timedelta(seconds=2)
    calls = solicit()
    time.sleep(LOG_WAIT_S)
    end = datetime.now(timezone.utc) + timedelta(seconds=5)
    return calls, start, end


def describe(rows: list[dict]) -> str:
    return "\n".join(f"{r['@timestamp']} {r.get('event.dataset')} : {(r.get('message') or '')[:220]}" for r in rows[:5])


def test_01_solicitation_calls_answer(run):
    calls, _, _ = run
    failed = [(label, status) for label, status in calls if status != 200]
    assert not failed, f"appels publics en échec : {failed}"


def search_rpc(*phrases: str, start, end) -> list[dict]:
    return [r for uri in RPC_URIS for r in es_search(*phrases, uri, start=start, end=end, limit=50)]


def test_02_no_internal_rpc_body_refused(run):
    _, start, end = run
    rows = search_rpc("validateBodyHook validation failed", start=start, end=end)
    assert not rows, f"{len(rows)} corps internal-rpc refusés (contrat rompu entre deux versions ?) :\n{describe(rows)}"


def test_03_no_internal_rpc_call_failed(run):
    _, start, end = run
    rows = search_rpc("_postRequest", "Request failed with status code", start=start, end=end)
    assert not rows, f"{len(rows)} appels internal-rpc en erreur HTTP :\n{describe(rows)}"


def test_04_solicitation_reached_the_internal_services(run):
    _, start, end = run
    seen = {r.get("event.dataset") for r in search_rpc(start=start, end=end)}
    missing = [svc for svc in REACHED if svc not in seen]
    assert not missing, f"aucun appel internal-rpc vu pour {missing} (vus : {sorted(s for s in seen if s)}) : test_02/03 non probants"
