from __future__ import annotations

"""
Test de non-régression généré par /cp-test — ticket BOV2KABAN-2262
[ORDER API][LOYALTY] Accept every loyalty provider handled by the Cashpad server

Fige le comportement OBSERVÉ et VALIDÉ le 2026-09-21 à 13:50 CEST sur le staging
(host allowlisté : staging.cashpad.app) :

    POST {STAGING_BASE_URL}/api/orders/v1/{INSTALLATION_ID}/cashpad/push_order_sync
        ?apiuser_email=...&apiuser_token=...
    body: {"order": {..., "loyalty": {"provider": "<x>"}}}

`extractLoyalty()` résout désormais `provider` via le mapping nommé
`PARTNER_LOYALTY_PROVIDERS` (comarch→0 … brevo→6), en `trim().toLowerCase()`,
au lieu de la comparaison codée en dur à `comarch`.

## Pourquoi ce test passe par un endpoint d'écriture — et pourquoi il n'écrit rien

`precheck_order` serait l'endpoint naturel : il appelle bien `_preparePartnerOrder()`,
donc le serializer. Mais il ne consulte **jamais** `serializeErrors` — vérifié le
2026-09-21, il répond `{"succeeded": true, "checks": {}}` même avec un produit
inexistant. Il est donc aveugle au comportement testé ici.

`push_order_sync` est la seule surface qui expose ces erreurs : `createOrder()` lève
`CashpadOrderSerializerError(serializeErrors.join(', '))`.

Contrepoids, à ne pas retirer :

  - chaque appel porte un `pos_id` UUID v4 valide mais **absent du catalogue**.
    `getProduct()` ajoute alors `Item not found for <uuid>`, ce qui garantit une
    exception **avant** `_pushExternalOrder()` : aucun ticket n'est jamais créé sur
    la caisse, aucun appel device n'est émis. C'est le pivot de sûreté du fichier ;
  - le host est verrouillé sur l'allowlist avant tout appel réseau ;
  - les `order.id` sont uniques par run (préfixe `nr-2262-`) — aucun rejeu, aucune
    collision d'idempotence avec un ticket réel.

Résidu assumé : une ligne `Orders` en status FAILED par appel, en base staging. Elle
est inhérente à toute tentative de push et n'est pas supprimable via l'API.

## Ce que ce test NE vérifie PAS

L'AC1 demande que chaque provider « yields the matching `CashpadLoyalty.provider`
ordinal (0-6) ». **L'ordinal n'est pas observable en boîte noire** : la réponse HTTP
ne contient pas le `CashpadLoyalty` transmis au device. Seuls l'acceptation et le
rejet le sont. La correspondance provider→ordinal relève d'un test unitaire côté
repo `partners` — ne pas croire que ce fichier la couvre.

## Cas `provider: ""` — écart connu, acté par le dev

L'AC4 annonçait « a missing or empty provider … still produces the "missing loyalty
provider" error (unchanged behaviour) ». Observé : la chaîne vide est désormais
rejetée **en amont**, par le validateur Joi (`400 form errors`,
`{"order.loyalty.provider": "StringEmpty"}`), parce que `provider` est typé
`Joi.string()` — qui refuse `''` par défaut. `null` et l'absence de clé, eux,
produisent toujours `missing loyalty provider`.

Le dev a tranché le 2026-09-21 que l'écart n'est pas bloquant (l'ordre est rejeté en
400 dans tous les cas, jamais envoyé avec un mauvais provider). `test_05` fige donc
le comportement **réel**, pas le libellé de l'AC. Si ce test vire au rouge en
attendant `missing loyalty provider`, c'est que le validateur a été assoupli — pas
forcément une régression, mais à requalifier avec l'équipe.

Lancer :
    uv run --with pytest --with httpx --with python-dotenv \
      pytest tests/test_bov2kaban_2262_loyalty_providers.py -v
"""

import os
import time
import uuid
from urllib.parse import urlparse

import httpx
import pytest
from dotenv import load_dotenv

load_dotenv()


# ── Garde-fou anti-prod : la vérification ne cible que le staging ──
HOST_ALLOWLIST = {"staging.cashpad.app"}

# Le mapping du ticket, miroir de loyalty::IProvider::Type (src/OSLoyalty/IProvider.h).
# Les ordinaux ne sont PAS assertables ici (cf. en-tête) — la liste sert à exercer
# chaque clé et à vérifier l'ordre exact annoncé dans le message d'erreur.
LOYALTY_PROVIDERS = ["comarch", "splio", "obypay", "zerosix", "como", "adelya", "brevo"]

EXPECTED_PROVIDER_LIST = ", ".join(LOYALTY_PROVIDERS)

# Le validateur impose un GUID sur pos_id : un UUID aléatoire est donc valide pour
# lui, mais introuvable au catalogue — ce qui bloque le push device. Cf. en-tête.
def bogus_pos_id() -> str:
    return str(uuid.uuid4())


def get_env() -> dict:
    """Charge les variables statiques depuis .env (convention du repo, cf. 2194)."""
    required = [
        "staging_base_url",   # base staging (host allowlisté) — cf. /cp-test
        "installation_id",    # alias du site ciblé (ex. cashpad-8007)
        "apiuser_email",      # auth partner orders
        "apiuser_token",
    ]
    env = {}
    missing = []
    for key in required:
        value = os.getenv(key.upper())
        if not value:
            missing.append(key.upper())
        else:
            env[key] = value
    if missing:
        raise EnvironmentError(f"Variables manquantes dans .env : {missing}")

    host = urlparse(env["staging_base_url"]).hostname
    assert host in HOST_ALLOWLIST, f"Host hors allowlist : {host!r} — refus d'exécuter"
    return env


def push_order(loyalty: dict | None = None, *, omit_loyalty: bool = False):
    """Pousse une commande volontairement non sérialisable. Renvoie (status, payload).

    Le `pos_id` inexistant garantit qu'aucun ticket n'atteint la caisse : l'exception
    est levée avant `_pushExternalOrder()`. Le message d'erreur agrège TOUTES les
    erreurs de sérialisation, d'où la lecture par `in` dans les tests.
    """
    env = get_env()
    url = (
        f"{env['staging_base_url'].rstrip('/')}"
        f"/api/orders/v1/{env['installation_id']}/cashpad/push_order_sync"
    )
    params = {
        "apiuser_email": env["apiuser_email"],
        "apiuser_token": env["apiuser_token"],
    }
    order = {
        "id": f"nr-2262-{uuid.uuid4()}",
        "date_create": int(time.time()),
        "nb_eaters": 1,
        "type": 0,
        "items": [{"pos_id": bogus_pos_id(), "price": 1.0, "quantity": 1}],
        "payments": [],
    }
    if not omit_loyalty:
        order["loyalty"] = loyalty if loyalty is not None else {}

    response = httpx.post(url, params=params, json={"order": order}, timeout=60)
    try:
        return response.status_code, response.json()
    except ValueError:
        return response.status_code, None


def serializer_message(payload: dict | None) -> str:
    """Message d'erreur du serializer, ou chaîne vide si la réponse a une autre forme."""
    if not isinstance(payload, dict):
        return ""
    return payload.get("message") or ""


def assert_item_not_found(payload: dict | None):
    """Sanity check : l'appel a bien été bloqué par le produit inexistant.

    Si cette assertion tombe, le garde-fou du fichier ne joue plus — un ticket a pu
    partir sur la caisse. À traiter en priorité avant de lire les autres échecs.
    """
    message = serializer_message(payload)
    assert "Item not found for" in message, (
        "Le produit bidon n'a pas bloqué la sérialisation — vérifier qu'aucun ticket "
        f"n'a été créé sur la caisse. Réponse : {payload!r}"
    )


# ── AC1 : les 7 providers du mapping sont acceptés ──

@pytest.mark.parametrize("provider", LOYALTY_PROVIDERS)
def test_01_every_mapped_provider_serialises(provider):
    """Aucune erreur loyalty pour les 7 providers — seul `Item not found` subsiste.

    Fige l'acceptation, PAS l'ordinal (non observable, cf. en-tête).
    """
    status, payload = push_order({"provider": provider})

    assert status == 400, f"attendu 400 (produit bidon), reçu {status}"
    assert_item_not_found(payload)

    message = serializer_message(payload)
    assert "loyalty provider" not in message, (
        f"provider {provider!r} rejeté alors qu'il est au mapping : {message!r}"
    )


# ── AC2 : casse et espaces ──

@pytest.mark.parametrize(
    "label,provider",
    [
        ("capitalisé", "Comarch"),
        ("majuscules", "COMARCH"),
        ("majuscules (autre clé)", "SPLIO"),
        ("espaces autour", "  comarch  "),
        ("espaces + casse", "  Splio "),
    ],
)
def test_02_provider_matching_is_case_and_whitespace_insensitive(label, provider):
    """`trim().toLowerCase()` aligne le matching sur le `boost::iequals` du serveur."""
    status, payload = push_order({"provider": provider})

    assert status == 400
    assert_item_not_found(payload)

    message = serializer_message(payload)
    assert "loyalty provider" not in message, (
        f"variante {label} ({provider!r}) rejetée : {message!r}"
    )


# ── AC3 : provider inconnu → erreur nommant les valeurs acceptées ──

@pytest.mark.parametrize("provider", ["foobar", "comarchcloud", "   "])
def test_03_unknown_provider_is_rejected_and_lists_accepted_values(provider):
    """L'erreur doit nommer les 7 valeurs, dans l'ordre du mapping.

    `"   "` est inclus à dessein : après `trim()` la valeur est vide, et elle sort
    par la branche « inconnu » — pas par « missing ».
    """
    status, payload = push_order({"provider": provider})

    assert status == 400
    assert_item_not_found(payload)

    message = serializer_message(payload)
    assert f"invalid loyalty provider {provider}" in message, (
        f"message inattendu pour {provider!r} : {message!r}"
    )
    assert f"(expected one of: {EXPECTED_PROVIDER_LIST})" in message, (
        "l'erreur ne liste plus les valeurs acceptées dans l'ordre du mapping : "
        f"{message!r}"
    )


# ── AC4 : provider absent ou null → message historique ──

@pytest.mark.parametrize(
    "label,loyalty",
    [
        ("clé provider absente", {"account": {"account_id": "42"}}),
        ("bloc loyalty vide", {}),
        ("provider null", {"provider": None}),
    ],
)
def test_04_missing_provider_keeps_its_historical_error(label, loyalty):
    status, payload = push_order(loyalty)

    assert status == 400
    assert_item_not_found(payload)

    message = serializer_message(payload)
    assert "missing loyalty provider" in message, f"{label} : {message!r}"


def test_05_empty_provider_is_rejected_by_the_validator_not_the_serializer():
    """Écart acté avec l'AC4 — fige le comportement réel, pas le libellé du ticket.

    Voir la section dédiée en en-tête avant de « corriger » ce test.
    """
    status, payload = push_order({"provider": ""})

    assert status == 400
    assert isinstance(payload, dict)
    assert payload.get("name") == "BadRequest", (
        f"la chaîne vide n'est plus rejetée par le validateur : {payload!r}"
    )
    assert payload.get("data", {}).get("order.loyalty.provider") == "StringEmpty", (
        f"forme d'erreur du validateur modifiée : {payload!r}"
    )


def test_06_non_string_provider_is_rejected_by_the_validator():
    """Effet de bord du typage `Joi.string()`, hors AC mais figé pour la détection."""
    status, payload = push_order({"provider": 42})

    assert status == 400
    assert isinstance(payload, dict)
    assert payload.get("data", {}).get("order.loyalty.provider") == "StringBase", (
        f"forme d'erreur du validateur modifiée : {payload!r}"
    )


# ── AC5 : aucun bloc loyalty → aucune erreur loyalty ──

def test_07_no_loyalty_block_produces_no_loyalty_error():
    status, payload = push_order(omit_loyalty=True)

    assert status == 400
    assert_item_not_found(payload)

    message = serializer_message(payload)
    assert "loyalty" not in message.lower(), (
        f"une erreur loyalty apparaît sans bloc loyalty : {message!r}"
    )


# ── AC7 : le trafic comarch existant est inchangé ──

def test_08_existing_comarch_traffic_is_unchanged():
    """`comarch` exact : le seul cas qui passait avant le fix doit passer à l'identique."""
    status, payload = push_order({"provider": "comarch"})

    assert status == 400
    assert_item_not_found(payload)

    message = serializer_message(payload)
    assert "loyalty" not in message.lower(), (
        f"régression sur le trafic comarch historique : {message!r}"
    )
