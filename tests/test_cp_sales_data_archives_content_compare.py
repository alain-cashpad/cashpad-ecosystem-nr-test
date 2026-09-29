from __future__ import annotations

"""
Tests E2E générés automatiquement pour la collection : CP_SALES_DATA_ARCHIVES_CONTENT_COMPARE
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

class GetArchivesContentFromBov1DataSalesTaxesItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    rate: int
    amount: int
    total_without_taxes: int
    total_with_taxes: int
    external_id: str

class GetArchivesContentFromBov1DataSales(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    total_with_taxes: int
    total_without_taxes: int
    nb_receipts: int
    nb_cancelled_receipts: int
    nb_seats: int
    taxes: list[GetArchivesContentFromBov1DataSalesTaxesItem]

class GetArchivesContentFromBov1DataStaff(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    total_with_taxes: int
    total_without_taxes: int
    nb_receipts: int
    nb_cancelled_receipts: int
    nb_seats: int
    taxes: list

class GetArchivesContentFromBov1DataTotalTaxesItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    rate: int
    amount: int
    total_without_taxes: int
    total_with_taxes: int
    external_id: str

class GetArchivesContentFromBov1DataTotal(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    total_with_taxes: int
    total_without_taxes: int
    nb_receipts: int
    nb_cancelled_receipts: int
    nb_seats: int
    taxes: list[GetArchivesContentFromBov1DataTotalTaxesItem]

class GetArchivesContentFromBov1DataPaymentsPaymentmethod(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    id: str
    name: str

class GetArchivesContentFromBov1DataPaymentsItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    paymentmethod: GetArchivesContentFromBov1DataPaymentsPaymentmethod
    amount: int
    nb_operations: int

class GetArchivesContentFromBov1DataReceiptsOwner(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    id: str
    name: str

class GetArchivesContentFromBov1DataReceiptsLocation(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    id: str
    external_id: str
    name: str

class GetArchivesContentFromBov1DataReceiptsConsumptionmode(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    id: str
    external_id: str
    name: str

class GetArchivesContentFromBov1DataReceiptsCustomer(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    id: str
    name: str

class GetArchivesContentFromBov1DataReceiptsPaymentsUser(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    id: str
    name: str

class GetArchivesContentFromBov1DataReceiptsPaymentsPaymentmethod(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    id: str
    name: str

class GetArchivesContentFromBov1DataReceiptsPaymentsItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    amount: int
    date: str
    user: GetArchivesContentFromBov1DataReceiptsPaymentsUser
    paymentmethod: GetArchivesContentFromBov1DataReceiptsPaymentsPaymentmethod

class GetArchivesContentFromBov1DataReceiptsItemsProduct(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    id: str
    name: str

class GetArchivesContentFromBov1DataReceiptsItemsTaxesItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    rate: int
    amount: int
    total_without_taxes: int
    total_with_taxes: int
    external_id: str

class GetArchivesContentFromBov1DataReceiptsItemsAddonsItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    addon: dict
    quantity: int

class GetArchivesContentFromBov1DataReceiptsItemsItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    """Modèle inféré depuis les exemples Postman"""
    id: str
    type_: str = Field(alias="type")
    quantity: int
    unit_price: int
    final_price: int
    product: GetArchivesContentFromBov1DataReceiptsItemsProduct
    taxes: list[GetArchivesContentFromBov1DataReceiptsItemsTaxesItem]
    addons: list[GetArchivesContentFromBov1DataReceiptsItemsAddonsItem]

class GetArchivesContentFromBov1DataReceiptsTaxesItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    rate: int
    amount: int
    total_without_taxes: int
    total_with_taxes: int
    external_id: str

class GetArchivesContentFromBov1DataReceiptsItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    id: str
    sequential_id: int
    period_id: int
    date_created: str
    date_closed: str
    owner: GetArchivesContentFromBov1DataReceiptsOwner
    nb_seats: int
    location: GetArchivesContentFromBov1DataReceiptsLocation
    table: int
    consumptionmode: GetArchivesContentFromBov1DataReceiptsConsumptionmode
    staff: bool
    customer: GetArchivesContentFromBov1DataReceiptsCustomer
    payments: list[GetArchivesContentFromBov1DataReceiptsPaymentsItem]
    items: list[GetArchivesContentFromBov1DataReceiptsItemsItem]
    total_with_taxes: int
    taxes: list[GetArchivesContentFromBov1DataReceiptsTaxesItem]

class GetArchivesContentFromBov1DataCashmovementsUser(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    id: str
    name: str

class GetArchivesContentFromBov1DataCashmovementsPaymentmethod(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    id: str
    name: str

class GetArchivesContentFromBov1DataCashmovementsCustomer(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    id: str

class GetArchivesContentFromBov1DataCashmovementsItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    amount: int
    date: str
    user: GetArchivesContentFromBov1DataCashmovementsUser
    paymentmethod: GetArchivesContentFromBov1DataCashmovementsPaymentmethod
    customer: GetArchivesContentFromBov1DataCashmovementsCustomer
    description: str

class GetArchivesContentFromBov1DataUser(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    id: str
    name: str

class GetArchivesContentFromBov1Data(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    sales: GetArchivesContentFromBov1DataSales
    staff: GetArchivesContentFromBov1DataStaff
    total: GetArchivesContentFromBov1DataTotal
    payments: list[GetArchivesContentFromBov1DataPaymentsItem]
    receipts: list[GetArchivesContentFromBov1DataReceiptsItem]
    cashmanagers: list
    cashmovements: list[GetArchivesContentFromBov1DataCashmovementsItem]
    drinkdispensersevents: list
    id: str
    sequential_id: int
    date_created: str
    user: GetArchivesContentFromBov1DataUser
    range_begin_date: str
    range_end_date: str

class GetArchivesContentFromBov1Context(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    key1: str
    key2: str

class GetArchivesContentFromBov1Response(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    succeeded: bool
    version: str
    timezone: str
    data: GetArchivesContentFromBov1Data
    context: GetArchivesContentFromBov1Context

class GetArchivesContentFromBov2DataReceiptsOwner(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    id: str
    name: str

class GetArchivesContentFromBov2DataReceiptsLocation(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    id: str
    name: str

class GetArchivesContentFromBov2DataReceiptsConsumptionmode(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    id: str
    name: str
    external_id: str

class GetArchivesContentFromBov2DataReceiptsPaymentsUser(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    id: str
    name: str

class GetArchivesContentFromBov2DataReceiptsPaymentsPaymentmethod(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    id: str
    name: str

class GetArchivesContentFromBov2DataReceiptsPaymentsItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    amount: int
    date: str
    user: GetArchivesContentFromBov2DataReceiptsPaymentsUser
    paymentmethod: GetArchivesContentFromBov2DataReceiptsPaymentsPaymentmethod

class GetArchivesContentFromBov2DataReceiptsItemsProduct(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    id: str
    name: str

class GetArchivesContentFromBov2DataReceiptsItemsTaxesItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    rate: int
    amount: int
    total_with_taxes: int
    total_without_taxes: int
    external_id: str

class GetArchivesContentFromBov2DataReceiptsItemsAddonsItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    addon: dict
    unit_price: int
    taxes: list
    quantity: int

class GetArchivesContentFromBov2DataReceiptsItemsItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    """Modèle inféré depuis les exemples Postman"""
    id: str
    type_: str = Field(alias="type")
    quantity: int
    unit_price: int
    final_price: int
    product: GetArchivesContentFromBov2DataReceiptsItemsProduct
    taxes: list[GetArchivesContentFromBov2DataReceiptsItemsTaxesItem]
    addons: list[GetArchivesContentFromBov2DataReceiptsItemsAddonsItem]

class GetArchivesContentFromBov2DataReceiptsTaxesItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    rate: int
    amount: int
    total_with_taxes: int
    total_without_taxes: int
    external_id: str

class GetArchivesContentFromBov2DataReceiptsItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    id: str
    sequential_id: int
    period_id: int
    date_created: str
    date_closed: str
    owner: GetArchivesContentFromBov2DataReceiptsOwner
    nb_seats: int
    location: GetArchivesContentFromBov2DataReceiptsLocation
    table: int
    consumptionmode: GetArchivesContentFromBov2DataReceiptsConsumptionmode
    notes: list[Any]
    cancelled: bool
    cancellation_reason: Optional[Any] = None
    staff: bool
    payments: list[GetArchivesContentFromBov2DataReceiptsPaymentsItem]
    items: list[GetArchivesContentFromBov2DataReceiptsItemsItem]
    total_with_taxes: int
    taxes: list[GetArchivesContentFromBov2DataReceiptsTaxesItem]

class GetArchivesContentFromBov2DataSalesTaxesItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    rate: int
    amount: int
    total_with_taxes: int
    total_without_taxes: int
    external_id: str

class GetArchivesContentFromBov2DataSales(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    total_with_taxes: int
    total_without_taxes: int
    nb_receipts: int
    nb_cancelled_receipts: int
    nb_seats: int
    taxes: list[GetArchivesContentFromBov2DataSalesTaxesItem]

class GetArchivesContentFromBov2DataStaff(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    total_with_taxes: int
    total_without_taxes: int
    nb_receipts: int
    nb_cancelled_receipts: int
    nb_seats: int
    taxes: list

class GetArchivesContentFromBov2DataTotalTaxesItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    rate: int
    amount: int
    total_with_taxes: int
    total_without_taxes: int
    external_id: str

class GetArchivesContentFromBov2DataTotal(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    total_with_taxes: int
    total_without_taxes: int
    nb_receipts: int
    nb_seats: int
    nb_cancelled_receipts: int
    taxes: list[GetArchivesContentFromBov2DataTotalTaxesItem]

class GetArchivesContentFromBov2DataPaymentsPaymentmethod(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    id: str
    name: str

class GetArchivesContentFromBov2DataPaymentsItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    paymentmethod: GetArchivesContentFromBov2DataPaymentsPaymentmethod
    amount: int
    nb_operations: int

class GetArchivesContentFromBov2DataUser(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    id: str
    name: str
    external_id: Optional[Any] = None

class GetArchivesContentFromBov2Data(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    receipts: list[GetArchivesContentFromBov2DataReceiptsItem]
    sales: GetArchivesContentFromBov2DataSales
    staff: GetArchivesContentFromBov2DataStaff
    total: GetArchivesContentFromBov2DataTotal
    payments: list[GetArchivesContentFromBov2DataPaymentsItem]
    id: str
    sequential_id: int
    date_created: str
    range_begin_date: str
    range_end_date: str
    user: GetArchivesContentFromBov2DataUser

class GetArchivesContentFromBov2Context(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    key1: str
    key2: str

class GetArchivesContentFromBov2Response(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    succeeded: bool
    version: str
    data: GetArchivesContentFromBov2Data
    context: GetArchivesContentFromBov2Context


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


@pytest.mark.dependency(name='test_01_get_archives_content_from_bov1')
def test_01_get_archives_content_from_bov1(ctx):
    """
    Étape 1 : GET ARCHIVES CONTENT FROM BOV1
    Utilise : bov1_host, apiuser_email, apiuser_token, installation_id
    Validation : GetArchivesContentFromBov1Response
    """
    env = {**get_env(), **ctx}
    url = f"{env['bov1_host']}/api/salesdata/v2/{env['installation_id']}/archive_content?apiuser_email={env['apiuser_email']}&apiuser_token={env['apiuser_token']}&sequential_id=1"
    headers = {

    }

    response = httpx.get(url, headers=headers, timeout=30)

    # Assertions de base
    assert response.status_code in (200, 201), (
        f"[GET ARCHIVES CONTENT FROM BOV1] Statut inattendu: {response.status_code}\n{response.text}"
    )
    data = response.json()
    assert data is not None

    # Stockage de la réponse pour les assertions cross-step
    responses = ctx.setdefault('_responses', {})
    responses['GET ARCHIVES CONTENT FROM BOV1'] = data

    # Validation Pydantic du schéma de réponse
    validated = GetArchivesContentFromBov1Response.model_validate(data)
    assert validated is not None, (
        f"[GET ARCHIVES CONTENT FROM BOV1] Validation Pydantic échouée: {data}"
    )

    # ── Règles métier ──



@pytest.mark.dependency(name='test_02_get_archives_content_from_bov2')
def test_02_get_archives_content_from_bov2(ctx):
    """
    Étape 2 : GET ARCHIVES CONTENT FROM BOV2
    Utilise : apiuser_token, apiuser_email, bov2_host, installation_id
    Validation : GetArchivesContentFromBov2Response
    """
    env = {**get_env(), **ctx}
    url = f"{env['bov2_host']}/api/salesdata/v2/{env['installation_id']}/archive_content?apiuser_email={env['apiuser_email']}&apiuser_token={env['apiuser_token']}&sequential_id=1"
    headers = {

    }

    response = httpx.get(url, headers=headers, timeout=30)

    # Assertions de base
    assert response.status_code in (200, 201), (
        f"[GET ARCHIVES CONTENT FROM BOV2] Statut inattendu: {response.status_code}\n{response.text}"
    )
    data = response.json()
    assert data is not None

    # Stockage de la réponse pour les assertions cross-step
    responses = ctx.setdefault('_responses', {})
    responses['GET ARCHIVES CONTENT FROM BOV2'] = data

    # Validation Pydantic du schéma de réponse
    validated = GetArchivesContentFromBov2Response.model_validate(data)
    assert validated is not None, (
        f"[GET ARCHIVES CONTENT FROM BOV2] Validation Pydantic échouée: {data}"
    )

    # ── Règles métier ──

    # ── Assertions cross-step ──
    if 'GET ARCHIVES CONTENT FROM BOV1' in responses:
        _src = responses["GET ARCHIVES CONTENT FROM BOV1"]["data"]["id"]
        _tgt = responses["GET ARCHIVES CONTENT FROM BOV2"]["data"]["id"]
        assert deep_sort(_src) == deep_sort(_tgt), (
            f"Cross-step assertion failed (GET ARCHIVES CONTENT FROM BOV1 → GET ARCHIVES CONTENT FROM BOV2) — src={_src!r}, tgt={_tgt!r}"
        )



@pytest.mark.dependency(depends=["test_01_get_archives_content_from_bov1", "test_02_get_archives_content_from_bov2"])
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
