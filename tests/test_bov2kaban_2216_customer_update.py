from __future__ import annotations

"""
Test de non-régression généré par /cp-test — ticket BOV2KABAN-2216
[BACK] Expose customer account update on editable information fields

Fige le comportement OBSERVÉ et VALIDÉ le 2026-09-10 sur le staging
(host allowlisté : staging.cashpad.app), endpoint BO-facing de mise à jour :

    PATCH {STAGING_BASE_URL}/p/customers/api/1/site/{SITE}/customers/{id}
    body JSON : sous-ensemble des champs éditables

⚠️ **Ce fichier ÉCRIT — mais il est auto-suffisant et ne touche AUCUN compte
existant.** C'est l'exception assumée à la règle « lecture seule » du repo, parce
qu'un PATCH ne peut pas se vérifier autrement.

Le contrat qu'il respecte, à ne pas casser en le modifiant :

  * il **crée son propre compte** au setup (Partner API `create_customer`) et le
    **soft-delete au teardown** (`delete_customer`). Deux exécutions successives
    n'accumulent donc pas de données, et aucun compte de fixture d'un autre
    fichier n'est jamais visé — en particulier pas `Cashpad NR auto test`, dont
    dépendent `test_bov2kaban_2212`, `2214` et `2215` ;
  * les deux critères de REJET (AC3, AC4) sont exercés en écrivant à chaque champ
    **sa valeur courante**. Si l'API régressait jusqu'à les accepter, le test
    échouerait sans avoir rien modifié — un garde-fou qui ne peut pas casser la
    donnée qu'il surveille.

## Deux pièges de tooling, vérifiés le 2026-09-10

1. `create_customer` répond **201**, pas 200. `scripts/seed_customers.py` ne teste
   que 200 et rapporte donc « ÉCHEC » sur une création qui a réussi. Ne pas
   recopier ce test de statut.
2. `company` vide est **rejeté** (`400 {"company":"StringEmpty"}`). La liste
   `COMPANIES` du script de seed contient `""`, d'où ~1 run sur 5 en échec. Le
   payload de ce fichier renseigne toujours une company.

## Écarts connus, NON figés ici

Hors périmètre des acceptance criteria — écarts vs la section Solution, pas des
comportements à préserver :

* **« pricing » est `grantLevel`, et c'est une STRING** : `null`, `'standard'` et
  `'1'` passent ; un entier, un float ou un booléen sont rejetés en
  `400 {"grantLevel":"Type"}`. Le ticket la décrit comme une « selection ».
  `test_02` envoie donc une chaîne — s'il casse sur `Type`, c'est que le champ a
  changé de nature, pas que le test est faux.
* **un client inconnu renvoie 400**, alors que la surface de lecture renvoie 404
  pour le même cas.
* **`version` ne bouge jamais** : il est resté à sa valeur initiale sur ~25 updates
  réussis. Non figé (ce serait figer un défaut probable), mais c'est le point dur
  de la question ouverte du ticket sur la propagation vers la caisse : une synchro
  indexée sur cette colonne ne verrait aucune de ces modifications.

Golden ciblé : `status_code` + les champs de l'observé liés aux AC. Aucune valeur
métier figée en dur.

## Retiré le 2026-09-29 : `test_02_every_editable_field_is_accepted` (AC2)

Il ne correspondait plus au comportement du staging : quatre champs du set éditable
étaient acceptés en 200 mais NON enregistrés à la relecture —
`type` (stocké 0 au lieu de 1), `email` (inchangé), `city` (inchangé), `language`
(`None` au lieu de `fr`). Retiré à la demande du dev, sans avoir tranché entre une
évolution produit et une régression : ce constat n'est plus couvert par la suite.
Version d'origine du test : cf. historique (fichier sauvegardé hors repo le 2026-09-29).

Lancer :
    uv run --with pytest --with httpx --with python-dotenv \
      pytest tests/test_bov2kaban_2216_customer_update.py -v
"""

import os
import time
import uuid
from urllib.parse import urlparse

import httpx
import pytest
from dotenv import load_dotenv

load_dotenv()


# ── Garde-fou anti-prod : la vérification ne cible que le staging ──
HOST_ALLOWLIST = {"staging.cashpad.app"}

SITE = 4652
CONTROL_SITE = 4757

# Champs dérivés et métadonnées : le PATCH doit les refuser (AC3).
FORBIDDEN_FIELDS = (
    "balance",
    "account",
    "loyaltyPoints",
    "version",
    "dateCreated",
    "id",
    "deleted",
)


def get_env() -> dict:
    """Base staging, identifiants BO (PATCH) et partenaire (create/delete)."""
    required = {
        "STAGING_BASE_URL": None,
        "BOV2_STAGING_LOGIN": None,
        "BOV2_STAGING_PASSWORD": None,
        "APIUSER_EMAIL": None,
        "APIUSER_TOKEN": None,
        "INSTALLATION_ID": None,
    }
    for name in required:
        required[name] = os.getenv(name)

    missing = [name for name, value in required.items() if not value]
    if missing:
        pytest.skip(f"Variables manquantes dans .env : {missing}")

    base = required["STAGING_BASE_URL"].rstrip("/")
    host = urlparse(base).hostname
    assert host in HOST_ALLOWLIST, f"Host hors allowlist : {host!r} — refus d'exécuter"
    required["STAGING_BASE_URL"] = base
    return required


@pytest.fixture(scope="module")
def env() -> dict:
    return get_env()


@pytest.fixture(scope="module")
def client(env) -> httpx.Client:
    """Client BO authentifié par JWT sso. Le token n'est jamais journalisé."""
    with httpx.Client(base_url=env["STAGING_BASE_URL"], timeout=60) as anon:
        response = anon.post(
            "/p/sso/public/1/sign-in",
            json={"username": env["BOV2_STAGING_LOGIN"], "password": env["BOV2_STAGING_PASSWORD"]},
        )
        assert response.status_code in (200, 201), (
            f"sign-in a échoué : HTTP {response.status_code} — {response.text[:200]}"
        )
        token = response.json().get("token")
        assert token, f"sign-in n'a pas renvoyé de `token` : {sorted(response.json())}"

    with httpx.Client(
        base_url=env["STAGING_BASE_URL"],
        timeout=60,
        headers={"authorization": f"Bearer {token}", "accept": "application/json"},
    ) as authed:
        yield authed


@pytest.fixture(scope="module")
def throwaway(env, client) -> str:
    """Un compte créé pour ce run, et soft-deleted à la fin.

    C'est ce qui rend le fichier rejouable sans accumuler de données et sans
    jamais toucher à un compte de fixture partagé.
    """
    partner = {"apiuser_email": env["APIUSER_EMAIL"], "apiuser_token": env["APIUSER_TOKEN"]}
    alias = env["INSTALLATION_ID"]
    run_id = f"nr2216-{uuid.uuid4().hex[:12]}"

    with httpx.Client(base_url=env["STAGING_BASE_URL"], timeout=60) as partner_client:
        created = partner_client.post(
            f"/api/customers/v1/{alias}/create_customer",
            params=partner,
            json={
                "firstName": "NR",
                "lastName": f"Probe [{run_id}]",
                # jamais vide : une company vide est rejetée `StringEmpty`
                "company": "NR Fixture",
                "street": "1 rue de la Non-Regression",
                "zipCode": "75001",
                "city": "Paris",
                "country": "FR",
                "code": run_id.upper().replace("-", ""),
                "email": f"{run_id}@example.invalid",
                "phone": "+33600000001",
                "externalId": run_id,
            },
        )
        # 201, pas 200 — cf. « pièges de tooling » en tête de fichier
        assert created.status_code in (200, 201), (
            f"create_customer a répondu {created.status_code} : {created.text[:200]}"
        )
        body = created.json()
        assert body.get("succeeded"), f"create_customer : {body}"
        customer_id = body["customerId"]

        # la création est asynchrone côté réplica : on attend sa visibilité
        deadline = time.time() + 60
        while time.time() < deadline:
            if client.get(f"/p/customers/api/1/site/{SITE}/customers/{customer_id}").status_code == 200:
                break
            time.sleep(2)
        else:
            pytest.fail(f"Le compte {customer_id} n'est pas visible sur le site {SITE} après 60 s")

        try:
            yield customer_id
        finally:
            partner_client.request(
                "DELETE",
                f"/api/customers/v1/{alias}/delete_customer",
                params={**partner, "id": customer_id},
            )


def detail(client: httpx.Client, customer: str, site: int = SITE) -> httpx.Response:
    return client.get(f"/p/customers/api/1/site/{site}/customers/{customer}")


def patch(client: httpx.Client, customer: str, body: dict, site: int = SITE) -> httpx.Response:
    return client.patch(f"/p/customers/api/1/site/{site}/customers/{customer}", json=body)


def payload(response: httpx.Response) -> dict:
    """Corps JSON d'une réponse 200, avec le garde-fou de la SPA HTML servie en 200."""
    assert response.status_code == 200, f"HTTP {response.status_code} : {response.text[:200]}"
    content_type = response.headers.get("content-type", "")
    assert "application/json" in content_type, (
        f"content-type inattendu {content_type!r} — la requête est-elle retombée sur la SPA ?"
    )
    return response.json()


def test_01_single_field_update_leaves_the_others_untouched(client, throwaway):
    """AC1 : un update d'un seul champ modifie ce champ, et lui seul."""
    before = payload(detail(client, throwaway))
    new_value = f"NR-{uuid.uuid4().hex[:8]}"

    updated = payload(patch(client, throwaway, {"firstName": new_value}))
    after = payload(detail(client, throwaway))

    assert after["firstName"] == new_value, (
        f"`firstName` vaut {after['firstName']!r} au lieu de {new_value!r} — update non appliqué"
    )
    changed = [k for k in before if before[k] != after[k]]
    assert changed == ["firstName"], (
        f"Un update de `firstName` a aussi modifié {sorted(set(changed) - {'firstName'})}"
    )
    assert updated["firstName"] == new_value


def test_03_derived_values_and_metadata_are_rejected(client, throwaway):
    """AC3 : soldes, points et métadonnées en lecture seule sont refusés.

    Chaque champ est écrit à SA VALEUR COURANTE : si l'API régressait jusqu'à
    l'accepter, ce test échouerait sans avoir modifié quoi que ce soit.
    """
    before = payload(detail(client, throwaway))

    for field in FORBIDDEN_FIELDS:
        response = patch(client, throwaway, {field: before[field]})
        assert response.status_code == 400, (
            f"`{field}` est accepté en écriture (HTTP {response.status_code}) — "
            "un champ dérivé ou en lecture seule est devenu modifiable"
        )
        assert response.json()["data"] == {field: "AdditionalProperties"}, response.json()

    # un champ inconnu est rejeté de la même façon
    unknown = patch(client, throwaway, {"totallyBogusField": "x"})
    assert unknown.status_code == 400, (
        f"Un champ inconnu passe en {unknown.status_code} — le schéma a-t-il perdu "
        "son `additionalProperties: false` ?"
    )
    assert unknown.json()["data"] == {"totallyBogusField": "AdditionalProperties"}

    # contre-épreuve : rien n'a bougé
    assert payload(detail(client, throwaway)) == before, (
        "Un des rejets ci-dessus a tout de même modifié le compte"
    )


def test_04_update_on_a_customer_of_another_site_is_rejected(client, throwaway):
    """AC4 : le PATCH est cloisonné par site.

    La valeur envoyée est la valeur courante : même si le cloisonnement sautait,
    la requête ne changerait rien.
    """
    before = payload(detail(client, throwaway))

    response = patch(
        client, throwaway, {"firstName": before["firstName"]}, site=CONTROL_SITE
    )
    assert response.status_code == 400, (
        f"Un compte du site {SITE} est modifiable via le site {CONTROL_SITE} "
        f"(HTTP {response.status_code}) — cloisonnement rompu"
    )

    # et un client inexistant est refusé aussi
    ghost = patch(client, str(uuid.UUID(int=0)), {"firstName": "x"})
    assert ghost.status_code == 400, f"Client inexistant : attendu 400, reçu {ghost.status_code}"


def test_05_response_reflects_the_state_after_the_update(client, throwaway):
    """AC5 : la réponse du PATCH est le compte tel qu'il est après l'update."""
    new_value = f"NR-{uuid.uuid4().hex[:8]}"

    updated = payload(patch(client, throwaway, {"city": new_value}))
    after = payload(detail(client, throwaway))

    assert updated == after, (
        "La réponse du PATCH diffère de la relecture du compte : "
        f"{[k for k in after if updated.get(k) != after[k]]}"
    )
    assert updated["city"] == new_value
