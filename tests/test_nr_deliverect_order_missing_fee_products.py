from __future__ import annotations

"""
Test de non-régression porté — `cashpad-bov2-non-reg-deliverect`,
tests/deliverect/orders/test_deliverect_order_no_delivery_fees_product.py,
test_deliverect_order_no_service_charge_product.py

Si la config du connecteur Deliverect n'a pas de produit « frais de livraison »
(resp. « frais de service ») alors que la commande en facture, la commande passe
en `failed` :

    GET   {base}/p/partners/api/1/site/<site>/connector-configs/deliverect          (JWT du front)
    PATCH {base}/p/partners/api/1/site/<site>/connector-configs/deliverect?step=2   (JWT du front)
          body: {"config": {"defaultChannel", "channels": <sans channelName, products.X: null>}}
    POST  {base}/p/partners/public/1/webhooks/deliverect/orders?locationId=<location>

⚠️ MODIFIE LA CONFIG DU CONNECTEUR le temps du test (`tickets_guard`, NR_ALLOW_WRITES=1).
Différence voulue avec l'ancien repo : il restaurait une config FIGÉE dans un fichier
(`connector_update_config.json`, valeurs de staging), qui aurait écrasé toute
évolution de la config réelle — et rien n'était restauré si le test échouait avant
la fin. Ici la config COURANTE est lue, seul le produit visé est mis à `null`, et la
config lue est réécrite dans un `finally`.

Lecture de la config OBSERVÉE le 2026-09-29 (route de test_cp_partners_order_simple,
réponse `{data: {config: {...}}}`). L'étape 2 du PATCH n'accepte que `defaultChannel`
et `channels` (sans `channelName`) et FUSIONNE (cf. `step2_body`). Garde-fous : un
PATCH à blanc précède toute dégradation, et la restauration est vérifiée par relecture.
Vert au run staging du 2026-09-29 ; config relue identique en base après coup.

Lancer :
    NR_ALLOW_WRITES=1 uv run --with pytest --with httpx --with python-dotenv \
      pytest tests/test_nr_deliverect_order_missing_fee_products.py -v
"""

import copy

import pytest
from dotenv import load_dotenv

load_dotenv()

from _nr import bo_request, connector_order, deliverect_order, deliverect_push, site, tickets_guard

pytestmark = tickets_guard()


def configs_path() -> str:
    return f"1/site/{site()['site_id']}/connector-configs"


def current_config() -> dict:
    """Config Deliverect courante, COMPLÈTE. Échoue sans rien écrire si introuvable.

    Même route que test_cp_partners_order_simple (étape « GET CONNECTOR INFO »).
    Observé le 2026-09-29 : `{data: {config: {account, channels, defaultChannel,
    location, meta}}}`, deux canaux (`0` et un id Deliverect).
    """
    status, payload = bo_request("GET", f"{configs_path()}/deliverect")
    assert status in (200, 201), f"GET connector-configs/deliverect : HTTP {status} — {payload!r}"
    config = ((payload or {}).get("data") or {}).get("config") if isinstance(payload, dict) else None
    assert isinstance(config, dict) and isinstance(config.get("channels"), dict) and config["channels"], (
        f"config.channels introuvable — forme reçue : {str(payload)[:300]}"
    )
    return config


def step2_body(config: dict) -> dict:
    """Corps accepté par l'étape 2 (validator.deliverect-step2.ts) : `defaultChannel` et
    `channels` seulement, sans `channelName` — BOV2 le refuse (« is not allowed ») et le
    recalcule en interrogeant Deliverect (`fetchChannels`). L'étape 2 FUSIONNE ces canaux
    dans la config (`deepMergeRightPrioritized`) : `account`, `location`, `meta` intacts.
    Observé le 2026-09-29 : envoyer la config complète → 400 « config.account is not allowed… »."""
    channels = {cid: {k: v for k, v in channel.items() if k != "channelName"}
                for cid, channel in config["channels"].items()}
    return {"config": {"defaultChannel": config["defaultChannel"], "channels": channels}}


def comparable(channels: dict) -> dict:
    return {cid: {k: v for k, v in c.items() if k != "channelName"} for cid, c in channels.items()}


def patch_config(config: dict):
    status, payload = bo_request("PATCH", f"{configs_path()}/deliverect", params={"step": 2},
                                 body=step2_body(config))
    assert status == 200, f"PATCH connector-configs (step 2) : HTTP {status} — {payload!r}"


@pytest.mark.parametrize("product_key", ["deliveryFee", "serviceCharge"])
def test_01_order_fails_when_a_billed_fee_has_no_product(product_key):
    original = current_config()

    # PATCH à blanc AVANT de dégrader quoi que ce soit : si l'étape 2 échoue (Deliverect
    # injoignable pour `fetchChannels`, schéma changé…), la restauration échouerait aussi
    # et laisserait la config dégradée. On s'arrête donc ici, config intacte.
    patch_config(original)
    assert comparable(current_config()["channels"]) == comparable(original["channels"]), (
        "le PATCH à blanc a modifié la config — arrêt avant toute dégradation"
    )

    degraded = copy.deepcopy(original)
    for channel in degraded["channels"].values():
        channel.setdefault("products", {})[product_key] = None

    patch_config(degraded)
    try:
        order = deliverect_order("order_simple")  # facture deliveryCost ET serviceCharge
        status, payload = deliverect_push(order)
        assert status == 201, f"webhook Deliverect : attendu 201, reçu {status} — {payload!r}"
        listed = connector_order("deliverect", order["channelOrderDisplayId"],
                                 done=lambda o: o.get("status") == "failed")
        assert listed["status"] == "failed", f"{product_key} à null : statut {listed!r}"
    finally:
        patch_config(original)
        assert comparable(current_config()["channels"]) == comparable(original["channels"]), (
            "config Deliverect NON restaurée à l'identique — la vérifier à la main dans le BO"
        )
