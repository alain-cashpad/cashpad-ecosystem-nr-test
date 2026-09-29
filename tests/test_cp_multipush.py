from __future__ import annotations

"""
Tests E2E générés automatiquement pour la collection : CP_MULTIPUSH
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

class CheckStaticModelFromBcModelAccountnumberItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    content: int
    id: str
    number: str

class CheckStaticModelFromBcModelBaseItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    cashContainer: str
    deleted: bool
    flags: int
    id: str
    name: str
    serial: str

class CheckStaticModelFromBcModelBaseparameterItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    base: str
    id: str
    key: str
    value: str

class CheckStaticModelFromBcModelCashcontainerItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    deleted: bool
    flags: int
    id: str
    latestCashFloat: int

class CheckStaticModelFromBcModelCashmanagerItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    driver: str
    flags: int
    id: str
    name: str

class CheckStaticModelFromBcModelCashmovementcategoryItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    deleted: bool
    flags: int
    id: str
    name: str

class CheckStaticModelFromBcModelConsumptionmodeItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    deleted: bool
    externalId: str
    flags: int
    id: str
    name: str

class CheckStaticModelFromBcModelConsumptionmodelinkItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    consumptionMode: str
    flags: int
    id: str
    location: str
    priority: int

class CheckStaticModelFromBcModelFilterItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    flags: int
    id: str
    receiptOrigin: int

class CheckStaticModelFromBcModelFiltercontentItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    filter: str
    group: str
    id: str

class CheckStaticModelFromBcModelFiscaltrackerdeviceItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    """Modèle inféré depuis les exemples Postman"""
    detail: str
    id: int
    serial: str
    type_: int = Field(alias="type")

class CheckStaticModelFromBcModelFunctionbuttonItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    color: str
    column: int
    function: int
    height: int
    id: str
    label: str
    mode: int
    row: int

class CheckStaticModelFromBcModelFunctionchildbuttonItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    function: int
    id: str
    index: int
    label: str
    parent: str

class CheckStaticModelFromBcModelGroupItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    accountingRights: int
    adminReadRights: int
    adminWriteRights: int
    checkInRequired: bool
    deleted: bool
    flags: int
    id: str
    level: int
    name: str
    rights: int
    rights2: int
    rights3: int
    stocksRights: int

class CheckStaticModelFromBcModelKitchendisplayItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    burstDuration: int
    flags: int
    id: str
    index: int
    name: str
    nbItemsPerBurst: int
    nbProductionPoints: int
    productionStage: int

class CheckStaticModelFromBcModelKitchendisplayproductItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    color: str
    flags: int
    id: str
    index: int
    kitchenDisplay: str
    product: str

class CheckStaticModelFromBcModelKitchendisplayproductgroupItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    color: str
    flags: int
    id: str
    index: int
    kitchenDisplay: str
    label: str

class CheckStaticModelFromBcModelLayoutItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    """Modèle inféré depuis les exemples Postman"""
    id: str
    menu: str
    priority: int
    type_: int = Field(alias="type")

class CheckStaticModelFromBcModelLevelnameItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    id: int

class CheckStaticModelFromBcModelLicenseItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    """Modèle inféré depuis les exemples Postman"""
    id: str
    instance: int
    key: str
    type_: int = Field(alias="type")
    valid: bool

class CheckStaticModelFromBcModelLocationItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    deleted: bool
    externalId: str
    filter: str
    flags: int
    id: str
    index: int
    name: str
    validNumbers: str

class CheckStaticModelFromBcModelMenuitemItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    filter: str
    id: str
    menuItemSet: str
    product: str

class CheckStaticModelFromBcModelMenuitemsetItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    id: str
    index: int
    menu: str
    name: str
    quantity: int

class CheckStaticModelFromBcModelMessagecategoryItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    id: str
    index: int
    name: str

class CheckStaticModelFromBcModelMessageproductcategoryItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    id: str
    messageCategory: str
    productCategory: str

class CheckStaticModelFromBcModelNoteItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    displayOrder: int
    id: str
    message: str
    messageCategory: str

class CheckStaticModelFromBcModelParameterItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    id: str
    value: str

class CheckStaticModelFromBcModelPaymentmethodItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    """Modèle inféré depuis les exemples Postman"""
    deleted: bool
    filter: str
    flags: int
    id: str
    index: int
    name: str
    type_: int = Field(alias="type")
    useForCredit: bool
    useForDebit: bool

class CheckStaticModelFromBcModelPaymentterminalItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    device: str
    driver: str
    flags: int
    id: str
    identifier: str
    name: str

class CheckStaticModelFromBcModelPredefineddiscountItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    """Modèle inféré depuis les exemples Postman"""
    active: bool
    deleted: bool
    externalId: str
    flags: int
    id: str
    index: int
    name: str
    offered: bool
    percentage: int
    type_: int = Field(alias="type")

class CheckStaticModelFromBcModelPredefineddiscountcontentItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    id: str
    predefinedDiscount: str
    product: str

class CheckStaticModelFromBcModelPriceItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    id: str
    priceInclTaxes: int
    product: str
    rateMaking: str
    tax: str

class CheckStaticModelFromBcModelProductItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    """Modèle inféré depuis les exemples Postman"""
    allergens: int
    category: str
    deleted: bool
    flags: int
    freeAmount: bool
    id: str
    name: str
    type_: int = Field(alias="type")

class CheckStaticModelFromBcModelProductaddonItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    category: str
    deleted: bool
    flags: int
    id: str
    index: int
    product: str

class CheckStaticModelFromBcModelProductaddoncategoryItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    allowMultiples: bool
    deleted: bool
    id: str
    includeInBills: bool
    includeInReports: bool
    maxQty: int
    name: str
    selectionInPopup: bool

class CheckStaticModelFromBcModelProductcategoryItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    defaultLevel: int
    deleted: bool
    flags: int
    id: str
    name: str
    printIndex: int

class CheckStaticModelFromBcModelProductcontainercontentItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    container: str
    content: str
    id: str
    index: int
    label: str

class CheckStaticModelFromBcModelProductgroupItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    id: str
    name: str

class CheckStaticModelFromBcModelProductgroupcontentItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    group: str
    id: str
    index: int
    product: str

class CheckStaticModelFromBcModelProductingredientItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    id: str
    ingredient: str
    product: str
    quantity: int

class CheckStaticModelFromBcModelProductlayoutItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    color: str
    column: int
    height: int
    id: str
    product: str
    productSetLayout: str
    row: int
    width: int

class CheckStaticModelFromBcModelProductlinkItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    child: str
    id: str
    index: int
    parent: str

class CheckStaticModelFromBcModelProductoptionItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    addonCategory: str
    id: str
    index: int
    optional: bool
    product: str

class CheckStaticModelFromBcModelProductsetlayoutItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    color: str
    column: int
    height: int
    icon: str
    id: str
    layout: str
    name: str
    parent: str
    row: int
    width: int

class CheckStaticModelFromBcModelRatemakingItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    active: bool
    defaultTax: str
    externalId: str
    flags: int
    id: str
    name: str
    parent: str
    priority: int
    scheduleEnd: str
    scheduleStart: str

class CheckStaticModelFromBcModelSeatingplanItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    backgroundAlpha: int
    backgroundWidth: int
    backgroundX: int
    backgroundY: int
    default: bool
    defaultLocation: str
    id: str
    name: str
    orderIndex: int
    translationX: int
    translationY: int
    widthInMeters: int

class CheckStaticModelFromBcModelSeatingplantableItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    """Modèle inféré depuis les exemples Postman"""
    id: str
    location: str
    nbSeats: int
    number: int
    plan: str
    rotation: int
    scaleX: int
    scaleY: int
    type_: int = Field(alias="type")
    x: float
    y: float

class CheckStaticModelFromBcModelSeatingplantablelinkItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    child: str
    id: str
    parent: str

class CheckStaticModelFromBcModelSiteItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    flags: int
    id: str
    name: str

class CheckStaticModelFromBcModelTaxItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    externalId: str
    id: str
    name: str
    rate1: int

class CheckStaticModelFromBcModelTerminalItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    """Modèle inféré depuis les exemples Postman"""
    capabilities: int
    deleted: bool
    id: str
    model: str
    name: str
    systemType: int
    type_: int = Field(alias="type")

class CheckStaticModelFromBcModelUserItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    dallas: str
    deleted: bool
    externalId: str
    flags: int
    group: str
    id: str
    name: str
    password: str

class CheckStaticModelFromBcModel(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    accountNumber: list[CheckStaticModelFromBcModelAccountnumberItem]
    base: list[CheckStaticModelFromBcModelBaseItem]
    baseParameter: list[CheckStaticModelFromBcModelBaseparameterItem]
    cashContainer: list[CheckStaticModelFromBcModelCashcontainerItem]
    cashManager: list[CheckStaticModelFromBcModelCashmanagerItem]
    cashMovementCategory: list[CheckStaticModelFromBcModelCashmovementcategoryItem]
    consumptionMode: list[CheckStaticModelFromBcModelConsumptionmodeItem]
    consumptionModeLink: list[CheckStaticModelFromBcModelConsumptionmodelinkItem]
    filter: list[CheckStaticModelFromBcModelFilterItem]
    filterContent: list[CheckStaticModelFromBcModelFiltercontentItem]
    fiscalTrackerDevice: list[CheckStaticModelFromBcModelFiscaltrackerdeviceItem]
    functionButton: list[CheckStaticModelFromBcModelFunctionbuttonItem]
    functionChildButton: list[CheckStaticModelFromBcModelFunctionchildbuttonItem]
    group: list[CheckStaticModelFromBcModelGroupItem]
    kitchenDisplay: list[CheckStaticModelFromBcModelKitchendisplayItem]
    kitchenDisplayProduct: list[CheckStaticModelFromBcModelKitchendisplayproductItem]
    kitchenDisplayProductGroup: list[CheckStaticModelFromBcModelKitchendisplayproductgroupItem]
    layout: list[CheckStaticModelFromBcModelLayoutItem]
    levelName: list[CheckStaticModelFromBcModelLevelnameItem]
    license: list[CheckStaticModelFromBcModelLicenseItem]
    location: list[CheckStaticModelFromBcModelLocationItem]
    menuItem: list[CheckStaticModelFromBcModelMenuitemItem]
    menuItemSet: list[CheckStaticModelFromBcModelMenuitemsetItem]
    messageCategory: list[CheckStaticModelFromBcModelMessagecategoryItem]
    messageProductCategory: list[CheckStaticModelFromBcModelMessageproductcategoryItem]
    note: list[CheckStaticModelFromBcModelNoteItem]
    parameter: list[CheckStaticModelFromBcModelParameterItem]
    paymentMethod: list[CheckStaticModelFromBcModelPaymentmethodItem]
    paymentTerminal: list[CheckStaticModelFromBcModelPaymentterminalItem]
    predefinedDiscount: list[CheckStaticModelFromBcModelPredefineddiscountItem]
    predefinedDiscountContent: list[CheckStaticModelFromBcModelPredefineddiscountcontentItem]
    price: list[CheckStaticModelFromBcModelPriceItem]
    product: list[CheckStaticModelFromBcModelProductItem]
    productAddon: list[CheckStaticModelFromBcModelProductaddonItem]
    productAddonCategory: list[CheckStaticModelFromBcModelProductaddoncategoryItem]
    productCategory: list[CheckStaticModelFromBcModelProductcategoryItem]
    productContainerContent: list[CheckStaticModelFromBcModelProductcontainercontentItem]
    productGroup: list[CheckStaticModelFromBcModelProductgroupItem]
    productGroupContent: list[CheckStaticModelFromBcModelProductgroupcontentItem]
    productIngredient: list[CheckStaticModelFromBcModelProductingredientItem]
    productLayout: list[CheckStaticModelFromBcModelProductlayoutItem]
    productLink: list[CheckStaticModelFromBcModelProductlinkItem]
    productOption: list[CheckStaticModelFromBcModelProductoptionItem]
    productSetLayout: list[CheckStaticModelFromBcModelProductsetlayoutItem]
    rateMaking: list[CheckStaticModelFromBcModelRatemakingItem]
    seatingPlan: list[CheckStaticModelFromBcModelSeatingplanItem]
    seatingPlanTable: list[CheckStaticModelFromBcModelSeatingplantableItem]
    seatingPlanTableLink: list[CheckStaticModelFromBcModelSeatingplantablelinkItem]
    site: list[CheckStaticModelFromBcModelSiteItem]
    tax: list[CheckStaticModelFromBcModelTaxItem]
    terminal: list[CheckStaticModelFromBcModelTerminalItem]
    user: list[CheckStaticModelFromBcModelUserItem]

class CheckStaticModelFromBcResponse(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    model: CheckStaticModelFromBcModel
    schemaVersion: int
    version: int

class TriggPushData(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    id: int
    note: str
    userId: int
    startAt: Optional[Any] = None
    endAt: Optional[Any] = None
    siteId: int
    options: list[str]
    pushType: str
    status: str

class TriggPushSyncsItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    id: int
    batchId: int
    status: str
    siteId: int
    startAt: Optional[Any] = None
    endAt: Optional[Any] = None

class TriggPushResponse(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    data: TriggPushData
    syncs: list[TriggPushSyncsItem]

class CheckPushProgressUsersItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    id: int
    firstName: str
    lastName: str
    status: str
    email: str
    telephone: str
    lastActiveAt: str
    language: str

class CheckPushProgressSyncsErrorv2Data(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    errorCode: str

class CheckPushProgressSyncsErrorv2(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    data: CheckPushProgressSyncsErrorv2Data
    message: str
    isRetryable: bool

class CheckPushProgressSyncsItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    id: int
    batchId: int
    errorV2: CheckPushProgressSyncsErrorv2
    binaryVersion: Optional[Any] = None
    startAt: Optional[Any] = None
    endAt: Optional[Any] = None
    status: str
    siteId: int
    createdAt: str

class CheckPushProgressDataItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    id: int
    note: str
    siteId: int
    userId: int
    startAt: str
    endAt: str
    options: list[str]
    status: str
    errorV2: Optional[Any] = None
    binaryVersion: str

class CheckPushProgressResponse(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    limit: int
    skip: int
    users: list[CheckPushProgressUsersItem]
    syncs: list[CheckPushProgressSyncsItem]
    data: list[CheckPushProgressDataItem]
    total: int

class CheckStaticModelFromTarget1ModelAccountnumberItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    content: int
    id: str
    number: str

class CheckStaticModelFromTarget1ModelBaseItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    billPrinter: str
    cashContainer: str
    deleted: bool
    flags: int
    id: str
    name: str
    serial: str

class CheckStaticModelFromTarget1ModelBaseparameterItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    base: str
    id: str
    key: str
    value: str

class CheckStaticModelFromTarget1ModelCashcontainerItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    deleted: bool
    flags: int
    id: str
    latestCashFloat: int

class CheckStaticModelFromTarget1ModelCashmovementcategoryItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    deleted: bool
    flags: int
    id: str
    name: str

class CheckStaticModelFromTarget1ModelConsumptionmodeItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    deleted: bool
    externalId: str
    flags: int
    id: str
    name: str

class CheckStaticModelFromTarget1ModelConsumptionmodelinkItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    consumptionMode: str
    flags: int
    id: str
    location: str
    priority: int

class CheckStaticModelFromTarget1ModelFilterItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    flags: int
    id: str
    receiptOrigin: int

class CheckStaticModelFromTarget1ModelFiltercontentItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    filter: str
    group: str
    id: str

class CheckStaticModelFromTarget1ModelFiscaltrackerdeviceItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    """Modèle inféré depuis les exemples Postman"""
    detail: str
    id: int
    serial: str
    type_: int = Field(alias="type")

class CheckStaticModelFromTarget1ModelFunctionbuttonItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    color: str
    column: int
    function: int
    height: int
    icon: str
    id: str
    label: str
    mode: int
    row: int

class CheckStaticModelFromTarget1ModelGroupItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    accountingRights: int
    adminReadRights: int
    adminWriteRights: int
    checkInRequired: bool
    deleted: bool
    flags: int
    id: str
    level: int
    name: str
    rights: int
    rights2: int
    rights3: int
    stocksRights: int

class CheckStaticModelFromTarget1ModelLayoutItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    """Modèle inféré depuis les exemples Postman"""
    id: str
    menu: str
    name: str
    priority: int
    type_: int = Field(alias="type")

class CheckStaticModelFromTarget1ModelLevelnameItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    id: int
    name: str

class CheckStaticModelFromTarget1ModelLicenseItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    """Modèle inféré depuis les exemples Postman"""
    id: str
    instance: int
    key: str
    type_: int = Field(alias="type")
    valid: bool

class CheckStaticModelFromTarget1ModelLocationItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    deleted: bool
    flags: int
    id: str
    index: int
    name: str

class CheckStaticModelFromTarget1ModelMenuitemItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    filter: str
    id: str
    menuItemSet: str
    product: str

class CheckStaticModelFromTarget1ModelMenuitemsetItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    id: str
    index: int
    menu: str
    name: str
    quantity: int

class CheckStaticModelFromTarget1ModelParameterItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    id: str
    value: str

class CheckStaticModelFromTarget1ModelPaymentmethodItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    """Modèle inféré depuis les exemples Postman"""
    autoChangeMethod: str
    deleted: bool
    flags: int
    id: str
    index: int
    name: str
    type_: int = Field(alias="type")
    useForCredit: bool
    useForDebit: bool

class CheckStaticModelFromTarget1ModelPredefineddiscountItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    """Modèle inféré depuis les exemples Postman"""
    active: bool
    deleted: bool
    externalId: str
    flags: int
    id: str
    index: int
    name: str
    offered: bool
    percentage: int
    type_: int = Field(alias="type")

class CheckStaticModelFromTarget1ModelPredefineddiscountcontentItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    id: str
    predefinedDiscount: str
    product: str

class CheckStaticModelFromTarget1ModelPriceItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    id: str
    priceInclTaxes: int
    rateMaking: str
    tax: str

class CheckStaticModelFromTarget1ModelPrinterItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    deliveryPrinter: bool
    device: str
    driver: str
    flags: int
    id: str
    index: int
    name: str
    preparationPrinter: bool
    productionFlags: int

class CheckStaticModelFromTarget1ModelProductItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    """Modèle inféré depuis les exemples Postman"""
    allergens: int
    category: str
    deleted: bool
    flags: int
    freeAmount: bool
    id: str
    name: str
    type_: int = Field(alias="type")

class CheckStaticModelFromTarget1ModelProductaddonItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    category: str
    deleted: bool
    flags: int
    id: str
    index: int
    propertyName: str

class CheckStaticModelFromTarget1ModelProductaddoncategoryItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    allowMultiples: bool
    deleted: bool
    id: str
    includeInBills: bool
    includeInReports: bool
    name: str
    selectionInPopup: bool

class CheckStaticModelFromTarget1ModelProductcategoryItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    defaultLevel: int
    deleted: bool
    flags: int
    id: str
    name: str
    printIndex: int

class CheckStaticModelFromTarget1ModelProductcategoryproductionItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    """Modèle inféré depuis les exemples Postman"""
    id: str
    printer: str
    productCategory: str
    type_: int = Field(alias="type")

class CheckStaticModelFromTarget1ModelProductcontainercontentItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    container: str
    content: str
    id: str
    index: int
    label: str

class CheckStaticModelFromTarget1ModelProductgroupItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    id: str
    name: str

class CheckStaticModelFromTarget1ModelProductgroupcontentItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    group: str
    id: str
    index: int
    product: str

class CheckStaticModelFromTarget1ModelProductingredientItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    id: str
    ingredient: str
    product: str
    quantity: int

class CheckStaticModelFromTarget1ModelProductlayoutItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    color: str
    column: int
    height: int
    id: str
    product: str
    productSetLayout: str
    row: int
    width: int

class CheckStaticModelFromTarget1ModelProductlinkItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    child: str
    id: str
    index: int
    parent: str

class CheckStaticModelFromTarget1ModelProductoptionItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    addonCategory: str
    id: str
    index: int
    optional: bool
    product: str

class CheckStaticModelFromTarget1ModelProductsetlayoutItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    color: str
    column: int
    height: int
    id: str
    layout: str
    menuItemSet: str
    name: str
    row: int
    width: int

class CheckStaticModelFromTarget1ModelRatemakingItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    active: bool
    defaultTax: str
    externalId: str
    flags: int
    id: str
    name: str
    priority: int

class CheckStaticModelFromTarget1ModelRawdataItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    data: str
    id: str

class CheckStaticModelFromTarget1ModelSeatingplanItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    backgroundAlpha: int
    backgroundWidth: int
    backgroundX: float
    backgroundY: float
    default: bool
    defaultLocation: str
    id: str
    name: str
    orderIndex: int
    translationX: float
    translationY: float
    widthInMeters: float

class CheckStaticModelFromTarget1ModelSeatingplantableItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    """Modèle inféré depuis les exemples Postman"""
    id: str
    location: str
    number: int
    plan: str
    rotation: int
    scaleX: int
    scaleY: int
    type_: int = Field(alias="type")
    x: float
    y: float

class CheckStaticModelFromTarget1ModelSiteItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    flags: int
    id: str
    name: str

class CheckStaticModelFromTarget1ModelTaxItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    externalId: str
    id: str
    name: str
    rate1: int

class CheckStaticModelFromTarget1ModelTerminalItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    """Modèle inféré depuis les exemples Postman"""
    capabilities: int
    deleted: bool
    id: str
    model: str
    name: str
    systemType: int
    type_: int = Field(alias="type")

class CheckStaticModelFromTarget1ModelUserItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    deleted: bool
    flags: int
    group: str
    id: str
    name: str
    password: str

class CheckStaticModelFromTarget1Model(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    accountNumber: list[CheckStaticModelFromTarget1ModelAccountnumberItem]
    base: list[CheckStaticModelFromTarget1ModelBaseItem]
    baseParameter: list[CheckStaticModelFromTarget1ModelBaseparameterItem]
    cashContainer: list[CheckStaticModelFromTarget1ModelCashcontainerItem]
    cashMovementCategory: list[CheckStaticModelFromTarget1ModelCashmovementcategoryItem]
    consumptionMode: list[CheckStaticModelFromTarget1ModelConsumptionmodeItem]
    consumptionModeLink: list[CheckStaticModelFromTarget1ModelConsumptionmodelinkItem]
    filter: list[CheckStaticModelFromTarget1ModelFilterItem]
    filterContent: list[CheckStaticModelFromTarget1ModelFiltercontentItem]
    fiscalTrackerDevice: list[CheckStaticModelFromTarget1ModelFiscaltrackerdeviceItem]
    functionButton: list[CheckStaticModelFromTarget1ModelFunctionbuttonItem]
    group: list[CheckStaticModelFromTarget1ModelGroupItem]
    layout: list[CheckStaticModelFromTarget1ModelLayoutItem]
    levelName: list[CheckStaticModelFromTarget1ModelLevelnameItem]
    license: list[CheckStaticModelFromTarget1ModelLicenseItem]
    location: list[CheckStaticModelFromTarget1ModelLocationItem]
    menuItem: list[CheckStaticModelFromTarget1ModelMenuitemItem]
    menuItemSet: list[CheckStaticModelFromTarget1ModelMenuitemsetItem]
    parameter: list[CheckStaticModelFromTarget1ModelParameterItem]
    paymentMethod: list[CheckStaticModelFromTarget1ModelPaymentmethodItem]
    predefinedDiscount: list[CheckStaticModelFromTarget1ModelPredefineddiscountItem]
    predefinedDiscountContent: list[CheckStaticModelFromTarget1ModelPredefineddiscountcontentItem]
    price: list[CheckStaticModelFromTarget1ModelPriceItem]
    printer: list[CheckStaticModelFromTarget1ModelPrinterItem]
    product: list[CheckStaticModelFromTarget1ModelProductItem]
    productAddon: list[CheckStaticModelFromTarget1ModelProductaddonItem]
    productAddonCategory: list[CheckStaticModelFromTarget1ModelProductaddoncategoryItem]
    productCategory: list[CheckStaticModelFromTarget1ModelProductcategoryItem]
    productCategoryProduction: list[CheckStaticModelFromTarget1ModelProductcategoryproductionItem]
    productContainerContent: list[CheckStaticModelFromTarget1ModelProductcontainercontentItem]
    productGroup: list[CheckStaticModelFromTarget1ModelProductgroupItem]
    productGroupContent: list[CheckStaticModelFromTarget1ModelProductgroupcontentItem]
    productIngredient: list[CheckStaticModelFromTarget1ModelProductingredientItem]
    productLayout: list[CheckStaticModelFromTarget1ModelProductlayoutItem]
    productLink: list[CheckStaticModelFromTarget1ModelProductlinkItem]
    productOption: list[CheckStaticModelFromTarget1ModelProductoptionItem]
    productSetLayout: list[CheckStaticModelFromTarget1ModelProductsetlayoutItem]
    rateMaking: list[CheckStaticModelFromTarget1ModelRatemakingItem]
    rawData: list[CheckStaticModelFromTarget1ModelRawdataItem]
    seatingPlan: list[CheckStaticModelFromTarget1ModelSeatingplanItem]
    seatingPlanTable: list[CheckStaticModelFromTarget1ModelSeatingplantableItem]
    site: list[CheckStaticModelFromTarget1ModelSiteItem]
    tax: list[CheckStaticModelFromTarget1ModelTaxItem]
    terminal: list[CheckStaticModelFromTarget1ModelTerminalItem]
    user: list[CheckStaticModelFromTarget1ModelUserItem]

class CheckStaticModelFromTarget1Response(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    model: CheckStaticModelFromTarget1Model
    schemaVersion: int
    version: int

class CheckStaticModelFromTarget2ModelBaseItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    billPrinter: str
    cashContainer: str
    cashManager: str
    deleted: bool
    flags: int
    id: str
    name: str
    paymentTerminal: str
    serial: str

class CheckStaticModelFromTarget2ModelBaseparameterItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    base: str
    id: str
    key: str
    value: str

class CheckStaticModelFromTarget2ModelCashcontainerItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    deleted: bool
    flags: int
    id: str
    latestCashFloat: int

class CheckStaticModelFromTarget2ModelCashmanagerItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    driver: str
    flags: int
    id: str
    license: str
    name: str

class CheckStaticModelFromTarget2ModelCashmovementcategoryItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    deleted: bool
    flags: int
    id: str
    name: str

class CheckStaticModelFromTarget2ModelConsumptionmodeItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    deleted: bool
    externalId: str
    flags: int
    id: str
    name: str

class CheckStaticModelFromTarget2ModelConsumptionmodelinkItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    consumptionMode: str
    flags: int
    id: str
    location: str
    priority: int

class CheckStaticModelFromTarget2ModelFilterItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    flags: int
    id: str
    receiptOrigin: int

class CheckStaticModelFromTarget2ModelFiltercontentItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    base: str
    filter: str
    id: str

class CheckStaticModelFromTarget2ModelFiscaltrackerdeviceItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    """Modèle inféré depuis les exemples Postman"""
    detail: str
    id: int
    serial: str
    type_: int = Field(alias="type")

class CheckStaticModelFromTarget2ModelFunctionbuttonItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    color: str
    column: int
    function: int
    height: int
    id: str
    label: str
    mode: int
    paymentMethod: str
    row: int

class CheckStaticModelFromTarget2ModelFunctionchildbuttonItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    function: int
    id: str
    index: int
    label: str
    parent: str

class CheckStaticModelFromTarget2ModelGroupItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    accountingRights: int
    adminReadRights: int
    adminWriteRights: int
    checkInRequired: bool
    deleted: bool
    flags: int
    id: str
    level: int
    name: str
    rights: int
    rights2: int
    rights3: int
    stocksRights: int

class CheckStaticModelFromTarget2ModelLayoutItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    """Modèle inféré depuis les exemples Postman"""
    id: str
    menu: str
    name: str
    priority: int
    type_: int = Field(alias="type")

class CheckStaticModelFromTarget2ModelLevelnameItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    id: int

class CheckStaticModelFromTarget2ModelLicenseItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    """Modèle inféré depuis les exemples Postman"""
    id: str
    instance: int
    key: str
    type_: int = Field(alias="type")
    valid: bool

class CheckStaticModelFromTarget2ModelLocationItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    deleted: bool
    flags: int
    id: str
    index: int
    name: str

class CheckStaticModelFromTarget2ModelMenuitemItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    filter: str
    id: str
    menuItemSet: str
    product: str

class CheckStaticModelFromTarget2ModelMenuitemsetItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    id: str
    index: int
    menu: str
    name: str
    quantity: int

class CheckStaticModelFromTarget2ModelNoteItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    displayOrder: int
    id: str
    message: str

class CheckStaticModelFromTarget2ModelParameterItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    id: str
    value: str

class CheckStaticModelFromTarget2ModelPaymentmethodItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    """Modèle inféré depuis les exemples Postman"""
    deleted: bool
    flags: int
    id: str
    index: int
    name: str
    type_: int = Field(alias="type")
    useForCredit: bool
    useForDebit: bool

class CheckStaticModelFromTarget2ModelPaymentterminalItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    device: str
    driver: str
    flags: int
    hostBase: str
    id: str
    identifier: str
    name: str

class CheckStaticModelFromTarget2ModelPredefineddiscountItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    """Modèle inféré depuis les exemples Postman"""
    active: bool
    deleted: bool
    filter: str
    flags: int
    id: str
    index: int
    name: str
    percentage: int
    type_: int = Field(alias="type")

class CheckStaticModelFromTarget2ModelPredefineddiscountcontentItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    id: str
    predefinedDiscount: str
    product: str

class CheckStaticModelFromTarget2ModelPriceItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    id: str
    priceInclTaxes: int
    rateMaking: str
    tax: str

class CheckStaticModelFromTarget2ModelPrinterItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    deliveryPrinter: bool
    device: str
    driver: str
    flags: int
    id: str
    index: int
    name: str
    preparationPrinter: bool
    productionFlags: int

class CheckStaticModelFromTarget2ModelProductItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    """Modèle inféré depuis les exemples Postman"""
    allergens: int
    category: str
    deleted: bool
    flags: int
    freeAmount: bool
    id: str
    name: str
    type_: int = Field(alias="type")

class CheckStaticModelFromTarget2ModelProductaddonItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    category: str
    deleted: bool
    flags: int
    id: str
    index: int
    propertyName: str

class CheckStaticModelFromTarget2ModelProductaddoncategoryItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    allowMultiples: bool
    deleted: bool
    id: str
    includeInBills: bool
    includeInReports: bool
    maxQty: int
    minQty: int
    name: str
    selectionInPopup: bool

class CheckStaticModelFromTarget2ModelProductcategoryItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    defaultLevel: int
    deleted: bool
    flags: int
    id: str
    name: str
    printIndex: int

class CheckStaticModelFromTarget2ModelProductcategoryproductionItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    """Modèle inféré depuis les exemples Postman"""
    id: str
    printer: str
    product: str
    type_: int = Field(alias="type")

class CheckStaticModelFromTarget2ModelProductcontainercontentItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    container: str
    content: str
    id: str
    index: int
    label: str

class CheckStaticModelFromTarget2ModelProductgroupItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    id: str
    name: str

class CheckStaticModelFromTarget2ModelProductgroupcontentItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    group: str
    id: str
    index: int
    product: str

class CheckStaticModelFromTarget2ModelProductingredientItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    id: str
    ingredient: str
    product: str
    quantity: int

class CheckStaticModelFromTarget2ModelProductlayoutItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    color: str
    column: int
    height: int
    id: str
    product: str
    productSetLayout: str
    row: int
    width: int

class CheckStaticModelFromTarget2ModelProductlinkItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    child: str
    id: str
    index: int
    parent: str

class CheckStaticModelFromTarget2ModelProductoptionItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    addonCategory: str
    id: str
    index: int
    optional: bool
    product: str

class CheckStaticModelFromTarget2ModelProductsetlayoutItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    color: str
    column: int
    height: int
    id: str
    layout: str
    menuItemSet: str
    name: str
    row: int
    width: int

class CheckStaticModelFromTarget2ModelRatemakingItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    active: bool
    defaultTax: str
    externalId: str
    flags: int
    id: str
    name: str
    parent: str
    priority: int
    scheduleEnd: str
    scheduleStart: str

class CheckStaticModelFromTarget2ModelSiteItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    flags: int
    id: str
    name: str

class CheckStaticModelFromTarget2ModelTaxItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    externalId: str
    id: str
    name: str
    rate1: int

class CheckStaticModelFromTarget2ModelTerminalItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    """Modèle inféré depuis les exemples Postman"""
    capabilities: int
    deleted: bool
    id: str
    model: str
    name: str
    systemType: int
    type_: int = Field(alias="type")

class CheckStaticModelFromTarget2ModelUserItem(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    deleted: bool
    flags: int
    group: str
    id: str
    name: str
    password: str

class CheckStaticModelFromTarget2Model(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    base: list[CheckStaticModelFromTarget2ModelBaseItem]
    baseParameter: list[CheckStaticModelFromTarget2ModelBaseparameterItem]
    cashContainer: list[CheckStaticModelFromTarget2ModelCashcontainerItem]
    cashManager: list[CheckStaticModelFromTarget2ModelCashmanagerItem]
    cashMovementCategory: list[CheckStaticModelFromTarget2ModelCashmovementcategoryItem]
    consumptionMode: list[CheckStaticModelFromTarget2ModelConsumptionmodeItem]
    consumptionModeLink: list[CheckStaticModelFromTarget2ModelConsumptionmodelinkItem]
    filter: list[CheckStaticModelFromTarget2ModelFilterItem]
    filterContent: list[CheckStaticModelFromTarget2ModelFiltercontentItem]
    fiscalTrackerDevice: list[CheckStaticModelFromTarget2ModelFiscaltrackerdeviceItem]
    functionButton: list[CheckStaticModelFromTarget2ModelFunctionbuttonItem]
    functionChildButton: list[CheckStaticModelFromTarget2ModelFunctionchildbuttonItem]
    group: list[CheckStaticModelFromTarget2ModelGroupItem]
    layout: list[CheckStaticModelFromTarget2ModelLayoutItem]
    levelName: list[CheckStaticModelFromTarget2ModelLevelnameItem]
    license: list[CheckStaticModelFromTarget2ModelLicenseItem]
    location: list[CheckStaticModelFromTarget2ModelLocationItem]
    menuItem: list[CheckStaticModelFromTarget2ModelMenuitemItem]
    menuItemSet: list[CheckStaticModelFromTarget2ModelMenuitemsetItem]
    note: list[CheckStaticModelFromTarget2ModelNoteItem]
    parameter: list[CheckStaticModelFromTarget2ModelParameterItem]
    paymentMethod: list[CheckStaticModelFromTarget2ModelPaymentmethodItem]
    paymentTerminal: list[CheckStaticModelFromTarget2ModelPaymentterminalItem]
    predefinedDiscount: list[CheckStaticModelFromTarget2ModelPredefineddiscountItem]
    predefinedDiscountContent: list[CheckStaticModelFromTarget2ModelPredefineddiscountcontentItem]
    price: list[CheckStaticModelFromTarget2ModelPriceItem]
    printer: list[CheckStaticModelFromTarget2ModelPrinterItem]
    product: list[CheckStaticModelFromTarget2ModelProductItem]
    productAddon: list[CheckStaticModelFromTarget2ModelProductaddonItem]
    productAddonCategory: list[CheckStaticModelFromTarget2ModelProductaddoncategoryItem]
    productCategory: list[CheckStaticModelFromTarget2ModelProductcategoryItem]
    productCategoryProduction: list[CheckStaticModelFromTarget2ModelProductcategoryproductionItem]
    productContainerContent: list[CheckStaticModelFromTarget2ModelProductcontainercontentItem]
    productGroup: list[CheckStaticModelFromTarget2ModelProductgroupItem]
    productGroupContent: list[CheckStaticModelFromTarget2ModelProductgroupcontentItem]
    productIngredient: list[CheckStaticModelFromTarget2ModelProductingredientItem]
    productLayout: list[CheckStaticModelFromTarget2ModelProductlayoutItem]
    productLink: list[CheckStaticModelFromTarget2ModelProductlinkItem]
    productOption: list[CheckStaticModelFromTarget2ModelProductoptionItem]
    productSetLayout: list[CheckStaticModelFromTarget2ModelProductsetlayoutItem]
    rateMaking: list[CheckStaticModelFromTarget2ModelRatemakingItem]
    site: list[CheckStaticModelFromTarget2ModelSiteItem]
    tax: list[CheckStaticModelFromTarget2ModelTaxItem]
    terminal: list[CheckStaticModelFromTarget2ModelTerminalItem]
    user: list[CheckStaticModelFromTarget2ModelUserItem]

class CheckStaticModelFromTarget2Response(BaseModel):
    """Modèle inféré depuis les exemples Postman"""
    model: CheckStaticModelFromTarget2Model
    schemaVersion: int
    version: int


def get_env() -> dict:
    """Charge les variables statiques depuis .env"""
    required = [
        "bc_cashpad_id",
        "target_01_cashpad_id",
        "target_02_cashpad_id",
        "bov2_host",
        "bov2_token",
        "organization_id",
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
    Variables dynamiques attendues en fin de séquence : ['bc_static_model_version', 'multipush_transaction_id', 'target_01_push_transacation_id', 'target_01_static_model_version', 'target_02_push_transacation_id', 'target_02_static_model_version']
    """
    return {}


@pytest.mark.dependency(name='test_01_check_static_model_from_bc')
def test_01_check_static_model_from_bc(ctx):
    """
    Étape 1 : CHECK STATIC MODEL FROM BC
    Utilise : bc_cashpad_id
    Extrait pour la suite : bc_static_model_version
    Validation : CheckStaticModelFromBcResponse
    """
    env = {**get_env(), **ctx}
    url = f"http://{env['bc_cashpad_id']}.vpn.osilia.com:9091/model/pull_model"
    headers = {

    }

    response = httpx.get(url, headers=headers, timeout=30)

    # Assertions de base
    assert response.status_code in (200, 201), (
        f"[CHECK STATIC MODEL FROM BC] Statut inattendu: {response.status_code}\n{response.text}"
    )
    data = response.json()
    assert data is not None

    # Stockage de la réponse pour les assertions cross-step
    responses = ctx.setdefault('_responses', {})
    responses['CHECK STATIC MODEL FROM BC'] = data

    # ── Règles métier ──

    # Extraction des variables pour les étapes suivantes
    try:
        bc_static_model_version = data['version']
    except (KeyError, TypeError):
        bc_static_model_version = None
    assert bc_static_model_version is not None, (
        f"[CHECK STATIC MODEL FROM BC] 'bc_static_model_version' introuvable via data['version']: {data}"
    )
    ctx['bc_static_model_version'] = bc_static_model_version
    if VERBOSITY in ("-v", "-vv"):
        print(f"  → bc_static_model_version = {bc_static_model_version}")



# # STEP DISABLED — enabled: false in rules YAML
# @pytest.mark.dependency(name='test_02_trigg_push')
# def test_02_trigg_push(ctx):
#     """
#     Étape 2 : TRIGG PUSH
#     Utilise : organization_id, bov2_host, bov2_token
#     Extrait pour la suite : multipush_transaction_id, target_01_push_transacation_id, target_02_push_transacation_id
#     Validation : TriggPushResponse
#     """
#     env = {**get_env(), **ctx}
#     url = f"{env['bov2_host']}/p/sync-manager/api/1/organization/{env['organization_id']}/batch-centralized-base"
#     headers = {
#         "Authorization": f"Bearer {env['bov2_token']}"
#     }
#
#     body = {'siteIds': [4737, 4752], 'note': '', 'options': {'Kds': False, 'V2': True, 'Users': False, 'AccountingExportSettings': False, 'MenuAutomationSettings': False}}
#
#     response = httpx.post(url, headers=headers, json=body, timeout=30)
#
#     # Assertions de base
#     assert response.status_code in (200, 201), (
#         f"[TRIGG PUSH] Statut inattendu: {response.status_code}\n{response.text}"
#     )
#     data = response.json()
#     assert data is not None
#
#     # Stockage de la réponse pour les assertions cross-step
#     responses = ctx.setdefault('_responses', {})
#     responses['TRIGG PUSH'] = data
#
#     # Validation Pydantic du schéma de réponse
#     validated = TriggPushResponse.model_validate(data)
#     assert validated is not None, (
#         f"[TRIGG PUSH] Validation Pydantic échouée: {data}"
#     )
#
#     # ── Règles métier ──
#
#     # Extraction des variables pour les étapes suivantes
#     try:
#         multipush_transaction_id = data['data']['id']
#     except (KeyError, TypeError):
#         multipush_transaction_id = None
#     assert multipush_transaction_id is not None, (
#         f"[TRIGG PUSH] 'multipush_transaction_id' introuvable via data['data']['id']: {data}"
#     )
#     ctx['multipush_transaction_id'] = multipush_transaction_id
#     if VERBOSITY in ("-v", "-vv"):
#         print(f"  → multipush_transaction_id = {multipush_transaction_id}")
#
#     try:
#         target_01_push_transacation_id = data['syncs']
#     except (KeyError, TypeError):
#         target_01_push_transacation_id = None
#     assert target_01_push_transacation_id is not None, (
#         f"[TRIGG PUSH] 'target_01_push_transacation_id' introuvable via data['syncs']: {data}"
#     )
#     ctx['target_01_push_transacation_id'] = target_01_push_transacation_id
#     if VERBOSITY in ("-v", "-vv"):
#         print(f"  → target_01_push_transacation_id = {target_01_push_transacation_id}")
#
#     try:
#         target_02_push_transacation_id = data['syncs']
#     except (KeyError, TypeError):
#         target_02_push_transacation_id = None
#     assert target_02_push_transacation_id is not None, (
#         f"[TRIGG PUSH] 'target_02_push_transacation_id' introuvable via data['syncs']: {data}"
#     )
#     ctx['target_02_push_transacation_id'] = target_02_push_transacation_id
#     if VERBOSITY in ("-v", "-vv"):
#         print(f"  → target_02_push_transacation_id = {target_02_push_transacation_id}")
#
#
#
# # STEP DISABLED — enabled: false in rules YAML
# @pytest.mark.dependency(name='test_03_check_push_progress')
# def test_03_check_push_progress(ctx):
#     """
#     Étape 3 : CHECK PUSH PROGRESS
#     Utilise : organization_id, bov2_host, bov2_token
#     Validation : CheckPushProgressResponse
#     """
#     env = {**get_env(), **ctx}
#     url = f"{env['bov2_host']}/p/sync-manager/api/1/organization/{env['organization_id']}/batch-centralized-base?skip=0&limit=50"
#     headers = {
#         "Authorization": f"Bearer {env['bov2_token']}"
#     }
#
#     response = httpx.get(url, headers=headers, timeout=30)
#
#     # Assertions de base
#     assert response.status_code in (200, 201), (
#         f"[CHECK PUSH PROGRESS] Statut inattendu: {response.status_code}\n{response.text}"
#     )
#     data = response.json()
#     assert data is not None
#
#     # Stockage de la réponse pour les assertions cross-step
#     responses = ctx.setdefault('_responses', {})
#     responses['CHECK PUSH PROGRESS'] = data
#
#     # Validation Pydantic du schéma de réponse
#     validated = CheckPushProgressResponse.model_validate(data)
#     assert validated is not None, (
#         f"[CHECK PUSH PROGRESS] Validation Pydantic échouée: {data}"
#     )
#
#     # ── Règles métier ──
#
#
#
@pytest.mark.dependency(name='test_04_check_static_model_from_target_1')
def test_04_check_static_model_from_target_1(ctx):
    """
    Étape 4 : CHECK STATIC MODEL FROM TARGET 1
    Utilise : target_01_cashpad_id
    Extrait pour la suite : target_01_static_model_version
    Validation : CheckStaticModelFromTarget1Response
    """
    env = {**get_env(), **ctx}
    url = f"http://{env['target_01_cashpad_id']}.vpn.osilia.com:9091/model/pull_model"
    headers = {

    }

    response = httpx.get(url, headers=headers, timeout=30)

    # Assertions de base
    assert response.status_code in (200, 201), (
        f"[CHECK STATIC MODEL FROM TARGET 1] Statut inattendu: {response.status_code}\n{response.text}"
    )
    data = response.json()
    assert data is not None

    # Stockage de la réponse pour les assertions cross-step
    responses = ctx.setdefault('_responses', {})
    responses['CHECK STATIC MODEL FROM TARGET 1'] = data

    # ── Règles métier ──

    # ── Assertions cross-step ──
    if 'CHECK STATIC MODEL FROM BC' in responses:
        _src = responses["CHECK STATIC MODEL FROM BC"]["model"]["layout"]
        _tgt = responses["CHECK STATIC MODEL FROM TARGET 1"]["model"]["layout"]
        assert deep_sort(_src) == deep_sort(_tgt), (
            f"Le noeud model.layout n'est pas identique entre la BC et le device target 1 — src={_src!r}, tgt={_tgt!r}"
        )

    # Extraction des variables pour les étapes suivantes
    try:
        target_01_static_model_version = data['version']
    except (KeyError, TypeError):
        target_01_static_model_version = None
    assert target_01_static_model_version is not None, (
        f"[CHECK STATIC MODEL FROM TARGET 1] 'target_01_static_model_version' introuvable via data['version']: {data}"
    )
    ctx['target_01_static_model_version'] = target_01_static_model_version
    if VERBOSITY in ("-v", "-vv"):
        print(f"  → target_01_static_model_version = {target_01_static_model_version}")



@pytest.mark.dependency(name='test_05_check_static_model_from_target_2')
def test_05_check_static_model_from_target_2(ctx):
    """
    Étape 5 : CHECK STATIC MODEL FROM TARGET 2
    Utilise : target_02_cashpad_id
    Extrait pour la suite : target_02_static_model_version
    Validation : CheckStaticModelFromTarget2Response
    """
    env = {**get_env(), **ctx}
    url = f"http://{env['target_02_cashpad_id']}.vpn.osilia.com:9091/model/pull_model"
    headers = {

    }

    response = httpx.get(url, headers=headers, timeout=30)

    # Assertions de base
    assert response.status_code in (200, 201), (
        f"[CHECK STATIC MODEL FROM TARGET 2] Statut inattendu: {response.status_code}\n{response.text}"
    )
    data = response.json()
    assert data is not None

    # Stockage de la réponse pour les assertions cross-step
    responses = ctx.setdefault('_responses', {})
    responses['CHECK STATIC MODEL FROM TARGET 2'] = data

    # ── Règles métier ──

    # ── Assertions cross-step ──
    if 'CHECK STATIC MODEL FROM BC' in responses:
        _src = responses["CHECK STATIC MODEL FROM BC"]["model"]["layout"]
        _tgt = responses["CHECK STATIC MODEL FROM TARGET 2"]["model"]["layout"]
        assert deep_sort(_src) == deep_sort(_tgt), (
            f"Le noeud model.layout n'est pas identique entre la BC et le device target 2 — src={_src!r}, tgt={_tgt!r}"
        )

    # Extraction des variables pour les étapes suivantes
    try:
        target_02_static_model_version = data['version']
    except (KeyError, TypeError):
        target_02_static_model_version = None
    assert target_02_static_model_version is not None, (
        f"[CHECK STATIC MODEL FROM TARGET 2] 'target_02_static_model_version' introuvable via data['version']: {data}"
    )
    ctx['target_02_static_model_version'] = target_02_static_model_version
    if VERBOSITY in ("-v", "-vv"):
        print(f"  → target_02_static_model_version = {target_02_static_model_version}")



@pytest.mark.dependency(depends=["test_01_check_static_model_from_bc", "test_02_trigg_push", "test_03_check_push_progress", "test_04_check_static_model_from_target_1", "test_05_check_static_model_from_target_2"])
def test_consistency(ctx):
    """Vérifie que toutes les variables dynamiques ont bien été propagées"""
    expected = [
        "bc_static_model_version",
        "multipush_transaction_id",
        "target_01_push_transacation_id",
        "target_01_static_model_version",
        "target_02_push_transacation_id",
        "target_02_static_model_version",
    ]
    for var in expected:
        assert ctx.get(var), (
            f"Variable '{var}' manquante ou vide en fin de séquence"
        )
    if VERBOSITY != "-q":
        print("\n✅ Consistance OK - toutes les variables dynamiques sont présentes")
