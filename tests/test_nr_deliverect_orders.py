from __future__ import annotations

"""
Test de non-régression porté — `cashpad-bov2-non-reg-deliverect`,
tests/deliverect/orders/test_deliverect_order.py, test_deliverect_order_with_menu.py,
test_deliverect_order_with_product_options.py

Simule Deliverect : le webhook de commande est poussé tel que Deliverect l'envoie,
puis la commande est suivie dans la liste du connecteur et le ticket lu sur la caisse.

    POST {base}/p/partners/public/1/webhooks/deliverect/orders?locationId=<location>
        body: payloads/deliverect/<order>.json.tmpl (commande déjà payée)
    GET  {base}/p/partners/api/2/site/<site>/connector/<deliverect>/orders   (JWT du front)
    GET  http://<CASHPAD_ID>.vpn.osilia.com:9091/reports/get_receipt_content?sequential_id=

Le webhook n'est PAS la Partner API : c'est la route d'entrée du connecteur
Deliverect, gardée telle quelle.

⚠️ CRÉE TROIS TICKETS PAYÉS sur la caisse à chaque run (`tickets_guard`, NR_ALLOW_WRITES=1).

Conventions Deliverect, reprises de l'ancien repo :
  - montants en CENTIMES (5640 = 56,40 €) → ×10 pour les millièmes de la caisse ;
  - produit « DELIVERY FEES » (C8E24C10-…) et « SERVICE CHARGE » (717A4374-…) ajoutés
    au ticket d'après la config du connecteur ;
  - le ticket se retrouve SUR LA CAISSE par son `deliveryId` = `channelOrderDisplayId`
    (`_nr.device_receipt_by_delivery_id`). Observé le 2026-09-29 : côté BOV2 la
    commande reste `preparing` avec `receiptId` vide, alors que le ticket existe —
    l'ancien test attendait la sortie de `preparing` et sautait ses assertions ;
  - menu : la remarque de l'article est agrégée à la note du ticket
    (`<note>\n<nom de l'article>: <remarque>`), les composants deviennent des lignes
    produit (PLU `<prefixe>_<uuid>`).

Précondition du banc : la config Deliverect doit porter les deux produits de frais
(`products.deliveryFee` et `products.serviceCharge`), sinon test_01 et test_03
passent en `failed` (« Missing service charge product for siteId: … »). Le
staging l'avait perdue du 2026-08-13 au 2026-09-29 (connector_configs 1224,
`serviceCharge: null`), rétablie le 2026-09-29 à 19:40 UTC. Un rouge de ce type
est une dérive de config, pas un défaut produit.

OBSERVÉ au run staging du 2026-09-29 : premier run rouge (tickets 3221–3223 bien créés,
mais la commande restait `preparing` — d'où la recherche par `deliveryId`), second run vert.

Lancer :
    NR_ALLOW_WRITES=1 uv run --with pytest --with httpx --with python-dotenv \
      pytest tests/test_nr_deliverect_orders.py -v
"""

import pytest
from dotenv import load_dotenv

load_dotenv()

from _nr import (connector_order, deliverect_order, deliverect_push, device_receipt_by_delivery_id,
                 receipt_addon, receipt_item, tickets_guard)

pytestmark = tickets_guard()

DELIVERY_FEES_PRODUCT = "C8E24C10-1D47-4380-96CE-649EDC8B180C"
SERVICE_CHARGE_PRODUCT = "717A4374-7D93-46FF-A4F2-83D8C8C14EC4"


def push_and_read(name: str):
    order = deliverect_order(name)
    status, payload = deliverect_push(order)
    assert status == 201, f"webhook Deliverect : attendu 201, reçu {status} — {payload!r}"
    listed = connector_order("deliverect", order["channelOrderDisplayId"], done=lambda o: bool(o.get("status")))
    assert listed["status"] != "failed", f"commande Deliverect en échec : {listed!r}"
    receipt = device_receipt_by_delivery_id(order["channelOrderDisplayId"])
    return order, receipt


def assert_paid_total(order: dict, receipt: dict):
    expected = order["payment"]["amount"] * 10
    assert receipt["amountTotal"] == receipt["amountPaid"] == expected, (
        f"amountTotal {receipt.get('amountTotal')!r} / amountPaid {receipt.get('amountPaid')!r}, attendu {expected}"
    )


def assert_items_and_options(order: dict, receipt: dict):
    for item in order["items"]:
        line = receipt_item(receipt, item["plu"])
        assert line["qty"] == item["quantity"] * 1000, f"{item['name']} : qty {line.get('qty')!r}"
        assert line["priceInclTaxes"] == item["price"] * 10, f"{item['name']} : prix {line.get('priceInclTaxes')!r}"
        for sub in item.get("subItems") or []:
            addon = receipt_addon(receipt, sub["plu"])
            assert addon["qty"] == sub["quantity"], f"option {sub['name']} : qty {addon.get('qty')!r}"
            if "priceInclTaxes" in addon:
                assert addon["priceInclTaxes"] == sub["price"] * 10, f"option {sub['name']} : prix {addon!r}"


def test_01_simple_order_reaches_the_device_with_fees():
    order, receipt = push_and_read("order_simple")
    assert receipt["deliveryId"] == order["channelOrderDisplayId"], f"deliveryId : {receipt.get('deliveryId')!r}"
    assert receipt["note"] == order["note"], f"note : {receipt.get('note')!r}"
    assert_paid_total(order, receipt)
    assert receipt_item(receipt, DELIVERY_FEES_PRODUCT)["priceInclTaxes"] == order["deliveryCost"] * 10
    assert receipt_item(receipt, SERVICE_CHARGE_PRODUCT)["priceInclTaxes"] == order["serviceCharge"] * 10
    assert_items_and_options(order, receipt)


def test_02_menu_order_expands_components_and_aggregates_remarks():
    order, receipt = push_and_read("order_with_menu")
    menu = order["items"][0]
    assert receipt["deliveryId"] == order["channelOrderDisplayId"], f"deliveryId : {receipt.get('deliveryId')!r}"
    expected_note = f"{order['note']}\n{menu['name']}: {menu['remark']}"
    assert receipt["note"] == expected_note, f"note {receipt.get('note')!r}, attendu {expected_note!r}"
    assert_paid_total(order, receipt)
    assert receipt_item(receipt, menu["plu"])["priceInclTaxes"] == menu["price"] * 10
    for component in menu["subItems"]:
        line = receipt_item(receipt, component["plu"].split("_")[1])
        assert line["qty"] == component["quantity"] * 1000, f"{component['name']} : qty {line.get('qty')!r}"
        assert line["priceInclTaxes"] == component["price"] * 10, f"{component['name']} : prix {line!r}"
        for addon in component.get("subItems") or []:
            receipt_addon(receipt, addon["plu"])


def test_03_order_with_options_keeps_options_and_payment():
    order, receipt = push_and_read("order_with_options")
    assert receipt["deliveryId"] == order["channelOrderDisplayId"], f"deliveryId : {receipt.get('deliveryId')!r}"
    assert receipt["note"] == order["note"], f"note : {receipt.get('note')!r}"
    assert_paid_total(order, receipt)
    assert receipt["payments"][0]["amount"] == order["payment"]["amount"] * 10, f"paiement : {receipt['payments']!r}"
    assert_items_and_options(order, receipt)
