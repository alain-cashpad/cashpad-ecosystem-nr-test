from __future__ import annotations

"""
Tests E2E générés automatiquement pour la collection : CP_DIGITAL_MENU_COMPARE
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

class GetDigitalMenuFromBov1DataProductcategoriesItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    id: str
    external_id: str
    label: str
    default_production_level: int

class GetDigitalMenuFromBov1DataOptionsContentItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    id: str
    external_id: Optional[Any] = None
    label: str
    extra: list
    product: str

class GetDigitalMenuFromBov1DataOptionsItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    id: str
    external_id: Optional[Any] = None
    label: str
    min_qty: int
    max_qty: int
    allow_multiples: bool
    content: list[GetDigitalMenuFromBov1DataOptionsContentItem]

class GetDigitalMenuFromBov1DataContainersItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    id: str
    external_id: Optional[Any] = None
    label: str
    category: str
    enabled: bool
    description: Optional[Any] = None
    content: list[str]

class GetDigitalMenuFromBov1DataProductsPricesItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    price: int
    pricing: str
    id: str
    external_id: str
    tax_rate: int

class GetDigitalMenuFromBov1DataProductsRulesScheduling(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    start: str
    end: str
    weekdays: list[dict]

class GetDigitalMenuFromBov1DataProductsRulesCalendar(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    """Modèle inféré depuis les exemples Postman"""
    from_: str = Field(alias="from")
    to: str

class GetDigitalMenuFromBov1DataProductsRules(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    scheduling: GetDigitalMenuFromBov1DataProductsRulesScheduling
    calendar: GetDigitalMenuFromBov1DataProductsRulesCalendar

class GetDigitalMenuFromBov1DataProductsItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    """Modèle inféré depuis les exemples Postman"""
    id: str
    external_id: Optional[Any] = None
    label: str
    category: str
    prices: list[GetDigitalMenuFromBov1DataProductsPricesItem]
    menu_only: bool
    enabled: bool
    description: Optional[Any] = None
    type_: str = Field(alias="type")
    options: list[str]
    rules: GetDigitalMenuFromBov1DataProductsRules

class GetDigitalMenuFromBov1DataMenusPricesItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    price: int
    pricing: str
    id: str
    external_id: str
    tax_rate: int

class GetDigitalMenuFromBov1DataMenusItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    id: str
    external_id: Optional[Any] = None
    label: str
    category: str
    prices: list[GetDigitalMenuFromBov1DataMenusPricesItem]
    enabled: bool
    description: Optional[Any] = None
    content: list

class GetDigitalMenuFromBov1DataLayoutsChildrenItemsItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    """Modèle inféré depuis les exemples Postman"""
    id: str
    label: str
    type_: str = Field(alias="type")

class GetDigitalMenuFromBov1DataLayoutsChildrenItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    id: str
    label: str
    items: list[GetDigitalMenuFromBov1DataLayoutsChildrenItemsItem]
    children: list

class GetDigitalMenuFromBov1DataLayoutsItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    id: str
    label: str
    children: list[GetDigitalMenuFromBov1DataLayoutsChildrenItem]

class GetDigitalMenuFromBov1DataRatemakingsSchedulingWeekdaysItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    index: int
    day: str

class GetDigitalMenuFromBov1DataRatemakingsScheduling(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    start: str
    end: str
    weekdays: list[GetDigitalMenuFromBov1DataRatemakingsSchedulingWeekdaysItem]

class GetDigitalMenuFromBov1DataRatemakingsItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    id: str
    external_id: str
    label: str
    scheduling: GetDigitalMenuFromBov1DataRatemakingsScheduling

class GetDigitalMenuFromBov1Data(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    version: int
    productcategories: list[GetDigitalMenuFromBov1DataProductcategoriesItem]
    options: list[GetDigitalMenuFromBov1DataOptionsItem]
    containers: list[GetDigitalMenuFromBov1DataContainersItem]
    products: list[GetDigitalMenuFromBov1DataProductsItem]
    menus: list[GetDigitalMenuFromBov1DataMenusItem]
    layouts: list[GetDigitalMenuFromBov1DataLayoutsItem]
    ratemakings: list[GetDigitalMenuFromBov1DataRatemakingsItem]

class GetDigitalMenuFromBov1Response(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    succeeded: bool
    version: str
    data: GetDigitalMenuFromBov1Data

class GetDigitalMenuFromBov2DataProductcategoriesItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    id: str
    external_id: str
    label: str
    default_production_level: int

class GetDigitalMenuFromBov2DataOptionsContentItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    id: str
    label: str
    external_id: Optional[Any] = None
    extra: list
    product: str

class GetDigitalMenuFromBov2DataOptionsItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    id: str
    external_id: Optional[Any] = None
    label: str
    min_qty: int
    max_qty: int
    allow_multiples: bool
    content: list[GetDigitalMenuFromBov2DataOptionsContentItem]

class GetDigitalMenuFromBov2DataContainersItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    id: str
    external_id: Optional[Any] = None
    label: str
    category: str
    enabled: bool
    description: Optional[Any] = None
    content: list[str]

class GetDigitalMenuFromBov2DataProductsPricesItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    price: int
    pricing: str
    id: str
    external_id: str
    tax_rate: int

class GetDigitalMenuFromBov2DataProductsRulesScheduling(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    start: str
    end: str
    weekdays: list[dict]

class GetDigitalMenuFromBov2DataProductsRulesCalendar(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    """Modèle inféré depuis les exemples Postman"""
    from_: str = Field(alias="from")
    to: str

class GetDigitalMenuFromBov2DataProductsRules(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    scheduling: GetDigitalMenuFromBov2DataProductsRulesScheduling
    calendar: GetDigitalMenuFromBov2DataProductsRulesCalendar

class GetDigitalMenuFromBov2DataProductsItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    """Modèle inféré depuis les exemples Postman"""
    id: str
    external_id: Optional[Any] = None
    label: str
    category: str
    prices: list[GetDigitalMenuFromBov2DataProductsPricesItem]
    menu_only: bool
    enabled: bool
    description: Optional[Any] = None
    type_: str = Field(alias="type")
    options: list[str]
    rules: GetDigitalMenuFromBov2DataProductsRules

class GetDigitalMenuFromBov2DataMenusPricesItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    price: int
    pricing: str
    id: str
    external_id: str
    tax_rate: int

class GetDigitalMenuFromBov2DataMenusItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    id: str
    external_id: Optional[Any] = None
    label: str
    category: str
    prices: list[GetDigitalMenuFromBov2DataMenusPricesItem]
    enabled: bool
    description: Optional[Any] = None
    content: list

class GetDigitalMenuFromBov2DataLayoutsChildrenItemsItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    """Modèle inféré depuis les exemples Postman"""
    id: str
    label: str
    type_: str = Field(alias="type")

class GetDigitalMenuFromBov2DataLayoutsChildrenItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    id: str
    label: str
    items: list[GetDigitalMenuFromBov2DataLayoutsChildrenItemsItem]
    children: list

class GetDigitalMenuFromBov2DataLayoutsItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    id: str
    label: str
    children: list[GetDigitalMenuFromBov2DataLayoutsChildrenItem]

class GetDigitalMenuFromBov2DataRatemakingsSchedulingWeekdaysItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    index: int
    day: str

class GetDigitalMenuFromBov2DataRatemakingsScheduling(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    start: str
    end: str
    weekdays: list[GetDigitalMenuFromBov2DataRatemakingsSchedulingWeekdaysItem]

class GetDigitalMenuFromBov2DataRatemakingsItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    id: str
    external_id: str
    label: str
    scheduling: GetDigitalMenuFromBov2DataRatemakingsScheduling

class GetDigitalMenuFromBov2Data(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    version: int
    productcategories: list[GetDigitalMenuFromBov2DataProductcategoriesItem]
    options: list[GetDigitalMenuFromBov2DataOptionsItem]
    containers: list[GetDigitalMenuFromBov2DataContainersItem]
    products: list[GetDigitalMenuFromBov2DataProductsItem]
    menus: list[GetDigitalMenuFromBov2DataMenusItem]
    layouts: list[GetDigitalMenuFromBov2DataLayoutsItem]
    ratemakings: list[GetDigitalMenuFromBov2DataRatemakingsItem]

class GetDigitalMenuFromBov2Response(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    version: str
    succeeded: bool
    data: GetDigitalMenuFromBov2Data


def get_env() -> dict:
    """Charge les variables statiques depuis .env"""
    required = [
        "installation_id",
        "bov1_host",
        "bov2_host",
        "apiuser_email",
        "apiuser_token",
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


@pytest.mark.dependency(name='test_01_get_digital_menu_from_bov1')
def test_01_get_digital_menu_from_bov1(ctx):
    """
    Étape 1 : GET DIGITAL MENU FROM BOV1
    Utilise : installation_id, apiuser_token, apiuser_email, bov1_host
    Validation : GetDigitalMenuFromBov1Response
    """
    env = {**get_env(), **ctx}
    url = f"{env['bov1_host']}/api/menus/v2/{env['installation_id']}/digital_menu?apiuser_email={env['apiuser_email']}&apiuser_token={env['apiuser_token']}"
    headers = {

    }

    response = httpx.get(url, headers=headers, timeout=30)

    # Assertions de base
    assert response.status_code in (200, 201), (
        f"[GET DIGITAL MENU FROM BOV1] Statut inattendu: {response.status_code}\n{response.text}"
    )
    data = response.json()
    assert data is not None

    # Stockage de la réponse pour les assertions cross-step
    responses = ctx.setdefault('_responses', {})
    responses['GET DIGITAL MENU FROM BOV1'] = data

    # ── Règles métier ──
    # Règle métier (YAML) : Règle métier pour GET DIGITAL MENU FROM BOV1
    assert data["succeeded"] == True, (
        f"Règle métier pour GET DIGITAL MENU FROM BOV1 — valeur: {data["succeeded"]}"
    )



@pytest.mark.dependency(name='test_02_get_digital_menu_from_bov2')
def test_02_get_digital_menu_from_bov2(ctx):
    """
    Étape 2 : GET DIGITAL MENU FROM BOV2
    Utilise : installation_id, apiuser_token, bov2_host, apiuser_email
    Validation : GetDigitalMenuFromBov2Response
    """
    env = {**get_env(), **ctx}
    url = f"{env['bov2_host']}/api/menus/v2/{env['installation_id']}/digital_menu?apiuser_email={env['apiuser_email']}&apiuser_token={env['apiuser_token']}"
    headers = {

    }

    response = httpx.get(url, headers=headers, timeout=30)

    # Assertions de base
    assert response.status_code in (200, 201), (
        f"[GET DIGITAL MENU FROM BOV2] Statut inattendu: {response.status_code}\n{response.text}"
    )
    data = response.json()
    assert data is not None

    # Stockage de la réponse pour les assertions cross-step
    responses = ctx.setdefault('_responses', {})
    responses['GET DIGITAL MENU FROM BOV2'] = data

    # ── Règles métier ──
    # Règle métier (YAML) : Règle métier pour GET DIGITAL MENU FROM BOV2
    assert data["succeeded"] == True, (
        f"Règle métier pour GET DIGITAL MENU FROM BOV2 — valeur: {data["succeeded"]}"
    )

    # ── Assertions cross-step ──
    if 'GET DIGITAL MENU FROM BOV1' in responses:
        _src = responses["GET DIGITAL MENU FROM BOV1"]["data"]["version"]
        _tgt = responses["GET DIGITAL MENU FROM BOV2"]["data"]["version"]
        assert deep_sort(_src) == deep_sort(_tgt), (
            f"La version du menu n'est pas la même entre le BOV1 et le BOV2 — src={_src!r}, tgt={_tgt!r}"
        )
    if 'GET DIGITAL MENU FROM BOV1' in responses:
        _src = responses["GET DIGITAL MENU FROM BOV1"]["data"]["productcategories"]
        _tgt = responses["GET DIGITAL MENU FROM BOV2"]["data"]["productcategories"]
        assert len(deep_sort(_src)) == len(deep_sort(_tgt)), (
            f"Le nombre de productcategories n'est pas le même entre le BOV1 et le BOV2 — src={_src!r}, tgt={_tgt!r}"
        )
    if 'GET DIGITAL MENU FROM BOV1' in responses:
        _src = responses["GET DIGITAL MENU FROM BOV1"]["data"]["options"]
        _tgt = responses["GET DIGITAL MENU FROM BOV2"]["data"]["options"]
        assert len(deep_sort(_src)) == len(deep_sort(_tgt)), (
            f"Le nombre d'options n'est pas le même entre le BOV1 et le BOV2 — src={_src!r}, tgt={_tgt!r}"
        )
    if 'GET DIGITAL MENU FROM BOV1' in responses:
        _src = responses["GET DIGITAL MENU FROM BOV1"]["data"]["containers"]
        _tgt = responses["GET DIGITAL MENU FROM BOV2"]["data"]["containers"]
        assert len(deep_sort(_src)) == len(deep_sort(_tgt)), (
            f"Le nombre de containers n'est pas le même entre le BOV1 et le BOV2 — src={_src!r}, tgt={_tgt!r}"
        )
    if 'GET DIGITAL MENU FROM BOV1' in responses:
        _src = responses["GET DIGITAL MENU FROM BOV1"]["data"]["products"]
        _tgt = responses["GET DIGITAL MENU FROM BOV2"]["data"]["products"]
        assert len(deep_sort(_src)) == len(deep_sort(_tgt)), (
            f"Le nombre de products n'est pas le même entre le BOV1 et le BOV2 — src={_src!r}, tgt={_tgt!r}"
        )



@pytest.mark.dependency(depends=["test_01_get_digital_menu_from_bov1", "test_02_get_digital_menu_from_bov2"])
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
