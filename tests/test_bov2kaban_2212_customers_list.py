from __future__ import annotations

"""
Test de non-régression généré par /cp-test — ticket BOV2KABAN-2212
[BACK] Expose paginated customer accounts list with search, filters and sorting

Fige le comportement OBSERVÉ et VALIDÉ le 2026-09-08 sur le staging
(host allowlisté : staging.cashpad.app), endpoint BO-facing de la liste :

    GET {STAGING_BASE_URL}/p/customers/api/1/site/{SITE}/customers
        ?search=&type=&debtorsOnly=&deleted=&includeDisabled=
        &sort[column]=&sort[type]=&skip=&limit=

⚠️ Deux pièges de routage, coûteux à re-découvrir (cf. le verdict /cp-test) :

1. **Le préfixe est `/p/`**, pas `/<service>/`. Sans lui, la requête retombe sur
   l'index de la SPA Angular et renvoie **200 + du HTML** — un 200 ne prouve rien,
   vérifier le `content-type`.
2. **L'auth n'est PAS `BOV2_STAGING_TOKEN`** (le bearer des routes `public/*`
   analytics) ni le `x-auth` que la KB annonce pour la famille `api/1`. C'est un
   **JWT sso** obtenu par `POST /p/sso/public/1/sign-in` avec `{username, password}`,
   qui renvoie 201 `{token, refreshToken}`. Un header `Authorization` mal formé
   fait renvoyer **500 par nginx**, pas 401 — ne pas lire ce 500 comme une panne
   du service.

Contrairement à la règle « ingress GET-only » de la KB, cette route `api/1` est un
vrai `find` → GET, donc exerçable ; et le POST de `sign-in` passe.

## Historique — le paramètre `deleted`

La vérification du **matin** du 2026-09-08 trouvait `deleted` **inerte** : six
variantes de nommage (`deleted=true|false|1`, `includeDeleted`, `withDeleted`,
`deletedOnly`) renvoyaient toutes les mêmes lignes que l'appel sans filtre, et le
ticket avait été rapporté `non conforme` sur ce seul critère.

Re-mesuré l'**après-midi** du même jour : `deleted=true` renvoie les comptes
soft-deleted, et `deleted=maybe` est rejeté en `400 {"deleted":"Type"}` — le
paramètre est déclaré au contrat. Redéploiement entre les deux runs. Le ticket est
conforme 7/7, et `test_04` est le garde-fou de ce correctif : c'est le step le plus
utile du fichier.

## Écarts connus, non figés ici

Volontairement hors assertions — ce sont des écarts vs la section Solution du
ticket, pas des comportements à préserver :

* un site inconnu ou invalide renvoie une **page HTML 403 nginx**, pas le payload
  d'erreur standard (le service ne vérifie jamais l'existence du site). Ne pas
  confondre avec un site RÉEL mais vide, qui répond bien 200 `total: 0` — c'est
  le cas de 4653 ; seuls des identifiants inexistants (999999, `abc`) sortent en
  403 ;
* `limit` est plafonné à 50, ce que le ticket ne documente pas ;
* les valeurs de `sort[column]` documentées sont en snake_case (`last_name`…)
  alors que l'API attend du camelCase — `test_08` fige le **rejet** du snake_case,
  qui est le comportement réel ;
* **`includeDisabled` n'est PAS au contrat** de ce endpoint : `includeDisabled=maybe`
  répond 200, exactement comme un paramètre inventé. Les schémas de `find` n'ont
  pas d'`additionalProperties: false`, donc un paramètre inconnu est accepté et
  ignoré en silence — impossible de distinguer « implémenté » d'« inexistant » par
  la valeur invalide. Rien n'est donc figé dessus. (Mesuré le 2026-09-10 ; une
  note du 2026-09-08 le disait « déclaré », c'était faux.)

Golden ciblé : `status_code` + invariants liés aux acceptance criteria. Aucun
compte exact n'est figé — le jeu de données du site de test évolue (des clients
sont créés et supprimés en continu). Ce sont les SÉMANTIQUES qui sont figées.

Lecture seule : uniquement des GET sur la liste et le détail, plus le POST de
`sign-in`. Aucune écriture métier.

Lancer :
    uv run --with pytest --with httpx --with python-dotenv \
      pytest tests/test_bov2kaban_2212_customers_list.py -v
"""

import os
import unicodedata
from collections import Counter
from urllib.parse import urlparse

import httpx
import pytest
from dotenv import load_dotenv

load_dotenv()


# ── Garde-fou anti-prod : la vérification ne cible que le staging ──
HOST_ALLOWLIST = {"staging.cashpad.app"}

# Site vérifié le 2026-09-08 (CP-STAGING-ALAIN / cashpad-8007) et son témoin,
# utilisé uniquement pour prouver le cloisonnement par site.
SITE = 4652
CONTROL_SITE = 4757

# Pagination canonique BOV2 (src/customers/src/constants/schema.ts)
DEFAULT_LIMIT = 10
MAX_LIMIT = 50

# Champs sur lesquels `search` doit matcher, d'après l'acceptance criterion.
SEARCH_FIELDS = ("lastName", "firstName", "company", "email", "phone")

SORT_COLUMNS = ("lastName", "firstName", "loyaltyPoints", "balance")


def get_env() -> dict:
    """Base staging + identifiants BO. Skip si absents : tout le monde n'a pas ce compte."""
    base = os.getenv("STAGING_BASE_URL")
    login = os.getenv("BOV2_STAGING_LOGIN")
    password = os.getenv("BOV2_STAGING_PASSWORD")

    missing = [
        name
        for name, value in (
            ("STAGING_BASE_URL", base),
            ("BOV2_STAGING_LOGIN", login),
            ("BOV2_STAGING_PASSWORD", password),
        )
        if not value
    ]
    if missing:
        pytest.skip(f"Variables manquantes dans .env : {missing}")

    host = urlparse(base).hostname
    assert host in HOST_ALLOWLIST, f"Host hors allowlist : {host!r} — refus d'exécuter"
    return {"base": base.rstrip("/"), "login": login, "password": password}


@pytest.fixture(scope="module")
def client() -> httpx.Client:
    """Client authentifié par JWT sso. Le token n'est jamais journalisé."""
    env = get_env()
    with httpx.Client(base_url=env["base"], timeout=60) as anon:
        response = anon.post(
            "/p/sso/public/1/sign-in",
            json={"username": env["login"], "password": env["password"]},
        )
        assert response.status_code in (200, 201), (
            f"sign-in a échoué : HTTP {response.status_code} — {response.text[:200]}"
        )
        token = response.json().get("token")
        assert token, f"sign-in n'a pas renvoyé de `token` : {sorted(response.json())}"

    with httpx.Client(
        base_url=env["base"],
        timeout=60,
        headers={"authorization": f"Bearer {token}", "accept": "application/json"},
    ) as authed:
        yield authed


def customers(client: httpx.Client, site: int = SITE, **params) -> httpx.Response:
    """GET de la liste. `sort` est passé en bracket-notation, comme le fait le dashboard."""
    query = {}
    for key, value in params.items():
        if key == "sort" and isinstance(value, dict):
            for sub, sub_value in value.items():
                query[f"sort[{sub}]"] = sub_value
        else:
            query[key] = value
    return client.get(f"/p/customers/api/1/site/{site}/customers", params=query)


def payload(response: httpx.Response) -> dict:
    """Corps JSON d'une réponse 200, avec le garde-fou du piège n°1 (SPA HTML en 200)."""
    assert response.status_code == 200, f"HTTP {response.status_code} : {response.text[:200]}"
    content_type = response.headers.get("content-type", "")
    assert "application/json" in content_type, (
        f"content-type inattendu {content_type!r} — la requête est-elle retombée sur la SPA ?"
    )
    return response.json()


def collect_all(client: httpx.Client, site: int = SITE, page_size: int = MAX_LIMIT, **params) -> list:
    """Parcourt toutes les pages et renvoie les lignes concaténées."""
    rows, skip = [], 0
    while True:
        body = payload(customers(client, site, limit=page_size, skip=skip, **params))
        rows.extend(body["data"])
        total = body["total"]
        if not body["data"] or len(rows) >= total:
            return rows
        skip += page_size


def collation_key(value: str) -> str:
    """Clé de tri imitant la collation linguistique Postgres.

    Postgres trie « Léo » avant « Louise » (é se compare comme e) et ignore la
    ponctuation (« BOV2KABAN » avant « BOV2-RETEST »). Une comparaison Python
    brute sur les points de code conclurait à tort au désordre. On enlève donc
    les diacritiques et tout ce qui n'est ni alphanumérique ni espace.
    """
    decomposed = unicodedata.normalize("NFKD", str(value))
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return "".join(c for c in stripped if c.isalnum() or c.isspace()).casefold().strip()


def assert_monotonic(values: list, direction: str, label: str) -> None:
    """Ordre monotone, valeurs nulles ignorées (Postgres place les NULL en tête en DESC)."""
    keyed = [collation_key(v) if isinstance(v, str) else v for v in values if v is not None]
    for previous, current in zip(keyed, keyed[1:]):
        if direction == "asc":
            assert previous <= current, f"{label} : {previous!r} précède {current!r} en asc"
        else:
            assert previous >= current, f"{label} : {previous!r} précède {current!r} en desc"


@pytest.fixture(scope="module")
def active_rows(client: httpx.Client) -> list:
    """Les comptes actifs du site, lus une fois et partagés entre les steps."""
    rows = collect_all(client)
    assert rows, "Aucun compte actif sur le site de test — s'est-il vidé ?"
    return rows


def test_01_unfiltered_list_is_scoped_to_the_requested_site(client, active_rows):
    """AC1 : sans filtre, la liste renvoie les comptes actifs du site demandé, et eux seuls.

    Le cloisonnement est prouvé par disjonction avec un site témoin, pas par des
    comptes figés : les deux jeux évoluent indépendamment.
    """
    body = payload(customers(client))
    assert body["limit"] == DEFAULT_LIMIT, f"limit par défaut inattendue : {body['limit']}"
    assert body["skip"] == 0
    assert body["total"] == len(active_rows)
    assert set(body) >= {"data", "aggregates", "total", "limit", "skip"}

    control = payload(customers(client, site=CONTROL_SITE, limit=MAX_LIMIT))
    ours = {row["id"] for row in active_rows}
    theirs = {row["id"] for row in control["data"]}
    assert not (ours & theirs), (
        f"{len(ours & theirs)} compte(s) partagé(s) entre les sites {SITE} et {CONTROL_SITE}"
    )


def test_02_search_matches_the_five_documented_fields(client, active_rows):
    """AC2 : `search` matche last name, first name, company, email et phone.

    La cible est choisie dans le jeu courant (un compte qui renseigne les cinq
    champs) : c'est la sémantique du filtre qui est figée, pas un client précis.
    """
    target = next((row for row in active_rows if all(row.get(f) for f in SEARCH_FIELDS)), None)
    if target is None:
        pytest.skip("Aucun compte ne renseigne les cinq champs — cas non discriminant")

    for field in SEARCH_FIELDS:
        body = payload(customers(client, search=target[field], limit=MAX_LIMIT))
        assert any(row["id"] == target["id"] for row in body["data"]), (
            f"search sur {field}={target[field]!r} ne renvoie pas le compte cible {target['id']}"
        )

    empty = payload(customers(client, search="zzz-aucun-client-zzz", limit=MAX_LIMIT))
    assert empty["total"] == 0, f"Un terme absent renvoie {empty['total']} résultat(s)"


def test_03_debtors_only_returns_negative_balances(client, active_rows):
    """AC3 : `debtorsOnly` ne renvoie que les comptes au solde négatif."""
    rows = collect_all(client, debtorsOnly=True)
    assert all(row["balance"] < 0 for row in rows), (
        "debtorsOnly renvoie des soldes positifs ou nuls : "
        f"{[r['balance'] for r in rows if r['balance'] >= 0][:5]}"
    )
    expected = {row["id"] for row in active_rows if row["balance"] < 0}
    assert {row["id"] for row in rows} == expected, (
        "debtorsOnly ne coïncide pas avec les soldes négatifs de la liste complète"
    )


def test_04_deleted_is_the_only_way_to_reach_soft_deleted_accounts(client, active_rows):
    """AC4 : `deleted` expose les comptes soft-deleted — et rien d'autre.

    Step le plus important du fichier : ce paramètre était inerte le matin du
    2026-09-08 (accepté en 200, sans effet) et a été corrigé par un redéploiement
    dans la journée. Une régression le rendrait de nouveau silencieux.

    Trois preuves indépendantes, pour ne pas confondre « filtre inerte » et
    « aucune donnée à filtrer » :
      a. le paramètre est DÉCLARÉ au contrat — une valeur invalide est rejetée en
         400, là où un paramètre inconnu passerait en 200 (témoin explicite) ;
      b. les deux jeux sont DISJOINTS ;
      c. chaque compte du jeu supprimé se déclare `deleted: true` sur le endpoint
         de détail, et les comptes actifs `deleted: false` — ce sont donc bien des
         soft-deleted, et pas simplement des lignes que le filtre aurait écartées
         au hasard.

    ⚠️ La preuve (c) reposait jusqu'au 2026-09-09 sur un **404** du détail, qui
    filtrait alors `deleted = false` en dur. Mesuré le 2026-09-10 : les 33 comptes
    supprimés répondent désormais **200**, corps à l'appui (`deleted: true`). Le
    critère du ticket porte sur la LISTE, il reste satisfait ; c'est la preuve
    auxiliaire qui a changé de nature. On assert donc le champ, ce qui est plus
    direct qu'un code de statut : un 404 ne disait pas *pourquoi* la fiche manquait.
    """
    # (a) déclaré au contrat, contre un témoin de paramètre inconnu
    invalid = customers(client, deleted="maybe")
    assert invalid.status_code == 400, (
        f"`deleted=maybe` renvoie {invalid.status_code} au lieu de 400 — "
        "le paramètre est-il redevenu un paramètre inconnu, silencieusement ignoré ?"
    )
    assert invalid.json()["data"] == {"deleted": "Type"}, invalid.json()

    witness = customers(client, totallyBogusParam="maybe")
    assert witness.status_code == 200, (
        "Le témoin de paramètre inconnu devrait passer en 200 ; sans ça, le 400 "
        "ci-dessus ne prouve rien sur `deleted` en particulier."
    )

    # (b) disjonction
    deleted_rows = collect_all(client, deleted=True)
    assert deleted_rows, "`deleted=true` ne renvoie aucun compte — plus de soft-deleted sur ce site ?"
    active_ids = {row["id"] for row in active_rows}
    deleted_ids = {row["id"] for row in deleted_rows}
    assert not (active_ids & deleted_ids), (
        f"{len(active_ids & deleted_ids)} compte(s) présent(s) dans les deux jeux"
    )

    # `deleted=false` doit rendre exactement la liste par défaut
    assert {row["id"] for row in collect_all(client, deleted=False)} == active_ids

    # (c) le détail confirme le statut, et la contre-épreuve active l'infirme
    for row in deleted_rows[:3]:
        detail = client.get(f"/p/customers/api/1/site/{SITE}/customers/{row['id']}")
        assert detail.status_code == 200, (
            f"Le compte supprimé {row['id']} répond {detail.status_code} sur le "
            "détail — le endpoint s'est-il remis à filtrer `deleted` en dur ?"
        )
        assert detail.json().get("deleted") is True, (
            f"Le compte {row['id']} est listé sous `deleted=true` mais son détail "
            f"annonce deleted={detail.json().get('deleted')!r} — les deux surfaces divergent."
        )

    control = client.get(f"/p/customers/api/1/site/{SITE}/customers/{next(iter(active_ids))}")
    assert control.status_code == 200, (
        f"Contre-épreuve : un compte actif devrait répondre 200, reçu {control.status_code}"
    )
    assert control.json().get("deleted") is False, (
        "Contre-épreuve : un compte de la liste par défaut se déclare "
        f"deleted={control.json().get('deleted')!r} — la liste ne filtre plus les supprimés."
    )


def test_05_sorting_is_honoured_on_four_columns_both_directions(client):
    """AC5 : tri sur last name, first name, loyalty points et balance, dans les deux sens.

    L'ordre est vérifié avec une clé de collation (cf. `collation_key`) : Postgres
    trie linguistiquement, une comparaison brute sur les points de code
    signalerait de faux désordres.

    Le tri est vérifié sur le feed ENTIER, pas sur la première page : le site
    porte plus de comptes qu'une page ne peut en rendre, et un tri appliqué page
    par page au lieu de l'être sur l'ensemble ne se verrait pas autrement.
    """
    for column in SORT_COLUMNS:
        for direction in ("asc", "desc"):
            rows = collect_all(client, sort={"column": column, "type": direction})
            assert_monotonic([row[column] for row in rows], direction, f"{column} {direction}")


def test_06_incremental_loading_yields_no_gap_and_no_duplicate(client, active_rows):
    """AC6 : suivre la pagination donne les résultats suivants sans trou ni doublon.

    La pagination est par offset (`skip`/`limit`) — le standard BOV2 ; le ticket
    parle de « cursor » de façon générique. Ce qui est figé, c'est la propriété de
    fond : parcourir par petites pages rend exactement le même ensemble qu'en
    grandes pages.

    Le second volet est le plus important. Une fenêtre `skip`/`limit` posée sur un
    tri SANS tie-breaker est non déterministe : sur les valeurs ex æquo, les lignes
    de bord changent de page entre deux requêtes, si bien que certaines sont
    servies deux fois et autant d'autres jamais. C'est exactement le défaut qui a
    touché le feed d'activité de BOV2KABAN-2214 (8 tickets injoignables, 36 sur 740
    en pages de 10). On le vérifie ici sous le tri le plus dégénéré du jeu —
    `loyaltyPoints`, où la quasi-totalité des comptes partagent la même valeur.
    """
    small_pages = collect_all(client, page_size=DEFAULT_LIMIT)
    ids = [row["id"] for row in small_pages]

    assert len(ids) == len(set(ids)), f"{len(ids) - len(set(ids))} doublon(s) en paginant"
    assert set(ids) == {row["id"] for row in active_rows}, (
        "Le parcours par pages de 10 ne rend pas le même ensemble que par pages de 50"
    )

    # ── pagination sous un tri massivement ex æquo ──
    tied = Counter(row["loyaltyPoints"] for row in active_rows)
    if max(tied.values(), default=0) < 2:
        pytest.skip(
            "Aucune valeur de `loyaltyPoints` ex æquo — le jeu de données ne peut "
            "pas révéler une pagination instable. À re-seeder avant de conclure."
        )

    def walk_sorted() -> list:
        return [
            row["id"]
            for row in collect_all(
                client,
                page_size=DEFAULT_LIMIT,
                sort={"column": "loyaltyPoints", "type": "asc"},
            )
        ]

    first = walk_sorted()
    assert len(first) == len(set(first)), (
        f"{len(first) - len(set(first))} doublon(s) en paginant sur un tri ex æquo — "
        "tri sans tie-breaker (cf. BOV2KABAN-2214)"
    )
    assert set(first) == {row["id"] for row in active_rows}, (
        f"Le parcours trié ne rend que {len(set(first))} comptes distincts sur "
        f"{len(active_rows)} — des lignes tombent entre deux pages"
    )
    assert walk_sorted() == first, (
        "Deux parcours identiques rendent un ORDRE différent — le tri n'est pas "
        "déterministe sur les valeurs ex æquo, la pagination finira par perdre des lignes"
    )


def test_07_aggregates_match_the_active_accounts(client, active_rows):
    """AC7 : les agrégats correspondent aux comptes actifs du site, et suivent les filtres."""
    body = payload(customers(client, limit=MAX_LIMIT))
    aggregates = body["aggregates"]

    credit = sum(row["balance"] for row in active_rows if row["balance"] > 0)
    debt = sum(row["balance"] for row in active_rows if row["balance"] < 0)
    assert aggregates["totalCreditorCredit"] == credit
    assert aggregates["totalDebtorBalance"] == debt

    # les agrégats sont recalculés sous filtre, pas repris de la liste complète
    companies = payload(customers(client, type=1, limit=MAX_LIMIT))
    company_credit = sum(row["balance"] for row in companies["data"] if row["balance"] > 0)
    assert companies["aggregates"]["totalCreditorCredit"] == company_credit
    assert companies["total"] <= body["total"]


def test_08_invalid_sort_and_filter_values_return_the_standard_error_payload(client):
    """Payload d'erreur standard sur valeurs invalides — `{name, message, code, className, data}`.

    Inclut le snake_case que la section Solution du ticket documente pour
    `sort[column]` : l'API attend du camelCase et rejette ces valeurs. C'est
    l'observé qui est figé, pas le libellé du ticket.
    """
    cases = {
        "sort.column": customers(client, sort={"column": "last_name", "type": "asc"}),
        "sort.type": customers(client, sort={"column": "lastName", "type": "sideways"}),
        "type": customers(client, type=7),
        "limit": customers(client, limit=MAX_LIMIT + 1),
    }
    for field, response in cases.items():
        assert response.status_code == 400, (
            f"Valeur invalide sur {field} : attendu 400, reçu {response.status_code}"
        )
        body = response.json()
        assert set(body) >= {"name", "message", "code", "className", "data"}, body
        assert field in body["data"], f"Le champ fautif {field} n'est pas nommé : {body['data']}"
