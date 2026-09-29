from __future__ import annotations

"""
Test de non-régression généré par /cp-test — ticket BOV2KABAN-2190
[BACK] Expose partner API to list & fetch customers

Fige le comportement OBSERVÉ et VALIDÉ le 2026-09-04 sur le staging
(host allowlisté : staging.cashpad.app), endpoint public partner customers :

    GET {STAGING_BASE_URL}/api/customers/v1/{INSTALLATION_ID}/get_customers
        ?apiuser_email=...&apiuser_token=...[&updated_since_version=N]

Auth = credentials partner (apiuser_email / apiuser_token) en query string —
même schéma que test_bov2kaban_2121 et les test_cp_partners_*, pas le bearer
BOV2_STAGING_TOKEN des services digested-data/partners.

Observé lors de la vérification (installation cashpad-8007, partenaire obypay) :
92 clients, 39 champs chacun, schéma identique sur les 92, versions [909..1131]
toutes distinctes, **0 client soft-deleted** sur 92.

Historique — la vérification du 2026-09-03 renvoyait 9 clients dont 8
soft-deleted : le filtre soft-delete demandé par l'AC révisée n'était pas posé
et `test_03` était marqué `xfail`. Le correctif est livré (0/92 le 2026-09-04)
→ marqueur retiré, `test_03` est désormais un vrai garde-fou de non-régression.

⚠️ Divergence connue, non tranchée (signalée sur le ticket) : la borne de
`updated_since_version` est **inclusive** (`version >= valeur`), alors que la
section Solution du ticket écrit "return only customers whose version is greater
than the given value" (borne stricte). `test_02` fige l'inclusif, c'est-à-dire
l'observé. Si l'équipe corrige le code plutôt que le libellé, ce step tombera —
c'est voulu : le passage inclusif → strict doit être un échec visible, pas un
changement silencieux.

Golden ciblé : status_code + uniquement les invariants liés aux acceptance
criteria. Pas de snapshot complet, ni de comptes exacts — le jeu de données du
site de test continue d'évoluer. La borne de `updated_since_version` est
recalculée depuis la liste complète lue au même instant : c'est la SÉMANTIQUE
qui est figée, pas les versions du jour.

Lecture seule : seuls des GET sur get_customers sont émis. Ne jamais appeler
add_credit_operation depuis ce repo — c'est un GET qui ÉCRIT.
"""

import os

import httpx
import pytest
from dotenv import load_dotenv

load_dotenv()


from _target import partner_env

# Champs standard attendus par le ticket (identité, contact, adresse, fidélité,
# solde, version, soft-delete) — repris du schéma de la doc partenaires.
STANDARD_FIELDS = {
    "id",
    "externalId",
    "firstName",
    "lastName",
    "name",
    "email",
    "phone",
    "street",
    "zipCode",
    "city",
    "country",
    "company",
    "code",
    "dateCreated",
    "dateLastSeen",
    "deleted",
    "version",
    "loyaltyPoints",
    "loyaltyPointsValue",
    "account",
    "balance",
    "type",
    "pendingCashback",
}


def get_env() -> dict:
    """Cible, alias et couple partenaire — cf. `_target.py` (NR_TARGET)."""
    env = partner_env()
    return env


def call_get_customers(*, email=None, token=None, **params):
    """GET get_customers. Renvoie (status_code, payload). Auth en query string."""
    env = get_env()
    base = env["base_url"].rstrip("/")
    query = {
        "apiuser_email": env["apiuser_email"] if email is None else email,
        "apiuser_token": env["apiuser_token"] if token is None else token,
        **params,
    }
    url = f"{base}/api/customers/v1/{env['installation_id']}/get_customers"
    response = httpx.get(url, params=query, timeout=60)
    try:
        return response.status_code, response.json()
    except ValueError:
        return response.status_code, None


@pytest.fixture(scope="module")
def all_customers() -> list:
    """Appel réel unique de l'endpoint, liste complète partagée entre les steps."""
    status, payload = call_get_customers()
    assert status == 200, f"HTTP {status} sur get_customers : {payload}"
    assert payload["succeeded"] is True
    return payload["customers"]


def test_01_returns_all_customers_with_standard_fields(all_customers):
    """AC1 : la liste complète est retournée, chaque client porte les champs standard."""
    assert all_customers, "Aucun client retourné — le site de test s'est-il vidé ?"
    for customer in all_customers:
        missing = STANDARD_FIELDS - set(customer)
        assert not missing, f"Champs standard manquants sur {customer.get('id')} : {sorted(missing)}"


def test_02_updated_since_version_uses_an_inclusive_bound(all_customers):
    """AC2 : `updated_since_version` filtre sur version >= valeur (borne INCLUSIVE).

    La référence est recalculée depuis la liste complète lue au même instant :
    c'est la sémantique de la borne qui est figée, pas les versions du jour.

    Les trois premiers pivots sont des versions RÉELLEMENT présentes dans le jeu
    de données — c'est ce qui rend le step discriminant : un pivot absent (ex.
    1000 alors qu'aucun client ne porte cette version) donne le même résultat en
    inclusif et en strict, et ne prouve rien. Vérifié le 2026-09-04 : pivot 1053
    → 46 clients (`>=` 46, `>` 45, le client en 1053 est bien renvoyé), pivot
    1131 (max) → 1 client au lieu de 0.

    ⚠️ Le ticket spécifie une borne STRICTE ("version greater than the given
    value") : cet écart est signalé sur BOV2KABAN-2190 et non tranché. Ce step
    fige l'observé, donc il ÉCHOUERA si le code passe en strict — c'est le
    signal attendu, pas un faux positif.
    """
    versions = sorted(c["version"] for c in all_customers)
    pivots = {versions[0], versions[len(versions) // 2], versions[-1], versions[-1] + 1000}

    for pivot in sorted(pivots):
        status, payload = call_get_customers(updated_since_version=pivot)
        assert status == 200, f"HTTP {status} avec updated_since_version={pivot} : {payload}"
        assert payload["succeeded"] is True

        returned = sorted(c["version"] for c in payload["customers"])
        expected = [v for v in versions if v >= pivot]
        assert returned == expected, (
            f"updated_since_version={pivot} : borne non inclusive ou filtre incorrect — "
            f"reçu {returned}, attendu {expected}"
        )


def test_03_soft_deleted_customers_are_not_listed(all_customers):
    """AC3 (révisé le 2026-09-03) : seuls les clients NON soft-deleted sont listés.

    Attendu aligné sur BOV1. Le champ `deleted` reste exposé — c'est sa VALEUR
    qui doit toujours être False dans la liste.

    Correctif livré : 0/92 le 2026-09-04, contre 8/9 la veille. Le marqueur
    `xfail` a été retiré — toute réapparition d'un client supprimé est
    désormais un échec franc.
    """
    for customer in all_customers:
        assert isinstance(customer["deleted"], bool), (
            f"`deleted` non booléen sur {customer.get('id')} : {customer['deleted']!r}"
        )

    soft_deleted = [c["id"] for c in all_customers if c["deleted"]]
    assert not soft_deleted, (
        f"{len(soft_deleted)} client(s) soft-deleted présents dans la réponse "
        f"sur {len(all_customers)} : {soft_deleted}"
    )


def test_04_invalid_credentials_are_rejected():
    """AC4 (auth) : un couple (email, token) inconnu ne résout aucune installation → 404."""
    status, payload = call_get_customers(
        email="nobody@example.invalid",
        token="00000000-0000-0000-0000-000000000000",
    )
    assert status == 404, f"Attendu 404 sur identifiants invalides, reçu {status} : {payload}"


def test_05_missing_credentials_hit_the_capability_gate():
    """AC4 : sans `apiuser_*`, la requête est rejetée par le contrôle de capability → 403.

    Contre-partie non conditionnelle de `test_06` : le connecteur résolu en
    l'absence d'identifiants ne porte pas la capability `customer`, et le rejet
    est explicite. Observé le 2026-09-04 :
        403 {"name":"Forbidden","message":"The capability \\"customer\\" is not
        supported. Supported capabilities are: payment, stock, menu.", ...}
    Ce qui est figé : le rejet et son motif, pas la liste des capabilities
    supportées (elle bougera au fil des livraisons).
    """
    env = get_env()
    url = f"{env['base_url'].rstrip('/')}/api/customers/v1/{env['installation_id']}/get_customers"
    response = httpx.get(url, timeout=60)

    assert response.status_code == 403, (
        f"Attendu 403 sans identifiants, reçu {response.status_code} : {response.text[:300]}"
    )
    payload = response.json()
    assert "capability" in payload.get("message", "").lower(), (
        f"Rejet non motivé par la capability : {payload}"
    )
    assert "customers" not in payload, f"Des données ont fuité dans le rejet : {payload}"


def test_06_partner_without_customer_capability_is_rejected():
    """AC4 : un partenaire installé sur le site mais SANS la capability `customer` → 403.

    Couple optionnel : ce scénario exige un SECOND partenaire installé sur la même
    installation. Absent du .env, le step est ignoré plutôt qu'en échec.
    """
    email = os.getenv("NOCAP_APIUSER_EMAIL")
    token = os.getenv("NOCAP_APIUSER_TOKEN")
    if not email or not token:
        pytest.skip("NOCAP_APIUSER_EMAIL / NOCAP_APIUSER_TOKEN absents de .env")

    status, payload = call_get_customers(email=email, token=token)
    assert status == 403, f"Attendu 403 sur capability absente, reçu {status} : {payload}"
    assert "capability" in payload.get("message", "").lower(), (
        f"Message de rejet inattendu : {payload}"
    )
