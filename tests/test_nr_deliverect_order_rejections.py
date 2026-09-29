from __future__ import annotations

"""
Test de non-régression porté — `cashpad-bov2-non-reg-deliverect`,
tests/deliverect/orders/test_deliverect_order_unknown_product.py,
test_deliverect_order_unknown_subitem_product.py, test_deliverect_order_wrong_total_amount.py

Une commande Deliverect invalide est ACCUSÉE en 201 par le webhook, puis passe en
statut `failed` dans la liste des commandes du connecteur, sans ticket caisse :

    POST {base}/p/partners/public/1/webhooks/deliverect/orders?locationId=<location>
    GET  {base}/p/partners/api/2/site/<site>/connector/<deliverect>/orders   (JWT du front)

Cas couverts : produit inconnu, option (subItem) inconnue, montant payé incohérent.

Sûreté : les deux premiers cas portent un PLU inexistant — même pivot que
test_bov2kaban_2262, la commande ne peut pas atteindre la caisse. Le cas « montant
incohérent » porte des produits réels : si le contrôle du total régressait, un
ticket serait créé. Il est donc seul sous `tickets_guard` (NR_ALLOW_WRITES=1).

Résidu assumé : une commande `failed` par cas et par run dans la liste du connecteur.

Observé le 2026-09-29 sur le staging (webhook 201 `{}`, puis en base `orders` :
statut `preparing` → `failed` en ~0,4 s, `display_id` = `channelOrderDisplayId`,
`receipt_id` vide), puis relu par la route BO avec le JWT du front (sign-in sso) :
la commande apparaît sous `data[].displayId`, `status: failed`.

⚠️ Commandes SANS frais de service. Du 2026-08-13 au 2026-09-29, la config Deliverect
du staging avait `products.serviceCharge: null` : toute commande facturant des frais
de service y échouait déjà (« Missing service charge product for siteId: 4652 »),
et les trois cas passaient en `failed` quel que soit le défaut testé. Pour que le
test reste discriminant même si la config dérive à nouveau, `serviceCharge` est mis
à 0 et le montant payé ajusté : seul le défaut visé fait échouer la commande
(vérifié en base : `error` = « Item not found for AAAAAAAA-… » seul).

L'ancien repo sautait l'assertion de statut en silence quand `failed` n'arrivait
pas ; ici le test échoue.

Lancer :
    uv run --with pytest --with httpx --with python-dotenv \
      pytest tests/test_nr_deliverect_order_rejections.py -v
"""

import pytest
from dotenv import load_dotenv

load_dotenv()

from _nr import connector_order, deliverect_order, deliverect_push, tickets_guard

UNKNOWN_PLU = "AAAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA"


def order_without_service_charge() -> dict:
    """`order_simple` sans frais de service (cf. en-tête) : 46,40 € au lieu de 56,40 €."""
    order = deliverect_order("order_simple")
    order["payment"]["amount"] -= order["serviceCharge"]
    order["serviceCharge"] = 0
    return order


def push_and_expect_failed(order: dict) -> dict:
    status, payload = deliverect_push(order)
    assert status == 201, f"webhook Deliverect : attendu 201, reçu {status} — {payload!r}"
    listed = connector_order("deliverect", order["channelOrderDisplayId"],
                             done=lambda o: o.get("status") == "failed")
    assert listed["status"] == "failed", f"statut : {listed!r}"
    return listed


def test_01_unknown_product_fails_the_order():
    order = order_without_service_charge()
    order["items"][0]["plu"] = UNKNOWN_PLU
    push_and_expect_failed(order)


def test_02_unknown_option_fails_the_order():
    order = order_without_service_charge()
    order["items"][1]["subItems"][0]["plu"] = UNKNOWN_PLU
    push_and_expect_failed(order)


@tickets_guard()
def test_03_inconsistent_paid_amount_fails_the_order():
    order = order_without_service_charge()
    order["payment"]["amount"] = 3300  # 33,00 € payés pour 46,40 € commandés
    push_and_expect_failed(order)
