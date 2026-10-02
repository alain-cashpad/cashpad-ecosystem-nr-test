from __future__ import annotations

"""
Test de non-régression — notification SORTANTE d'un événement de ticket vers un partenaire

Premier test de la suite sur ce que BOV2 ENVOIE aux partenaires (les autres testent ce
qui entre). Chaque run pousse UN ticket non payé, puis lit dans les logs Elasticsearch
de la cible toute la chaîne qu'il déclenche :

    POST {base}/api/orders/v1/{INSTALLATION_ID}/cashpad/push_order_sync
    caisse → sync-manager `[proxyTriggers] … notify_receipt_event`  (web proxy de la caisse)
    rabbitmq `partners-new-receipt-event` start/end
    partners → POST du connecteur de référence (`order_new_receipt_event`)
    GET  {base}/p/partners/api/1/site/<site>/connector-configs        (connecteurs actifs, JWT du front)

⚠️ CRÉE UN TICKET NON PAYÉ sur la caisse à chaque run (`tickets_guard`,
NR_ALLOW_WRITES=1). Il reste ouvert.

## Préconditions (sinon le test échoue sans rien dire de BOV2)

- **Web proxy de la caisse pointé sur la cible.** C'est la CAISSE qui émet l'événement,
  vers la plateforme de son web proxy. Le 2026-10-02, `cashpad-8007` pointait sur la
  préprod : les tickets poussés depuis le staging notifiaient la préprod (site 1018).
  test_01 le vérifie en premier.
- **Cache des configs de connecteurs.** partners garde en mémoire, par pod, la liste des
  connecteurs actifs d'un site (30 min) et leur config (2 h), vidées seulement par une
  édition via le BO / l'API. Après un UPDATE SQL sur `connector_configs`, attendre 30 min
  ou redémarrer partners. Observé le 2026-10-02 à 18:22 : `flunch`, `drakkar` et
  `ilristo`, désactivés en base juste avant, étaient encore notifiés (test_03 aurait
  échoué) ; propre après redémarrage des pods.

## Connecteur de référence

`delarte` (staging, site 4652) : actif, `receiptEventNotification` et
`notifyOnAllReceipts` à true, sandbox `api.del-arte-staging.apizr.io` qui répond OK.
Les autres connecteurs actifs du site (`obypay`, `deliverect`, `ubereats`) ne
produisent pas d'appel sortant pour un `receiptCreated` (observé, cause non vérifiée
pour `ubereats`). Pour la préprod, `REFERENCE` est à revérifier.

Observé VERT le 2026-10-02 sur le staging (ticket 3274, trace 8cdf2f11…) : événement
reçu +1 s après le push, POST delarte +1,1 s, réponse `{"data": ""}` +1,6 s.

Lancer :
    NR_ALLOW_WRITES=1 uv run --with pytest --with httpx --with python-dotenv \
      pytest tests/test_nr_partners_receipt_event_notification.py -v
"""

import json
import re
import time
from datetime import datetime, timedelta, timezone

import pytest
from dotenv import load_dotenv

load_dotenv()

from _nr import assert_pushed, bo_request, es_search, partner_call, push_order, site, tickets_guard, unique_order_id
from _target import partner_env

pytestmark = tickets_guard()

REFERENCE = "delarte"
POUTINE = {"pos_id": "12ac180d-9ec1-4741-89ab-9cfb3eb7d81e", "price": 7.0}  # « Poutine Vladimir tsar »

# Budget d'attente des logs : la chaîne prend ~2 s, l'indexation Elasticsearch quelques s.
LOG_POLL_ATTEMPTS = 20
LOG_POLL_DELAY_S = 3.0


def poll_logs(*phrases: str, start: datetime, done, **kwargs) -> list[dict]:
    rows: list[dict] = []
    for _ in range(LOG_POLL_ATTEMPTS):
        rows = es_search(*phrases, start=start, end=datetime.now(timezone.utc) + timedelta(minutes=1), **kwargs)
        if done(rows):
            return rows
        time.sleep(LOG_POLL_DELAY_S)
    return rows


def payload_after(marker: str, message: str) -> dict:
    """Le JSON qui suit `marker` dans une ligne de log (`… data: {…}`)."""
    index = message.index(marker) + len(marker)
    value, _ = json.JSONDecoder().raw_decode(message[index:].lstrip())
    return value


@pytest.fixture(scope="module")
def chain():
    start = datetime.now(timezone.utc) - timedelta(seconds=5)
    order_id = unique_order_id("nr-notif-receipt")
    body = {"customer": {}, "order": {
        "id": order_id, "date_order": int(time.time()), "channel": "CHANNEL",
        "nb_eaters": 1, "comment": "NR receipt event notification", "table_number": 2,
        "items": [{**POUTINE, "quantity": 1, "production_level": 0}], "payments": [],
    }}
    ticket = assert_pushed(*push_order(body))
    events = poll_logs("partners-new-receipt-event", ticket["receipt_id"], start=start,
                       service="partners", done=lambda rows: any(" end: " in r["message"] for r in rows))
    trace_id = next((r["trace.id"] for r in events if r.get("trace.id")), None)
    prefix = f"PARTNER_ACTION [{site()['site_id']}][{REFERENCE}][order][order_new_receipt_event]"
    trace = []
    if trace_id:
        trace = poll_logs(start=start, service="partners", trace_id=trace_id,
                          done=lambda rows: any(prefix in r["message"] and " response: " in r["message"] for r in rows))
    return {"order_id": order_id, "ticket": ticket, "events": events, "trace_id": trace_id,
            "trace": trace, "prefix": prefix}


def test_01_receipt_event_reaches_the_target(chain):
    assert chain["events"], (
        f"aucun `partners-new-receipt-event` pour le ticket {chain['ticket']['receipt_sequential_id']} "
        f"sur {partner_env()['base_url']} en {LOG_POLL_ATTEMPTS * LOG_POLL_DELAY_S:.0f} s : le web proxy de "
        "la caisse pointe-t-il ailleurs que sur la cible ? (cf. en-tête)"
    )
    assert chain["trace_id"], f"événement sans trace.id : {chain['events'][0]['message'][:200]}"
    assert any(" end: " in r["message"] for r in chain["events"]), "événement consommé sans `end` (consumer bloqué ?)"


def test_02_reference_connector_posts_the_receipt_event(chain):
    lines = [r["message"] for r in chain["trace"] if chain["prefix"] in r["message"]]
    sent = [m for m in lines if " POST " in m and " data: " in m]
    assert sent, f"{REFERENCE} : aucun POST `order_new_receipt_event` dans la trace {chain['trace_id']}"
    data = payload_after(" data: ", sent[0]).get("data") or {}
    assert data.get("installation_id") == partner_env()["installation_id"], f"installation_id : {data.get('installation_id')!r}"
    assert (data.get("event") or {}).get("type_name") == "receiptCreated", f"event : {data.get('event')!r}"
    assert (data.get("receipt") or {}).get("deliveryId") == chain["order_id"], (
        f"deliveryId {(data.get('receipt') or {}).get('deliveryId')!r} ≠ order.id {chain['order_id']!r}"
    )
    errors = [r for r in chain["trace"] if chain["prefix"] in r["message"] and r.get("log.level") == "error"]
    assert not errors, f"{REFERENCE} en erreur : {[e['message'][:200] for e in errors]}"
    assert any(" response: " in m for m in lines), f"{REFERENCE} : POST parti sans réponse loguée"


def test_03_only_active_connectors_are_notified(chain):
    status, payload = bo_request("GET", f"1/site/{site()['site_id']}/connector-configs")
    assert status == 200, f"connector-configs : HTTP {status} — {payload!r}"
    active = {c["connectorSlug"] for c in (payload or {}).get("data") or []
              if c.get("isActive") and c.get("state") == "configured"}
    notified = set()
    for r in chain["trace"]:
        notified |= set(re.findall(r"PARTNER_ACTION \[\d+\]\[([\w-]+)\]", r["message"]))
        notified |= set(re.findall(r"^\[([\w-]+)\] _notifyNewReceiptEvent", r["message"]))
    notified.discard("undefined")  # préfixe des lignes de cache, sans connecteur
    assert notified, f"aucun connecteur notifié dans la trace {chain['trace_id']}"
    assert notified <= active, (
        f"connecteurs INACTIFS notifiés : {sorted(notified - active)} (actifs : {sorted(active)}). "
        "Après un UPDATE SQL sur connector_configs, le cache de partners garde l'ancienne liste 30 min (cf. en-tête)"
    )
