"""
Socle des tests portés (famille `test_nr_*`) : Partner API, webhook Deliverect,
lecture caisse et liste des commandes d'un connecteur.

Ces tests reprennent ceux des anciens repos `cashpad-bov2-non-reg-partners-api`
et `cashpad-bov2-non-reg-deliverect`. Ils s'appuient sur `_target.py` (cible,
allowlist anti-prod, couple partenaire) et n'ajoutent que ce qui manque :

  - `partner_call()`   Partner API sur la route DOCUMENTÉE (doc Notion « APIs ») :
                       /api/<capability>/<vN>/<alias>/[cashpad/]<action>, auth en
                       query. Jamais la route native /p/partners/public/1/… .
  - `device_receipt()` lecture du ticket SUR LA CAISSE, via le VPN
                       (http://<CASHPAD_ID>.vpn.osilia.com:9091). Source de vérité
                       de ce qui a réellement été encaissé.
  - `bo_request()`     routes BO du service partners (/p/partners/api/…), JWT du front
                       (sign-in sso, repli `BOV2_TOKEN`). Liste des commandes d'un
                       connecteur, config.
  - `tickets_guard()`  garde des modules qui CRÉENT UN TICKET sur la caisse.
  - `es_search()`      logs Elasticsearch de la cible, en LECTURE (ES|QL, clé API en
                       lecture seule du skill bov2-elastic-logs, ~/.config/cashpad/
                       elastic.json). Seul moyen d'observer une notification SORTANTE
                       vers un partenaire.

Identifiants de site et de connecteur : table `SITES` ci-dessous, par cible. Ce ne
sont pas des secrets (relevés dans les anciens repos, 2025), mais ils sont propres
à la plateforme : `cashpad-8007` n'a pas le même site_id en staging et en préprod.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

from _target import partner_env, target

SITES = {
    "staging": {
        "site_id": 4652,
        "connectors": {"obypay": 1123, "deliverect": 1224},
        # Lu en base staging le 2026-09-29 (connector_configs 1224). L'ancien repo avait
        # 684b2589… : le webhook répond désormais 400 « Connector not configured » dessus.
        "deliverect_location": "6628c9bc857b17fee4dd134b",
    },
    "preprod": {
        "site_id": 1018,
        "connectors": {"obypay": 1088, "deliverect": 1080},
        "deliverect_location": "6628c9bc857b17fee4dd134b",
    },
}

# La doc Notion écrit les actions orders sous un segment fixe `cashpad/`.
ACTION_PREFIX = {"orders": "cashpad/"}

TIMEOUT_S = 60

# Polling de la liste des commandes d'un connecteur : le traitement d'une commande
# (push device, statut) est asynchrone. Budget repris des anciens repos (11 × 0,5 s),
# élargi : un statut attendu qui n'arrive pas doit ÉCHOUER, pas être ignoré en silence
# comme le faisaient les anciens tests (`if order_treated:`).
ORDER_POLL_ATTEMPTS = 20
ORDER_POLL_DELAY_S = 1.0


def site() -> dict:
    return SITES[target()]


def unique_order_id(prefix: str) -> str:
    """`order.id` est la clé d'idempotence de push_order_sync : unique par run."""
    return f"{prefix}-{uuid.uuid4()}"


def _json(response: httpx.Response):
    try:
        return response.json()
    except ValueError:
        return None


# ── Partner API (route documentée) ──

def partner_call(capability: str, version: int, action: str, *, verb: str = "GET",
                 params: dict | None = None, body=None):
    """Appelle une action Partner API sur sa route documentée. Renvoie (status, payload).

    Le corps n'est envoyé que s'il est fourni : GET/DELETE sans corps, comme la doc.
    """
    env = partner_env()
    url = (f"{env['base_url']}/api/{capability}/v{version}/{env['installation_id']}/"
           f"{ACTION_PREFIX.get(capability, '')}{action}")
    query = dict(params or {})
    query["apiuser_email"] = env["apiuser_email"]
    query["apiuser_token"] = env["apiuser_token"]
    kwargs = {"json": body} if body is not None else {}
    response = httpx.request(verb, url, params=query, timeout=TIMEOUT_S, **kwargs)
    return response.status_code, _json(response)


def push_order(body: dict):
    return partner_call("orders", 1, "push_order_sync", verb="POST", body=body)


def assert_pushed(status, payload) -> dict:
    """Push accepté : `{succeeded, receipt_id, receipt_sequential_id, receipt_period_id}`."""
    assert status == 200, f"push_order_sync : attendu 200, reçu {status} — {payload!r}"
    assert isinstance(payload, dict) and payload.get("succeeded") is True, f"push refusé : {payload!r}"
    for key in ("receipt_id", "receipt_sequential_id", "receipt_period_id"):
        assert payload.get(key) not in (None, ""), f"`{key}` absent de la réponse du push : {payload!r}"
    return payload


# ── Caisse (VPN) ──

def device_base() -> str:
    cashpad_id = os.getenv("CASHPAD_ID") or partner_env()["installation_id"]
    return f"http://{cashpad_id}.vpn.osilia.com:9091"


def device_receipt(sequential_id: int) -> dict:
    """Ticket lu sur la caisse. Montants et quantités en MILLIÈMES (7 € → 7000)."""
    response = httpx.get(f"{device_base()}/reports/get_receipt_content",
                         params={"sequential_id": sequential_id}, timeout=TIMEOUT_S)
    payload = _json(response)
    assert response.status_code == 200, f"caisse : HTTP {response.status_code} — {payload!r}"
    assert isinstance(payload, dict) and payload.get("succeeded") is True, f"caisse : {payload!r}"
    receipt = payload["receipt"]
    assert receipt.get("sequentialId") == int(sequential_id), (
        f"caisse : ticket {receipt.get('sequentialId')} lu, {sequential_id} attendu"
    )
    return receipt


def device_receipt_by_delivery_id(delivery_id: str) -> dict:
    """Ticket EN COURS dont `deliveryId` vaut `delivery_id`, cherché dans la liste live de la
    caisse (`get_receipts_content` sans paramètre : tous les tickets non archivés).

    Pour Deliverect, c'est le seul lien fiable : observé le 2026-09-29 sur le staging, la
    commande reste `preparing` avec `receiptId` vide côté BOV2 alors que le ticket existe
    bien sur la caisse. Polling : la création du ticket suit le webhook de quelques secondes.
    """
    last = 0
    for _ in range(ORDER_POLL_ATTEMPTS):
        response = httpx.get(f"{device_base()}/reports/get_receipts_content", timeout=TIMEOUT_S)
        payload = _json(response) or {}
        assert response.status_code == 200 and payload.get("succeeded") is True, (
            f"caisse get_receipts_content : HTTP {response.status_code} — {str(payload)[:200]}"
        )
        receipts = payload.get("receipts") or []
        hits = [r for r in receipts if r.get("deliveryId") == delivery_id]
        if hits:
            return device_receipt(hits[0]["sequentialId"])
        last = len(receipts)
        time.sleep(ORDER_POLL_DELAY_S)
    raise AssertionError(
        f"aucun ticket en cours avec deliveryId={delivery_id!r} sur la caisse après "
        f"{ORDER_POLL_ATTEMPTS * ORDER_POLL_DELAY_S:.0f} s ({last} tickets en cours)"
    )


def receipt_item(receipt: dict, product_id: str) -> dict:
    hits = [i for i in receipt.get("items") or [] if str(i.get("product", "")).upper() == product_id.upper()]
    assert hits, f"produit {product_id} absent du ticket caisse — produits : {[i.get('product') for i in receipt.get('items') or []]}"
    return hits[0]


def receipt_addon(receipt: dict, product_id: str) -> dict:
    hits = [a for i in receipt.get("items") or [] for a in i.get("addons") or []
            if str(a.get("productAddon", "")).upper() == product_id.upper()]
    assert hits, f"option {product_id} absente des addons du ticket caisse"
    return hits[0]


# ── Routes BO du service partners (bearer) ──

_BO_TOKEN: dict = {}


def bo_token() -> str:
    """JWT du front BO (celui que le dashboard envoie en `Authorization: Bearer`).

    Même mécanisme que test_bov2kaban_2212/2214/2216… : `POST /p/sso/public/1/sign-in`
    avec `{username, password}` → 201 `{token, refreshToken}`. Identifiants par cible :
    `BOV2_<CIBLE>_LOGIN` / `BOV2_<CIBLE>_PASSWORD` (en staging : les mêmes noms que les
    tests customers). Repli : `BOV2_TOKEN`, un JWT copié du front (celui des test_cp_*),
    qui expire. Guillemets retirés : `localStorage.getItem` les inclut, et un header mal
    formé fait répondre 500 à nginx, pas 401. Skip si rien n'est configuré.
    """
    name = target()
    if name in _BO_TOKEN:
        return _BO_TOKEN[name]
    login, password = os.getenv(f"BOV2_{name.upper()}_LOGIN"), os.getenv(f"BOV2_{name.upper()}_PASSWORD")
    if login and password:
        response = httpx.post(f"{partner_env()['base_url']}/p/sso/public/1/sign-in",
                              json={"username": login, "password": password}, timeout=TIMEOUT_S)
        assert response.status_code in (200, 201), (
            f"sign-in sso ({name}) : HTTP {response.status_code} — {response.text[:200]}"
        )
        token = (_json(response) or {}).get("token")
        assert token, f"sign-in sso ({name}) sans `token` : {sorted(_json(response) or {})}"
    else:
        token = (os.getenv("BOV2_TOKEN") or "").strip().strip('"').removeprefix("Bearer ").strip()
        if not token:
            pytest.skip(f"Ni BOV2_{name.upper()}_LOGIN/BOV2_{name.upper()}_PASSWORD, ni BOV2_TOKEN "
                        "dans .env — étape BO partners non exécutable")
    _BO_TOKEN[name] = token
    return token


def bo_request(verb: str, path: str, *, params: dict | None = None, body=None):
    """/p/partners/api/<path>, authentifié par le JWT du front (cf. `bo_token`)."""
    headers = {"Authorization": f"Bearer {bo_token()}", "accept": "application/json"}
    url = f"{partner_env()['base_url']}/p/partners/api/{path.lstrip('/')}"
    kwargs = {"json": body} if body is not None else {}
    response = httpx.request(verb, url, params=params, headers=headers, timeout=TIMEOUT_S, **kwargs)
    return response.status_code, _json(response)


def connector_order(connector: str, display_id: str, *, done) -> dict:
    """Attend qu'une commande du connecteur satisfasse `done(order)`. Renvoie la commande.

    `display_id` = `order.id` pour un partenaire, `channelOrderDisplayId` pour Deliverect.
    """
    s = site()
    path = f"2/site/{s['site_id']}/connector/{s['connectors'][connector]}/orders"
    last = "jamais lue"
    for _ in range(ORDER_POLL_ATTEMPTS):
        status, payload = bo_request("GET", path, params={"limit": 50, "skip": 0})
        assert status == 200, f"liste des commandes {connector} : HTTP {status} — {payload!r}"
        hits = [o for o in (payload or {}).get("data") or [] if o.get("displayId") == display_id]
        if hits and done(hits[0]):
            return hits[0]
        last = f"statut {hits[0].get('status')!r}" if hits else "absente de la liste"
        time.sleep(ORDER_POLL_DELAY_S)
    raise AssertionError(
        f"commande {display_id} ({connector}) : état attendu non atteint après "
        f"{ORDER_POLL_ATTEMPTS * ORDER_POLL_DELAY_S:.0f} s — dernier état : {last}"
    )


# ── Webhook Deliverect ──

PAYLOADS_DIR = Path(__file__).parent / "payloads"


def deliverect_order(name: str) -> dict:
    """Rend `payloads/deliverect/<name>.json.tmpl` : identifiants uniques par run, dates
    du moment, location de la cible. Montants Deliverect en CENTIMES (5640 = 56,40 €) :
    ×10 pour comparer aux millièmes de la caisse."""
    now = datetime.now(timezone.utc)
    iso = "%Y-%m-%dT%H:%M:%SZ"
    channel_order_id = f"NR{uuid.uuid4().int % 10**9:09d}"
    tokens = {
        "_id": str(uuid.uuid1()),
        "date": now.strftime("%Y%m%d"),
        "_created": now.strftime(iso),
        "_updated": (now + timedelta(seconds=30)).strftime(iso),
        "pickupTime": (now + timedelta(minutes=20)).strftime(iso),
        "deliveryTime": (now + timedelta(minutes=30)).strftime(iso),
        "channelOrderId": channel_order_id,
        "channelOrderDisplayId": f"T{channel_order_id[-6:]}",
        "location": site()["deliverect_location"],
    }
    text = (PAYLOADS_DIR / "deliverect" / f"{name}.json.tmpl").read_text()
    for key, value in tokens.items():
        text = text.replace(f"{{{key}}}", value)
    return json.loads(text)


def deliverect_push(order: dict):
    """Webhook de commande Deliverect → BOV2 (route publique, sans auth). 201 attendu :
    l'accusé de réception ne dit rien du sort de la commande, lu ensuite dans la liste
    des commandes du connecteur (cf. `connector_order`)."""
    url = f"{partner_env()['base_url']}/p/partners/public/1/webhooks/deliverect/orders"
    response = httpx.post(url, params={"locationId": site()["deliverect_location"]}, json=order, timeout=TIMEOUT_S)
    return response.status_code, _json(response)


# ── Garde des modules qui créent un ticket ──

def tickets_guard() -> pytest.MarkDecorator:
    """`pytestmark` des modules qui CRÉENT UN TICKET sur la caisse (ou modifient une config).

    Plus strict que `writes_guard()` : skippé sur TOUTES les cibles, staging compris,
    sauf `NR_ALLOW_WRITES=1`. Un ticket poussé est fiscal : il ne s'annule pas par l'API.
    """
    return pytest.mark.skipif(
        os.getenv("NR_ALLOW_WRITES") != "1",
        reason=f"crée des tickets sur la caisse ({target()}) — NR_ALLOW_WRITES=1 pour l'autoriser",
    )


# ── Logs Elasticsearch (lecture seule) ──

ES_CONFIG = Path.home() / ".config" / "cashpad" / "elastic.json"
# Préfixe d'index par cible : le staging s'appelle `dev` dans les logs. Pas de prod.
ES_INDEX = {"staging": "filebeat-dev-*", "preprod": "filebeat-preprod-*"}


def _esql_literal(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def es_search(*phrases: str, start: datetime, end: datetime, service: str | None = None,
              trace_id: str | None = None, limit: int = 500) -> list[dict]:
    """Lignes de log de la cible entre `start` et `end` dont `message` contient TOUTES les
    `phrases` (MATCH_PHRASE). Triées par date côté client : avec SORT, ES|QL renvoie
    `message` à null sur une partie des lignes (mesuré par le skill le 2026-09-30).
    Skip si la clé du skill bov2-elastic-logs est absente."""
    if not ES_CONFIG.exists():
        pytest.skip(f"{ES_CONFIG} absent — logs Elasticsearch non lisibles")
    conf = json.loads(ES_CONFIG.read_text())
    where = ["@timestamp >= ?_tstart", "@timestamp < ?_tend"]
    if service:
        where.append(f"`event.dataset.keyword` == {_esql_literal(service)}")
    if trace_id:
        where.append(f"`trace.id.keyword` == {_esql_literal(trace_id)}")
    where += [f"MATCH_PHRASE(message, {_esql_literal(p)})" for p in phrases]
    query = (f"FROM {ES_INDEX[target()]} | WHERE {' AND '.join(where)}"
             f" | KEEP `@timestamp`, `event.dataset`, `log.level`, `trace.id`, message | LIMIT {limit}")
    iso = lambda d: d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    response = httpx.post(f"{conf['es_url'].rstrip('/')}/_query", params={"format": "json"},
                          headers={"Authorization": f"ApiKey {conf['api_key']}"},
                          json={"query": query, "params": [{"_tstart": iso(start)}, {"_tend": iso(end)}]},
                          timeout=TIMEOUT_S)
    assert response.status_code == 200, f"Elasticsearch : HTTP {response.status_code} — {response.text[:300]}"
    payload = response.json()
    cols = [c["name"] for c in payload.get("columns", [])]
    rows = [dict(zip(cols, values)) for values in payload.get("values", [])]
    return sorted(rows, key=lambda r: r["@timestamp"])
