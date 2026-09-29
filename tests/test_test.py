from __future__ import annotations

"""
Tests E2E générés automatiquement pour la collection : TEST
"""

import os
import time
import uuid
import pytest
import httpx
from dotenv import load_dotenv
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field

load_dotenv()
VERBOSITY = os.environ.get('PYTEST_VERBOSITY', '')


def deep_sort(obj):
    """Trie récursivement listes et dicts pour permettre une comparaison stable."""
    if isinstance(obj, list):
        return sorted([deep_sort(i) for i in obj], key=lambda x: str(x))
    elif isinstance(obj, dict):
        return {k: deep_sort(v) for k, v in sorted(obj.items())}
    return obj


def soft_equal(a: object, b: object) -> bool:
    """Comparaison non-stricte entre deux scalaires (int/str tolérant)."""
    if type(a) is type(b):
        return a == b
    try:
        return float(a) == float(b)
    except (ValueError, TypeError):
        return str(a) == str(b)


def deep_soft_equal(a: object, b: object) -> bool:
    """Comparaison récursive non-stricte (tri stable + soft_equal sur les feuilles)."""
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a.keys()) != set(b.keys()):
            return False
        return all(deep_soft_equal(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return False
        return all(
            deep_soft_equal(x, y)
            for x, y in zip(
                sorted(a, key=lambda x: str(x)),
                sorted(b, key=lambda x: str(x)),
            )
        )
    return soft_equal(a, b)


# ── Modèles Pydantic inférés depuis les exemples Postman ──

class GetConnectorInfogetConnectorInfoDataConfigApicontext(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    key1: str
    key2: str

class GetConnectorInfogetConnectorInfoDataConfig(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    baseURL: str
    channels: dict
    apiContext: GetConnectorInfogetConnectorInfoDataConfigApicontext
    enableDebug: bool
    autoSyncMenu: bool
    defaultChannel: str
    explicitDeliveryId: bool
    stocksNotification: bool
    readinessManagement: bool

class GetConnectorInfogetConnectorInfoData(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    """Modèle inféré depuis les exemples Postman"""
    id: int
    spaceId: int
    spaceType: str
    connectorSlug: str
    connectorEnv: str
    state: str
    config: GetConnectorInfogetConnectorInfoDataConfig
    isActive: bool
    alias: str
    flags: int
    type_: str = Field(alias="type")
    capabilities: list[str]
    logo: str
    icon: str
    beta: bool

class GetConnectorInfogetConnectorInfoResponse(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    data: GetConnectorInfogetConnectorInfoData

class PushOrderToBov2CopyResponse(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    succeeded: bool
    receipt_id: str
    receipt_sequential_id: int
    receipt_period_id: int

class CheckOrderInBov2DataItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    id: int
    connectorConfigId: int
    externalId: str
    status: str
    channel: str
    receiptId: str
    displayId: str
    createdAt: str
    receiptPeriodId: int

class CheckOrderInBov2Response(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    data: list[CheckOrderInBov2DataItem]
    limit: int
    skip: int
    total: int

class PushOrderToBov2Response(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    succeeded: bool
    receipt_id: str
    receipt_sequential_id: int
    receipt_period_id: int

class PushOrderToBov2CopyCopyResponse(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    succeeded: bool
    receipt_id: str
    receipt_sequential_id: int
    receipt_period_id: int


def get_env() -> dict:
    """Charge les variables statiques depuis .env"""
    required = [
        "installation_id",
        "bov2_host",
        "apiuser_email",
        "apiuser_token",
        "site_id",
        "slug",
        "bov2_token",
        "connector_config_id",
        "receipt_sequential_id",
        "cashpad_id",
    ]
    env = {}
    missing = []
    for key in required:
        value = os.getenv(key.upper())
        if not value:
            missing.append(key)
        else:
            env[key] = value
    if missing:
        raise EnvironmentError(f"Variables manquantes dans .env : {missing}")
    return env


@pytest.fixture(scope='module')
def ctx():
    """
    Contexte partagé entre les étapes (simule pm.collectionVariables).
    Variables dynamiques attendues en fin de séquence : []
    """
    return {}


@pytest.mark.dependency(name='test_01_get_connector_infoget_connector_info')
def test_01_get_connector_infoget_connector_info(ctx):
    """
    Étape 1 : GET CONNECTOR INFOGET CONNECTOR INFO
    Utilise : bov2_token
    Validation : GetConnectorInfogetConnectorInfoResponse
    """
    env = {**get_env(), **ctx}
    url = f"vvvv"
    headers = {
        "Content-Type": f"application/json",
        "Authorization": f"Bearer {env['bov2_token']}"
    }

    body = {'customer': {}, 'order': {'date_order': 1744043964, 'id': 'MENU_TEST_STAGING_31102025_01', 'channel': 'CHANNEL', 'nb_eaters': 1, 'comment': 'This is an order with mneu', 'table_number': 1, 'items': [{'name': 'Menu Big Boss', 'pos_id': '80d7f8cf-0a4c-4374-96ea-a74978cd1011', 'price': 10.9, 'extras': None, 'quantity': 1, 'children': [{'name': 'Burger Big Boss', 'price': 0, 'extras': [], 'pos_id': '076982e6-04fa-4d94-adf2-00bbb1817907', 'quantity': 1}, {'name': 'Capri-sun', 'price': 0, 'extras': [], 'pos_id': '501e9c4b-ebcd-4636-b6d6-e475d69f7e78', 'quantity': 1}, {'name': 'Crepe Nutella®', 'price': 0, 'extras': [], 'pos_id': '3544b353-71c7-4c1d-887e-fff35f15597f', 'quantity': 1}]}], 'payments': []}}
    # order.id généré dynamiquement pour éviter les doublons
    body['order']['id'] = f"{env['slug']}_{str(uuid.uuid4())}"
    # date_order généré dynamiquement avec la date actuelle
    body['order']['date_order'] = int(time.time())

    response = httpx.get(url, headers=headers, timeout=30)

    # Assertions de base
    assert response.status_code in (200, 201), (
        f"[GET CONNECTOR INFOGET CONNECTOR INFO] Statut inattendu: {response.status_code}\n{response.text}"
    )
    data = response.json()
    assert data is not None

    # Stockage de la réponse pour les assertions cross-step
    responses = ctx.setdefault('_responses', {})
    responses['GET CONNECTOR INFOGET CONNECTOR INFO'] = data

    # Validation Pydantic du schéma de réponse
    validated = GetConnectorInfogetConnectorInfoResponse.model_validate(data)
    assert validated is not None, (
        f"[GET CONNECTOR INFOGET CONNECTOR INFO] Validation Pydantic échouée: {data}"
    )

    # ── Règles métier ──
    # Règle métier (YAML) : jbhggbgblgbljb
    assert len(data["data"]) == 1, (
        f"jbhggbgblgbljb — longueur: {len(data["data"])}, attendu: 1"
    )

    # ── Assertions cross-step ──
    if 'CHECK ORDER IN BOV2' in responses:
        _src = responses["CHECK ORDER IN BOV2"]["data"]
        _tgt = responses["GET CONNECTOR INFOGET CONNECTOR INFO"]["data"]
        assert deep_sort(_src) == deep_sort(_tgt), (
            f"Cross-step assertion failed (CHECK ORDER IN BOV2 → GET CONNECTOR INFOGET CONNECTOR INFO) — src={_src!r}, tgt={_tgt!r}"
        )



@pytest.mark.dependency(name='test_02_push_order_to_bov2_copy')
def test_02_push_order_to_bov2_copy(ctx):
    """
    Étape 2 : PUSH ORDER TO BOV2_copy
    Validation : PushOrderToBov2CopyResponse
    """
    env = {**get_env(), **ctx}
    url = f"{{{"
    headers = {
        "Content-Type": f"application/json"
    }

    body = {'customer': {}, 'order': {'date_order': 1744043964, 'id': 'ID_d__', 'channel': 'CHANNEL', 'nb_eaters': 1, 'comment': 'This is a simple order', 'table_number': 1, 'items': [{'pos_id': '12ac180d-9ec1-4741-89ab-9cfb3eb7d81e', 'price': 7.0, 'quantity': 1, 'production_level': 0}], 'payments': []}}
    # order.id généré dynamiquement pour éviter les doublons
    body['order']['id'] = f"{env['slug']}_{str(uuid.uuid4())}"
    # date_order généré dynamiquement avec la date actuelle
    body['order']['date_order'] = int(time.time())

    response = httpx.post(url, headers=headers, json=body, timeout=30)

    # Assertions de base
    assert response.status_code in (200, 201), (
        f"[PUSH ORDER TO BOV2_copy] Statut inattendu: {response.status_code}\n{response.text}"
    )
    data = response.json()
    assert data is not None

    # Stockage de la réponse pour les assertions cross-step
    responses = ctx.setdefault('_responses', {})
    responses['PUSH ORDER TO BOV2_copy'] = data

    # Validation Pydantic du schéma de réponse
    validated = PushOrderToBov2CopyResponse.model_validate(data)
    assert validated is not None, (
        f"[PUSH ORDER TO BOV2_copy] Validation Pydantic échouée: {data}"
    )

    # ── Assertions cross-step ──
    if 'efefefefe' in responses:
        _src = responses["efefefefe"]["data"]
        _tgt = responses["PUSH ORDER TO BOV2_copy"]["receipt_id"]
        assert deep_sort(_src) == deep_sort(_tgt), (
            f"Cross-step assertion failed (efefefefe → PUSH ORDER TO BOV2_copy) — src={_src!r}, tgt={_tgt!r}"
        )



@pytest.mark.dependency(name='test_03_check_order_in_bov2')
def test_03_check_order_in_bov2(ctx):
    """
    Étape 3 : CHECK ORDER IN BOV2
    Utilise : bov2_host, site_id, bov2_token, receipt_sequential_id, connector_config_id
    Validation : CheckOrderInBov2Response
    """
    env = {**get_env(), **ctx}
    url = f"{env['bov2_host']}/p/partners/api/2/site/{env['site_id']}/connector/{env['connector_config_id']}/orders?limit=10&sort[column]=createdAt&sort[type]=desc&search={env['receipt_sequential_id']}&skip=0"
    headers = {
        "Content-Type": f"application/json",
        "Authorization": f"Bearer {env['bov2_token']}"
    }

    body = {'customer': {}, 'order': {'date_order': 1744043964, 'id': 'MENU_TEST_STAGING_31102025_01', 'channel': 'CHANNEL', 'nb_eaters': 1, 'comment': 'This is an order with mneu', 'table_number': 1, 'items': [{'name': 'Menu Big Boss', 'pos_id': '80d7f8cf-0a4c-4374-96ea-a74978cd1011', 'price': 10.9, 'extras': None, 'quantity': 1, 'children': [{'name': 'Burger Big Boss', 'price': 0, 'extras': [], 'pos_id': '076982e6-04fa-4d94-adf2-00bbb1817907', 'quantity': 1}, {'name': 'Capri-sun', 'price': 0, 'extras': [], 'pos_id': '501e9c4b-ebcd-4636-b6d6-e475d69f7e78', 'quantity': 1}, {'name': 'Crepe Nutella®', 'price': 0, 'extras': [], 'pos_id': '3544b353-71c7-4c1d-887e-fff35f15597f', 'quantity': 1}]}], 'payments': []}}
    # order.id généré dynamiquement pour éviter les doublons
    body['order']['id'] = f"{env['slug']}_{str(uuid.uuid4())}"
    # date_order généré dynamiquement avec la date actuelle
    body['order']['date_order'] = int(time.time())

    response = httpx.get(url, headers=headers, timeout=30)

    # Assertions de base
    assert response.status_code in (200, 201), (
        f"[CHECK ORDER IN BOV2] Statut inattendu: {response.status_code}\n{response.text}"
    )
    data = response.json()
    assert data is not None

    # Stockage de la réponse pour les assertions cross-step
    responses = ctx.setdefault('_responses', {})
    responses['CHECK ORDER IN BOV2'] = data

    # Validation Pydantic du schéma de réponse
    validated = CheckOrderInBov2Response.model_validate(data)
    assert validated is not None, (
        f"[CHECK ORDER IN BOV2] Validation Pydantic échouée: {data}"
    )

    # ── Règles métier ──
    # Règle métier (auto-détectée) : search={{receipt_sequential_id}} → doit apparaître dans data[*].receiptId
    _rule_data_receiptId = [str(item['receiptId']) for item in data['data']]
    _search_receipt_sequential_id = str(ctx['receipt_sequential_id'])
    assert _search_receipt_sequential_id in _rule_data_receiptId, (
        f'receipt_sequential_id={_search_receipt_sequential_id} introuvable dans data[*].receiptId: {_rule_data_receiptId}'
    )
    assert data["total"] >= 1, (
        f'Aucun résultat retourné pour search={_search_receipt_sequential_id}'
    )



@pytest.mark.dependency(name='test_04_push_order_to_bov2')
def test_04_push_order_to_bov2(ctx):
    """
    Étape 4 : PUSH ORDER TO BOV2
    Utilise : apiuser_token, apiuser_email, installation_id, bov2_host
    Validation : PushOrderToBov2Response
    """
    env = {**get_env(), **ctx}
    url = f"{env['bov2_host']}/api/orders/v1/{env['installation_id']}/cashpad/push_order_sync?apiuser_email={env['apiuser_email']}&apiuser_token={env['apiuser_token']}"
    headers = {
        "Content-Type": f"application/json"
    }

    body = {'customer': {}, 'order': {'date_order': 1744043964, 'id': 'ID_d__', 'channel': 'CHANNEL', 'nb_eaters': 1, 'comment': 'This is a simple order', 'table_number': 1, 'items': [{'pos_id': '12ac180d-9ec1-4741-89ab-9cfb3eb7d81e', 'price': 7.0, 'quantity': 1, 'production_level': 0}], 'payments': []}}
    # order.id généré dynamiquement pour éviter les doublons
    body['order']['id'] = f"{env['slug']}_{str(uuid.uuid4())}"
    # date_order généré dynamiquement avec la date actuelle
    body['order']['date_order'] = int(time.time())

    response = httpx.post(url, headers=headers, json=body, timeout=30)

    # Assertions de base
    assert response.status_code in (200, 201, 401), (
        f"[PUSH ORDER TO BOV2] Statut inattendu: {response.status_code}\n{response.text}"
    )
    data = response.json()
    assert data is not None

    # Stockage de la réponse pour les assertions cross-step
    responses = ctx.setdefault('_responses', {})
    responses['PUSH ORDER TO BOV2'] = data

    # Validation Pydantic du schéma de réponse
    validated = PushOrderToBov2Response.model_validate(data)
    assert validated is not None, (
        f"[PUSH ORDER TO BOV2] Validation Pydantic échouée: {data}"
    )

    # ── Règles métier ──

    # ── Assertions cross-step ──
    if 'efefefefe' in responses:
        _src = responses["efefefefe"]["data"]
        _tgt = responses["PUSH ORDER TO BOV2"]["receipt_id"]
        assert deep_sort(_src) == deep_sort(_tgt), (
            f"Cross-step assertion failed (efefefefe → PUSH ORDER TO BOV2) — src={_src!r}, tgt={_tgt!r}"
        )



@pytest.mark.dependency(name='test_05_push_order_to_bov2_copy_copy')
def test_05_push_order_to_bov2_copy_copy(ctx):
    """
    Étape 5 : PUSH ORDER TO BOV2_copy_copy
    Utilise : site_id
    Validation : PushOrderToBov2CopyCopyResponse
    """
    env = {**get_env(), **ctx}
    url = f"{env['site_id']}/efefefefe{env['site_id']}sdsdsds"
    headers = {
        "Content-Type": f"application/json"
    }

    body = {'customer': {}, 'order': {'date_order': 1744043964, 'id': 'ID_d__', 'channel': 'CHANNEL', 'nb_eaters': 1, 'comment': 'This is a simple order', 'table_number': 1, 'items': [{'pos_id': '12ac180d-9ec1-4741-89ab-9cfb3eb7d81e', 'price': 7.0, 'quantity': 1, 'production_level': 0}], 'payments': []}}
    # order.id généré dynamiquement pour éviter les doublons
    body['order']['id'] = f"{env['slug']}_{str(uuid.uuid4())}"
    # date_order généré dynamiquement avec la date actuelle
    body['order']['date_order'] = int(time.time())

    response = httpx.post(url, headers=headers, json=body, timeout=30)

    # Assertions de base
    assert response.status_code in (200, 201), (
        f"[PUSH ORDER TO BOV2_copy_copy] Statut inattendu: {response.status_code}\n{response.text}"
    )
    data = response.json()
    assert data is not None

    # Stockage de la réponse pour les assertions cross-step
    responses = ctx.setdefault('_responses', {})
    responses['PUSH ORDER TO BOV2_copy_copy'] = data

    # Validation Pydantic du schéma de réponse
    validated = PushOrderToBov2CopyCopyResponse.model_validate(data)
    assert validated is not None, (
        f"[PUSH ORDER TO BOV2_copy_copy] Validation Pydantic échouée: {data}"
    )

    # ── Assertions cross-step ──
    if 'efefefefe' in responses:
        _src = responses["efefefefe"]["data"]
        _tgt = responses["PUSH ORDER TO BOV2_copy_copy"]["receipt_id"]
        assert deep_sort(_src) == deep_sort(_tgt), (
            f"Cross-step assertion failed (efefefefe → PUSH ORDER TO BOV2_copy_copy) — src={_src!r}, tgt={_tgt!r}"
        )



@pytest.mark.dependency(depends=["test_01_get_connector_infoget_connector_info", "test_02_push_order_to_bov2_copy", "test_03_check_order_in_bov2", "test_04_push_order_to_bov2", "test_05_push_order_to_bov2_copy_copy"])
def test_consistency(ctx):
    """Vérifie que toutes les variables dynamiques ont bien été propagées"""
    expected = [
    ]
    for var in expected:
        assert ctx.get(var), (
            f"Variable '{var}' manquante ou vide en fin de séquence"
        )
    if VERBOSITY != "-q":
        print("\n✅ Consistance OK - toutes les variables dynamiques sont présentes")
