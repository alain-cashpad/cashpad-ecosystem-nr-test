from __future__ import annotations

"""
Tests E2E générés automatiquement pour la collection : CP_PARTNERS_ORDER_SIMPLE
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

class PushOrderToBov2Response(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    succeeded: bool
    receipt_id: str
    receipt_sequential_id: int
    receipt_period_id: int

class GetConnectorInfoDataConfigApicontext(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    key1: str
    key2: str

class GetConnectorInfoDataConfig(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    baseURL: str
    channels: dict
    apiContext: GetConnectorInfoDataConfigApicontext
    enableDebug: bool
    autoSyncMenu: bool
    defaultChannel: str
    explicitDeliveryId: bool
    stocksNotification: bool
    readinessManagement: bool

class GetConnectorInfoData(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    """Modèle inféré depuis les exemples Postman"""
    id: int
    spaceId: int
    spaceType: str
    connectorSlug: str
    connectorEnv: str
    state: str
    config: GetConnectorInfoDataConfig
    isActive: bool
    alias: str
    flags: int
    type_: str = Field(alias="type")
    capabilities: list[str]
    logo: str
    icon: str
    beta: bool

class GetConnectorInfoResponse(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    data: GetConnectorInfoData

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

class CheckOrderOnDeviceReceiptItemsItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    addons: list
    displayOrder: int
    flags: int
    id: str
    level: int
    priceInclTaxes: int
    product: str
    qty: int
    qtyBilled: int
    qtyPrinted: int
    taxRate1: int
    valueInclTaxes: int

class CheckOrderOnDeviceReceipt(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    amountPaid: int
    amountTotal: int
    cancelled: bool
    consumptionMode: str
    contentVersion: int
    currentLevel: int
    customData: str
    dateCreated: str
    dateLastOpened: str
    dateLastProductionAction: str
    datePickup: str
    deliveryId: str
    documents: list
    externalOrder: str
    flags: int
    id: str
    items: list[CheckOrderOnDeviceReceiptItemsItem]
    location: str
    locationNumber: int
    manualRateMaking: str
    maxLevel: int
    nbReopening: int
    nbSeats: int
    note: str
    owner: str
    payments: list
    periodId: int
    sequentialId: int
    version: int

class CheckOrderOnDeviceResponse(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    receipt: CheckOrderOnDeviceReceipt
    schemaVersion: int
    succeeded: bool


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
    Variables dynamiques attendues en fin de séquence : ['connector_config_id', 'receipt_sequential_id']
    """
    return {}


@pytest.mark.dependency(name='test_01_push_order_to_bov2')
def test_01_push_order_to_bov2(ctx):
    """
    Étape 1 : PUSH ORDER TO BOV2
    Utilise : apiuser_token, installation_id, bov2_host, apiuser_email
    Extrait pour la suite : receipt_sequential_id
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
    assert response.status_code in (200, 201), (
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
    # Règle métier (YAML) : Règle métier pour PUSH ORDER TO BOV2
    assert data["succeeded"] == True, (
        f"Règle métier pour PUSH ORDER TO BOV2 — valeur: {data["succeeded"]}"
    )

    # Extraction des variables pour les étapes suivantes
    try:
        receipt_sequential_id = data['receipt_sequential_id']
    except (KeyError, TypeError):
        receipt_sequential_id = None
    assert receipt_sequential_id is not None, (
        f"[PUSH ORDER TO BOV2] 'receipt_sequential_id' introuvable via data['receipt_sequential_id']: {data}"
    )
    ctx['receipt_sequential_id'] = receipt_sequential_id
    if VERBOSITY in ("-v", "-vv"):
        print(f"  → receipt_sequential_id = {receipt_sequential_id}")



@pytest.mark.dependency(name='test_02_get_connector_info')
def test_02_get_connector_info(ctx):
    """
    Étape 2 : GET CONNECTOR INFO
    Utilise : site_id, slug, bov2_host, bov2_token
    Extrait pour la suite : connector_config_id
    Validation : GetConnectorInfoResponse
    """
    env = {**get_env(), **ctx}
    url = f"{env['bov2_host']}/p/partners/api/1/site/{env['site_id']}/connector-configs/{env['slug']}"
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
        f"[GET CONNECTOR INFO] Statut inattendu: {response.status_code}\n{response.text}"
    )
    data = response.json()
    assert data is not None

    # Stockage de la réponse pour les assertions cross-step
    responses = ctx.setdefault('_responses', {})
    responses['GET CONNECTOR INFO'] = data

    # Validation Pydantic du schéma de réponse
    validated = GetConnectorInfoResponse.model_validate(data)
    assert validated is not None, (
        f"[GET CONNECTOR INFO] Validation Pydantic échouée: {data}"
    )

    # ── Règles métier ──
    # Règle métier (YAML) : Règle métier pour GET CONNECTOR INFO
    assert data["data"]["alias"] == env["installation_id"], (
        f"Règle métier pour GET CONNECTOR INFO — valeur: {data["data"]["alias"]}"
    )

    # Extraction des variables pour les étapes suivantes
    try:
        connector_config_id = data['data']['id']
    except (KeyError, TypeError):
        connector_config_id = None
    assert connector_config_id is not None, (
        f"[GET CONNECTOR INFO] 'connector_config_id' introuvable via data['data']['id']: {data}"
    )
    ctx['connector_config_id'] = connector_config_id
    if VERBOSITY in ("-v", "-vv"):
        print(f"  → connector_config_id = {connector_config_id}")



@pytest.mark.dependency(name='test_03_check_order_in_bov2')
@pytest.mark.dependency(depends=["test_01_push_order_to_bov2", "test_02_get_connector_info"])
def test_03_check_order_in_bov2(ctx):
    """
    Étape 3 : CHECK ORDER IN BOV2
    Utilise : bov2_host, bov2_token, site_id, receipt_sequential_id, connector_config_id
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
    # Règle métier (YAML) : Au moins une commande doit être retournée
    assert data["total"] >= 1, (
        f"Au moins une commande doit être retournée — valeur: {data["total"]}"
    )
    # Règle métier (auto-détectée) : search={{receipt_sequential_id}} → doit apparaître dans data[*].receiptId
    _rule_data_receiptId = [str(item['receiptId']) for item in data['data']]
    _search_receipt_sequential_id = str(ctx['receipt_sequential_id'])
    assert _search_receipt_sequential_id in _rule_data_receiptId, (
        f'receipt_sequential_id={_search_receipt_sequential_id} introuvable dans data[*].receiptId: {_rule_data_receiptId}'
    )
    assert data["total"] >= 1, (
        f'Aucun résultat retourné pour search={_search_receipt_sequential_id}'
    )

    # ── Assertions cross-step ──
    if 'PUSH ORDER TO BOV2' in responses:
        _src = responses["PUSH ORDER TO BOV2"]["receipt_sequential_id"]
        _tgt = [item["receiptId"] for item in responses["CHECK ORDER IN BOV2"]["data"]]
        assert any(soft_equal(_src, _x) for _x in _tgt), (
            f"La nouvelle commande n'est pas présente dans la liste des orders sur le BOV2 — src={_src!r}, tgt={_tgt!r}"
        )



@pytest.mark.dependency(name='test_04_check_order_on_device')
@pytest.mark.dependency(depends=["test_01_push_order_to_bov2"])
def test_04_check_order_on_device(ctx):
    """
    Étape 4 : CHECK ORDER ON DEVICE
    Utilise : cashpad_id, receipt_sequential_id
    Validation : CheckOrderOnDeviceResponse
    """
    env = {**get_env(), **ctx}
    url = f"http://{env['cashpad_id']}.vpn.osilia.com:9091/reports/get_receipt_content?sequential_id={env['receipt_sequential_id']}"
    headers = {

    }

    response = httpx.get(url, headers=headers, timeout=30)

    # Assertions de base
    assert response.status_code in (200, 201), (
        f"[CHECK ORDER ON DEVICE] Statut inattendu: {response.status_code}\n{response.text}"
    )
    data = response.json()
    assert data is not None

    # Stockage de la réponse pour les assertions cross-step
    responses = ctx.setdefault('_responses', {})
    responses['CHECK ORDER ON DEVICE'] = data

    # Validation Pydantic du schéma de réponse
    validated = CheckOrderOnDeviceResponse.model_validate(data)
    assert validated is not None, (
        f"[CHECK ORDER ON DEVICE] Validation Pydantic échouée: {data}"
    )

    # ── Règles métier ──

    # ── Assertions cross-step ──
    if 'PUSH ORDER TO BOV2' in responses:
        _src = responses["PUSH ORDER TO BOV2"]["receipt_sequential_id"]
        _tgt = responses["CHECK ORDER ON DEVICE"]["receipt"]["sequentialId"]
        assert deep_soft_equal(_src, _tgt), (
            f"La commande n'est pas présente sur le device cashpad — src={_src!r}, tgt={_tgt!r}"
        )



@pytest.mark.dependency(depends=["test_01_push_order_to_bov2", "test_02_get_connector_info", "test_03_check_order_in_bov2", "test_04_check_order_on_device"])
def test_consistency(ctx):
    """Vérifie que toutes les variables dynamiques ont bien été propagées"""
    expected = [
        "connector_config_id",
        "receipt_sequential_id",
    ]
    for var in expected:
        assert ctx.get(var), (
            f"Variable '{var}' manquante ou vide en fin de séquence"
        )
    if VERBOSITY != "-q":
        print("\n✅ Consistance OK - toutes les variables dynamiques sont présentes")
