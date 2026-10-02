"""
Socle des tests `test_nr_salesdata_<endpoint>` : un fichier par endpoint de la capability
`salesdata` (Partner API, route documentée `/api/salesdata/v2/<alias>/<action>`).

Ce que chaque fichier vérifie, en plus de ses règles propres :
  - l'enveloppe `{succeeded, version, data}` et sa `version` (`VERSIONS`, relevées le
    2026-10-02 sur le staging) ;
  - les erreurs d'entrée (`sequential_id` absent, non entier, archive inconnue) ;
  - le refus d'un mauvais token (404 « Not found », pas une fuite de données).

Périmètre : les `SCOPE_COUNT` dernières archives listées par le BO (pas de numéros figés :
le même fichier vaut pour le staging et la préprod). Montants et quantités en MILLIÈMES.
La caisse (VPN) sert d'oracle quand elle est joignable, sinon les tests qui en dépendent
sont skippés.
"""

from __future__ import annotations

from functools import lru_cache

import httpx
import pytest

from _nr import TIMEOUT_S, device_base, partner_call
from _target import partner_env

SCOPE_COUNT = 12
# Version servie dans l'enveloppe (staging, 2026-10-02). archive_content est en retard
# d'une version sur les autres actions.
VERSIONS = {"archives": "2.17", "archive_content": "2.15", "sales_summary": "2.17",
            "products_summary": "2.17", "users_summary": "2.17", "cashcontainers": "2.17"}
TOL = 10  # millièmes : arrondis de la répartition des menus (écart max relevé : 5)
UNKNOWN_SEQ = 999999


def call(action: str, **params):
    return partner_call("salesdata", 2, action, params=params or None)


def data(action: str, **params):
    status, payload = call(action, **params)
    assert status == 200, f"{action} {params} : HTTP {status} — {str(payload)[:300]}"
    assert payload.get("succeeded") is True, f"{action} {params} : {str(payload)[:300]}"
    assert payload.get("version") == VERSIONS[action], f"{action} : version {payload.get('version')!r} ≠ {VERSIONS[action]}"
    return payload["data"]


@lru_cache(maxsize=None)
def archives() -> tuple[dict, ...]:
    rows = data("archives")
    assert rows, "aucune archive dans le BO"
    return tuple(sorted(rows, key=lambda a: a["sequential_id"]))


def scope() -> list[int]:
    return [a["sequential_id"] for a in archives()[-SCOPE_COUNT:]]


def by_seq() -> dict[int, dict]:
    return {a["sequential_id"]: a for a in archives()}


# ── Erreurs d'entrée, communes aux actions par archive ──

def assert_input_errors(action: str, unknown_message: str | None, validates_input: bool = True):
    """Erreurs d'entrée : toujours un 400, jamais un 500 ni un 200.

    `validates_input` : l'action valide ses paramètres (Joi : `AnyRequired`, `NumberBase`).
    archive_content ne le fait pas (2026-10-02) : tout y répond « internal communication
    error ». `unknown_message` : message attendu pour une archive inconnue, None quand
    l'action répond « internal communication error ».

    Non figé, relevé le 2026-10-02 : sur une archive inconnue, les cinq actions renvoient la
    stack trace du serveur dans `data.backtrace`."""
    for params, joi in (({}, "AnyRequired"), ({"sequential_id": "abc"}, "NumberBase")):
        status, payload = call(action, **params)
        assert status == 400, f"{action} {params} : attendu 400, reçu {status} — {str(payload)[:200]}"
        if validates_input:
            assert (payload.get("data") or {}).get("sequential_id") == joi, (
                f"{action} {params} : erreur {joi} attendue — {str(payload)[:200]}")
    status, payload = call(action, sequential_id=UNKNOWN_SEQ)
    assert status == 400, f"{action} archive inconnue : attendu 400, reçu {status} — {str(payload)[:200]}"
    if unknown_message:
        assert payload.get("message") == unknown_message, f"{action} archive inconnue : {payload.get('message')!r}"


def assert_wrong_token_refused(action: str, **params):
    env = partner_env()
    response = httpx.get(f"{env['base_url']}/api/salesdata/v2/{env['installation_id']}/{action}",
                         params={**params, "apiuser_email": env["apiuser_email"], "apiuser_token": "nr-wrong-token"},
                         timeout=TIMEOUT_S)
    body = response.json()
    assert response.status_code == 404 and body.get("name") == "NotFound", (
        f"{action} mauvais token : attendu 404 NotFound, reçu {response.status_code} — {response.text[:200]}")
    assert "succeeded" not in body, f"{action} mauvais token : réponse de données — {response.text[:200]}"


# ── Caisse (VPN), oracle ──

def device(path: str) -> dict:
    try:
        response = httpx.get(f"{device_base()}/{path}", timeout=TIMEOUT_S)
    except httpx.TransportError as exc:
        pytest.skip(f"caisse injoignable ({exc.__class__.__name__}) : VPN ?")
    assert response.status_code == 200, f"caisse {path} : HTTP {response.status_code}"
    return response.json()


def pos_utc(ts: str | None) -> str | None:
    """Date caisse `20261001T122219` (UTC, pas l'heure locale) → `2026-10-01T12:22:19Z`."""
    if not ts:
        return None
    return f"{ts[0:4]}-{ts[4:6]}-{ts[6:8]}T{ts[9:11]}:{ts[11:13]}:{ts[13:15]}Z"


# ── Structure des réponses (test_00_fields de chaque fichier) ──

import json as _json
import re as _re
from pathlib import Path as _Path

SCHEMAS_DIR = _Path(__file__).parent / "schemas" / "salesdata"
_DYNAMIC_KEY = _re.compile(r"^[0-9a-fA-F-]{36}$|^\d+$")  # clés d'objet qui sont des identifiants


def _type(value) -> str:
    return {bool: "bool", int: "int", float: "float", str: "str", dict: "dict", list: "list"}.get(type(value), "null")


def walk(value, path: str, stats: dict):
    """Accumule, par chemin, le nombre d'objets parents vus, les présences et les types."""
    if isinstance(value, dict):
        stats.setdefault(path, {"seen": 0, "present": 0, "types": set()})["seen"] += 1
        for key, child in value.items():
            name = "{id}" if _DYNAMIC_KEY.match(str(key)) else key
            child_path = f"{path}.{name}" if path else name
            entry = stats.setdefault(child_path, {"seen": 0, "present": 0, "types": set()})
            entry["present"] += 1
            entry["types"].add(_type(child))
            walk(child, child_path, stats)
    elif isinstance(value, list):
        for item in value:
            entry = stats.setdefault(f"{path}[]", {"seen": 0, "present": 0, "types": set()})
            entry["present"] += 1
            entry["types"].add(_type(item))
            walk(item, f"{path}[]", stats)


def payloads(action: str) -> list:
    """Réponses brutes (enveloppe comprise) de l'action sur le périmètre."""
    if action == "archives":
        return [call("archives")[1]]
    return [call(action, sequential_id=seq)[1] for seq in scope()]


def structure(action: str) -> dict:
    stats: dict = {}
    payloads_seen = payloads(action)
    for payload in payloads_seen:
        walk(payload, "", stats)
    out = {}
    for path, s in stats.items():
        if not path:
            continue
        parent = path[:-2] if path.endswith("[]") else (path.rsplit(".", 1)[0] if "." in path else "")
        parent_seen = stats.get(parent, {}).get("seen", 0) if parent else len(payloads_seen)
        required = path.endswith("[]") or (s["present"] == parent_seen and "null" not in s["types"])
        out[path] = {"required": required, "types": sorted(s["types"])}
    return out


def parent_of(path: str) -> str:
    if path.endswith("[]"):
        return path[:-2]
    return path.rsplit(".", 1)[0] if "." in path else ""


def frozen(action: str) -> dict:
    return _json.loads((SCHEMAS_DIR / f"{action}.json").read_text())


def assert_fields(action: str):
    """Échoue si un champ figé disparaît (obligatoire) ou change de type ; un champ NOUVEAU
    n'est qu'affiché (un ajout ne casse pas un partenaire)."""
    expected, seen = frozen(action), structure(action)
    # Requis = présent dans chaque objet PARENT : sans parent objet dans l'échantillon (parent
    # optionnel ou toujours null, ex. cashmovements[].category, products[].unit), son absence
    # ne prouve rien.
    missing = [p for p, e in expected.items() if e["required"] and not p.endswith("[]") and p not in seen
               and (not parent_of(p) or set(seen.get(parent_of(p), {}).get("types", [])) & {"dict", "list"})]
    absent_where_required = [p for p, e in expected.items() if e["required"] and p in seen and not seen[p]["required"]
                             and "null" not in expected[p]["types"]]
    retyped = [f"{p} : {sorted(set(seen[p]['types']) - set(e['types']))} (figé : {e['types']})"
               for p, e in expected.items() if p in seen and set(seen[p]["types"]) - set(e["types"])]
    added = sorted(set(seen) - set(expected))
    if added:
        print(f"{action} : champs nouveaux (non figés) : {added}")
    assert not (missing or absent_where_required or retyped), (
        f"{action} — disparus : {missing} ; plus toujours présents : {absent_where_required} ; type changé : {retyped}")
