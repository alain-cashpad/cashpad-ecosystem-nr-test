from __future__ import annotations

"""
Test de non-régression généré par /cp-test — ticket BOV2KABAN-2192
[BACK] Expose partner API to update a customer

Fige le comportement OBSERVÉ et VALIDÉ le 2026-09-04 sur le staging
(host allowlisté : staging.cashpad.app), endpoint partner customers :

    POST {STAGING_BASE_URL}/api/customers/v1/{INSTALLATION_ID}/update_customer
        ?apiuser_email=...&apiuser_token=...[&id=<uuid>]
    body JSON : identifiant (optionnel ici) + champs à mettre à jour

Auth = credentials partner (apiuser_email / apiuser_token) en query string —
même schéma que test_bov2kaban_2190, pas le bearer BOV2_STAGING_TOKEN des
services digested-data/partners.

⚠️ NON DESTRUCTIF PAR CONSTRUCTION. `update_customer` est une écriture, mais
aucun step de ce fichier ne touche à un client réel : tous ciblent un UUID
inexistant, un identifiant absent, ou des identifiants partenaire invalides.
Le seul chemin qui muterait des données — un `id` de client existant — n'est
volontairement PAS couvert ici :
  - la sémantique de l'update (patch partiel vs remplacement complet) est un
    point produit non tranché, suivi en BOV2KABAN-2280 ;
  - un update réussi DÉTRUIT les champs non transmis (cf. 2280), donc le figer
    en NR exigerait de recréer un client à chaque run.
AC1 de 2192 ("applies only the transmitted fields") est sorti du périmètre du
ticket vers 2280 : il n'a pas sa place ici tant que la décision n'est pas prise.

Périmètre couvert = les deux AC restants de 2192 :
  - AC2 "Non-existent customer returns an error response"
  - AC3 "Unauthorized partner is rejected"

Deux régressions précises que ce fichier garde, corrigées entre le 2026-09-03
et le 2026-09-04 :
  - `id` en query string était rejeté par `400 {"id":"ObjectUnknown"}` avant
    d'atteindre le handler → `test_02` verrouille la forme documentée ;
  - un client inexistant renvoyait `"internal communication error"`
    (`errorCode: 5`) au lieu de l'erreur métier → `test_01`/`test_02`
    verrouillent le libellé `"Unknown customer"`.

Golden ciblé : status_code + le champ `error` et le flag `succeeded`. Pas de
snapshot complet — les backtraces et le détail interne bougent à chaque build.

Ne JAMAIS ajouter d'appel à `add_credit_operation` dans ce repo : c'est un GET
qui ÉCRIT (il crédite un compte client).
"""

import os

import httpx
import pytest
from dotenv import load_dotenv

load_dotenv()


from _target import partner_env, writes_guard

# Module en écriture : skippé hors staging sans NR_ALLOW_WRITES=1.
pytestmark = writes_guard()

# UUID v4 valide dans sa forme, garanti absent du référentiel clients.
# C'est ce qui rend tout ce fichier non destructif.
UNKNOWN_CUSTOMER_ID = "00000000-0000-4000-8000-000000000000"


def get_env() -> dict:
    """Cible, alias et couple partenaire — cf. `_target.py` (NR_TARGET)."""
    env = partner_env()
    return env


def post_update_customer(*, body=None, email=None, token=None, authenticated=True, **query):
    """POST update_customer. Renvoie (status_code, payload). Auth en query string.

    `authenticated=False` omet totalement le couple `apiuser_*` — c'est le
    scénario du contrôle de capability (test_04).
    """
    env = get_env()
    url = f"{env['base_url'].rstrip('/')}/api/customers/v1/{env['installation_id']}/update_customer"
    params = dict(query)
    if authenticated:
        params["apiuser_email"] = env["apiuser_email"] if email is None else email
        params["apiuser_token"] = env["apiuser_token"] if token is None else token

    response = httpx.post(url, params=params, json=body if body is not None else {}, timeout=60)
    try:
        return response.status_code, response.json()
    except ValueError:
        return response.status_code, None


def test_01_unknown_customer_by_id_in_body_returns_a_business_error():
    """AC2 : un `id` inconnu passé dans le corps → erreur métier documentée.

    Régression gardée : le 2026-09-03 la réponse était
    `{"succeeded": false, "error": "internal communication error", "errorCode": 5}`.
    Depuis le 2026-09-04 c'est le libellé métier attendu, aligné sur BOV1.
    """
    status, payload = post_update_customer(body={"id": UNKNOWN_CUSTOMER_ID, "city": "Nowhere"})

    assert status == 422, f"Attendu 422 sur client inconnu, reçu {status} : {payload}"
    assert payload["succeeded"] is False
    assert payload["error"] == "Unknown customer", (
        f"Erreur métier attendue 'Unknown customer', reçu {payload.get('error')!r} — "
        "retour à une erreur interne générique ?"
    )
    assert "errorCode" not in payload, (
        f"`errorCode` de retour (signature de l'erreur interne du 2026-09-03) : {payload}"
    )


def test_02_unknown_customer_by_id_in_query_string_reaches_the_handler():
    """AC2 : l'identifiant en QUERY STRING est accepté — forme documentée BOV1.

    Régression gardée : le 2026-09-03 cette forme était rejetée par
    `400 {"id": "ObjectUnknown"}` sans atteindre le handler. Un retour du 400
    signifierait que la validation d'entrée a de nouveau perdu le param de query.
    Le corps ne porte ici QUE le champ à modifier, comme le spécifie le ticket.
    """
    status, payload = post_update_customer(body={"city": "Nowhere"}, id=UNKNOWN_CUSTOMER_ID)

    assert status != 400, (
        f"400 sur l'identifiant en query string — régression du rejet 'ObjectUnknown' : {payload}"
    )
    assert status == 422, f"Attendu 422 sur client inconnu, reçu {status} : {payload}"
    assert payload["succeeded"] is False
    assert payload["error"] == "Unknown customer", (
        f"Erreur métier attendue 'Unknown customer', reçu {payload.get('error')!r}"
    )


def test_03_missing_identifier_is_rejected():
    """Aucun identifiant transmis → erreur métier explicite (ni 500, ni update aveugle).

    Le libellé observé (`Missing id or code or external_id param`) documente au
    passage que `code` et `external_id` existent en aval côté device — l'« open
    point » du ticket porte sur leur exposition BOV2, pas sur le modèle stocké.
    """
    status, payload = post_update_customer(body={"city": "Nowhere"})

    assert status == 422, f"Attendu 422 sans identifiant, reçu {status} : {payload}"
    assert payload["succeeded"] is False
    assert "missing id" in payload.get("error", "").lower(), (
        f"Erreur attendue sur identifiant manquant, reçu {payload.get('error')!r}"
    )


def test_04_missing_credentials_hit_the_capability_gate():
    """AC3 : sans `apiuser_*`, rejet par le contrôle de capability → 403.

    Ce qui est figé : le rejet et son motif, pas la liste des capabilities
    supportées (elle bougera au fil des livraisons de l'épic BOV2KABAN-2189).
    """
    status, payload = post_update_customer(
        body={"id": UNKNOWN_CUSTOMER_ID, "city": "Nowhere"},
        authenticated=False,
    )

    assert status == 403, f"Attendu 403 sans identifiants, reçu {status} : {payload}"
    assert "capability" in payload.get("message", "").lower(), (
        f"Rejet non motivé par la capability : {payload}"
    )


def test_05_invalid_credentials_are_rejected():
    """AC3 : un couple (email, token) inconnu ne résout aucune installation → 404."""
    status, payload = post_update_customer(
        body={"id": UNKNOWN_CUSTOMER_ID, "city": "Nowhere"},
        email="nobody@example.invalid",
        token="00000000-0000-0000-0000-000000000000",
    )

    assert status == 404, f"Attendu 404 sur identifiants invalides, reçu {status} : {payload}"


@pytest.mark.xfail(
    reason="BOV2KABAN-2192 : le `backtrace` est renvoyé dans le corps sur tous les chemins "
    "d'erreur (chemins /app/dist/..., arborescence node_modules, noms de classes) — "
    "divulgation interne sur une surface partenaire, non couverte par les acceptance "
    "criteria. XPASS = le correctif a été livré, retirer ce marqueur.",
    strict=False,
)
def test_06_error_responses_do_not_leak_a_backtrace():
    """Attendu : une erreur partenaire n'expose aucune trace d'exécution interne.

    Vérifié sur les trois chemins d'erreur métier — le contenu de la fuite est
    identique partout, donc figer les trois évite un correctif partiel qui ne
    nettoierait qu'un seul handler.
    """
    cases = {
        "id in body": dict(body={"id": UNKNOWN_CUSTOMER_ID, "city": "Nowhere"}),
        "id in query": dict(body={"city": "Nowhere"}, id=UNKNOWN_CUSTOMER_ID),
        "no identifier": dict(body={"city": "Nowhere"}),
    }
    leaking = {}
    for label, kwargs in cases.items():
        _, payload = post_update_customer(**kwargs)
        if payload and payload.get("backtrace"):
            leaking[label] = payload["backtrace"].splitlines()[0]

    assert not leaking, f"`backtrace` exposé sur {len(leaking)} chemin(s) d'erreur : {leaking}"
