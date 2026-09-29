from __future__ import annotations

"""
Test de non-régression porté — `cashpad-bov2-non-reg-deliverect`,
tests/partners/model/test_get_payment_methods.py

Fige le comportement OBSERVÉ le 2026-09-29 sur le staging ET la préprod
(cashpad-8007, partenaire obypay) :

    GET {base}/api/model/v1/{INSTALLATION_ID}/paymentmethods
        ?apiuser_email=...&apiuser_token=...

Route documentée (doc Notion « Data retrieval »). L'ancien test passait par la route
native `/p/partners/public/1/obypay/cashpad-8007/model/payment-methods` : non
documentée, abandonnée ici.

Observé : 9 moyens de paiement, enveloppe `{version, succeeded, data}`. Les 7
premiers sont ceux que l'ancien test figeait (id → libellé) ; `TIP` et `VUNCHER`
sont apparus depuis. Seuls les 7 historiques sont figés — un moyen ajouté ne doit
pas faire rougir la suite, un moyen retiré ou renommé, si.

Lecture seule.

Lancer :
    uv run --with pytest --with httpx --with python-dotenv \
      pytest tests/test_nr_partners_model_payment_methods.py -v
"""

import pytest
from dotenv import load_dotenv

load_dotenv()

from _nr import partner_call

EXPECTED = {
    "2F4D154E-2397-4E86-A244-85AE8C805F2B": "Espèces",
    "B2C2161B-F3B6-435F-9E35-61973B3389D1": "CB",
    "10140245-C3C8-4415-AD27-ACC0A8C6948E": "TR",
    "BAF9848B-FEEA-471B-AFB7-877BBDB1942D": "Carte TR",
    "d2e011c4-919b-11e3-b450-001a92ba1fbf": "Compte client",
    "664BC77D-BF6E-47E4-A9BB-DBD83CA9A74F": "Cheques",
    "92CBCABE-CFB7-449A-BFF1-4BEF3C1F8AB3": "Deliveroo",
}


@pytest.fixture(scope="module")
def response():
    return partner_call("model", 1, "paymentmethods")


def test_01_status_and_envelope(response):
    status, payload = response
    assert status == 200, f"attendu 200, reçu {status} — {payload!r}"
    assert payload.get("succeeded") is True, f"succeeded attendu : {payload!r}"
    assert isinstance(payload.get("data"), list), f"`data` doit être une liste : {payload!r}"


@pytest.mark.parametrize("method_id,name", EXPECTED.items())
def test_02_historical_payment_methods_are_exposed(response, method_id, name):
    _, payload = response
    by_id = {m["id"].upper(): m for m in payload["data"]}
    assert method_id.upper() in by_id, f"moyen {name!r} ({method_id}) absent — ids : {sorted(by_id)}"
    assert by_id[method_id.upper()]["name"] == name, (
        f"{method_id} : libellé {by_id[method_id.upper()]['name']!r}, attendu {name!r}"
    )


def test_03_every_method_has_the_documented_shape(response):
    """Doc : `{id, name, external_id, type}`, `type` = énumération entière."""
    _, payload = response
    for m in payload["data"]:
        assert {"id", "name", "external_id", "type"} <= set(m), f"clés manquantes : {m!r}"
        assert isinstance(m["type"], int), f"`type` non entier : {m!r}"
