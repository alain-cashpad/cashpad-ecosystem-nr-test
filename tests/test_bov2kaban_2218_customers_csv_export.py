from __future__ import annotations

"""
Test de non-régression généré par /cp-test — ticket BOV2KABAN-2218
[BACK] Generate CSV export of the customer accounts list

Fige le comportement OBSERVÉ et VALIDÉ le 2026-09-10 sur le staging
(host allowlisté : staging.cashpad.app), export CSV de la liste clients :

    GET {STAGING_BASE_URL}/p/customers/api/1/site/{SITE}/customers/export
        ?search=&type=&debtorsOnly=&deleted=&sort[column]=&sort[type]=

Mêmes pièges de routage que `test_bov2kaban_2212_customers_list.py` : préfixe
`/p/` obligatoire (sinon 200 + HTML de la SPA) et **JWT sso** via
`POST /p/sso/public/1/sign-in`, pas `BOV2_STAGING_TOKEN`.

Lecture seule : uniquement des GET, plus le POST de `sign-in`. Aucun client créé.

## Ce que ce fichier fige — et ce qu'il ne fige surtout pas

Le cœur du ticket est le **périmètre exporté**. Il n'est pas figé par un nombre
de lignes en dur (le jeu de données bouge en continu) mais par une **égalité avec
la liste** : sous chaque filtre, l'export doit rendre exactement autant de lignes
que `total` côté liste. C'est ce qui attrape un export qui ignorerait un filtre,
qui plafonnerait à une page, ou qui exporterait les comptes supprimés.

⚠️ **La colonne `Balance` n'est PAS assertée sur sa valeur.** Au 2026-09-10 elle
sort en **millièmes bruts** (`1102890`) là où l'export BOV1 rend des euros
(`1102.89`) — écart mesuré sur les 46 comptes non nuls communs aux deux fichiers,
46/46 au facteur 1000 exact. C'est un défaut ouvert, signalé sur le ticket : le
figer en NR reviendrait à verrouiller le bug et à faire échouer le test le jour
de sa correction. On fige donc la PRÉSENCE de la colonne, pas son unité.

Même raison pour les deux autres écarts de parité BOV1 signalés et non figés :
colonne `Anniversaire` absente (12 colonnes contre 13), et absence de la ligne
`Total` finale.

## Écarts connus, non figés ici

* un site non autorisé renvoie une **page HTML 403 nginx**, pas le payload
  d'erreur standard (`test_04` fige le refus, pas sa forme) ;
* **aucun champ n'est jamais entouré de guillemets** : au 2026-09-10 aucun compte
  du site ne contient de virgule, de guillemet ou de saut de ligne dans un champ
  exporté, donc le fichier est bien formé — mais l'échappement n'est jamais
  exercé. `test_05` vérifie la cohérence structurelle sur la donnée du moment et
  **skippe** si un champ à risque apparaît : ce jour-là, il faudra trancher le
  comportement attendu avant d'asserter quoi que ce soit.
* les autres exports BO V2 (`digested-data`) sont des **POST** rendant une
  enveloppe JSON `{content, fileName, contentType}` ; celui-ci est un GET rendant
  le CSV brut. Divergence de protocole, hors périmètre des AC.

Lancer :
    uv run --with pytest --with httpx --with python-dotenv \
      pytest tests/test_bov2kaban_2218_customers_csv_export.py -v
"""

import csv
import io
import os
from urllib.parse import urlparse

import httpx
import pytest
from dotenv import load_dotenv

load_dotenv()


# ── Garde-fou anti-prod : la vérification ne cible que le staging ──
HOST_ALLOWLIST = {"staging.cashpad.app"}

SITE = 4652
CONTROL_SITE = 4757

# Identifiants de site que la gateway n'autorise pas — ils ne correspondent à
# aucun site accessible et sortent en 403. À ne pas confondre avec un site réel
# mais vide (4653), qui répond 200 avec un fichier réduit à son en-tête.
UNAUTHORISED_SITES = (999999, "abc")

MAX_LIMIT = 50

# Colonnes servies au 2026-09-10. On fige leur PRÉSENCE et leur ordre : c'est le
# contrat de lecture des consommateurs du fichier. Les valeurs, elles, ne sont
# pas figées (cf. la réserve sur `Balance` en tête de fichier).
EXPECTED_COLUMNS = [
    "Nom",
    "Prénom",
    "Email",
    "Code",
    "Tel.",
    "Adresse",
    "Code postal",
    "Société",
    "Ville",
    "Pays",
    "Informations d'accès",
    "Balance",
]

# Filtres de la liste que l'export doit honorer à l'identique.
PERIMETER_CASES = {
    "sans filtre": {},
    "search": {"search": "Bernard"},
    "debtorsOnly": {"debtorsOnly": True},
    "deleted": {"deleted": True},
    "type entreprise": {"type": 1},
    "trié": {"sort": {"column": "lastName", "type": "desc"}},
}

# Champs texte présents dans le CSV, à surveiller pour l'échappement.
RISKY_CHARS = (",", '"', "\n", "\r")
EXPORTED_TEXT_FIELDS = ("lastName", "firstName", "email", "code", "phone", "city", "company")


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
        timeout=90,
        headers={"authorization": f"Bearer {token}", "accept": "*/*"},
    ) as authed:
        yield authed


def flatten(params: dict) -> dict:
    """`{'sort': {'column': …}}` → `{'sort[column]': …}`, comme le fait le dashboard."""
    query = {}
    for key, value in params.items():
        if key == "sort" and isinstance(value, dict):
            for sub, sub_value in value.items():
                query[f"sort[{sub}]"] = sub_value
        else:
            query[key] = value
    return query


def export(client: httpx.Client, site: int | str = SITE, **params) -> httpx.Response:
    return client.get(
        f"/p/customers/api/1/site/{site}/customers/export", params=flatten(params)
    )


def list_total(client: httpx.Client, site: int = SITE, **params) -> int:
    response = client.get(
        f"/p/customers/api/1/site/{site}/customers", params={"limit": 1, **flatten(params)}
    )
    assert response.status_code == 200, f"Liste : HTTP {response.status_code}"
    return response.json()["total"]


def text_of(response: httpx.Response) -> str:
    """Corps décodé en `utf-8-sig` — le fichier commence par un BOM UTF-8.

    Piège : `fetch().text()` côté navigateur retire le BOM silencieusement, alors
    que `response.text` de httpx le conserve. Une sonde écrite depuis la console
    du navigateur conclut donc à tort qu'il n'y a pas de BOM, et la première
    colonne se lit `\\ufeffNom`. On décode explicitement.
    """
    return response.content.decode("utf-8-sig")


def rows_of(response: httpx.Response) -> list[list[str]]:
    """Lignes de données du CSV (en-tête exclu), avec le garde-fou de la SPA en 200."""
    assert response.status_code == 200, f"HTTP {response.status_code} : {response.text[:200]}"
    content_type = response.headers.get("content-type", "")
    assert "text/csv" in content_type, (
        f"content-type inattendu {content_type!r} — la requête est-elle retombée sur la SPA ?"
    )
    parsed = list(csv.reader(io.StringIO(text_of(response))))
    return [r for r in parsed[1:] if any(cell.strip() for cell in r)]


def header_of(response: httpx.Response) -> list[str]:
    return next(csv.reader(io.StringIO(text_of(response))))


def test_01_export_returns_a_csv_file_for_the_requested_site(client):
    """AC1 : l'endpoint rend un fichier CSV téléchargeable pour le site demandé."""
    response = export(client)

    assert response.status_code == 200
    assert "text/csv" in response.headers.get("content-type", "")
    disposition = response.headers.get("content-disposition", "")
    assert "attachment" in disposition, f"Pas un téléchargement : {disposition!r}"
    assert str(SITE) in disposition, (
        f"Le nom de fichier ne porte pas le site demandé : {disposition!r}"
    )

    # BOM UTF-8 : c'est lui qui fait qu'Excel ouvre le fichier avec les bons
    # accents. Le perdre casserait « Prénom », « Société », « accès » chez tous
    # les utilisateurs Windows, sans qu'aucun autre test ne le voie.
    assert response.content.startswith(b"\xef\xbb\xbf"), (
        "Le CSV ne commence plus par un BOM UTF-8 — Excel affichera des accents cassés"
    )

    assert header_of(response) == EXPECTED_COLUMNS, (
        "Les colonnes de l'export ont changé — contrat de lecture rompu pour les "
        "consommateurs du fichier"
    )


def test_02_export_is_synchronous_and_needs_no_polling(client):
    """AC2 : le fichier est produit de façon synchrone, sans polling.

    Preuve : la réponse EST le fichier. Un export asynchrone rendrait un 202 ou un
    identifiant de job en JSON, qu'il faudrait ensuite interroger.
    """
    response = export(client)

    assert response.status_code == 200, f"Statut {response.status_code} — file d'attente ?"
    assert "json" not in response.headers.get("content-type", ""), (
        "La réponse est du JSON : un identifiant de job a-t-il remplacé le fichier ?"
    )
    assert header_of(response) == EXPECTED_COLUMNS
    assert rows_of(response), "Le fichier ne contient aucune ligne de données"


def test_03_export_is_scoped_to_the_requested_site(client):
    """AC1 (cloisonnement) : le fichier d'un site ne contient que ses propres comptes.

    Prouvé par disjonction avec un site témoin plutôt que par des comptes figés :
    les deux jeux évoluent indépendamment.
    """
    ours = rows_of(export(client))
    theirs = rows_of(export(client, site=CONTROL_SITE))
    if not theirs:
        pytest.skip(f"Le site témoin {CONTROL_SITE} n'a aucun compte — cas non discriminant")

    def names(rows):
        return {r[0] for r in rows if r and r[0].strip()}

    shared = names(ours) & names(theirs)
    assert not shared, (
        f"{len(shared)} compte(s) apparaissent dans les exports des deux sites : {sorted(shared)[:3]}"
    )

    # chaque fichier est bien calé sur la volumétrie de SON site
    assert len(ours) == list_total(client)
    assert len(theirs) == list_total(client, site=CONTROL_SITE)


def test_04_export_is_refused_for_a_site_the_user_cannot_access(client):
    """AC3 : l'export est refusé sur un site auquel l'utilisateur n'a pas accès.

    On fige le REFUS, pas sa forme : aujourd'hui la gateway rend une page HTML 403
    et non le payload d'erreur standard (écart connu, cf. en-tête).
    """
    for site in UNAUTHORISED_SITES:
        response = export(client, site=site)
        assert response.status_code == 403, (
            f"Site {site!r} : attendu 403, reçu {response.status_code} — "
            "un site non autorisé est-il devenu exportable ?"
        )

    # contre-épreuve : un site autorisé mais vide répond 200 avec le seul en-tête
    empty = export(client, site=CONTROL_SITE, search="zzz-aucun-client-zzz")
    assert empty.status_code == 200
    assert header_of(empty) == EXPECTED_COLUMNS
    assert rows_of(empty) == []


def test_05_exported_perimeter_matches_the_list_under_every_filter(client):
    """AC4 : le périmètre exporté est celui de la liste, filtres compris.

    Le step le plus utile du fichier. Aucune volumétrie n'est figée en dur : on
    compare l'export au `total` de la liste sous chaque filtre. Cela attrape un
    export qui ignorerait un paramètre, qui s'arrêterait à une page, ou qui
    inclurait les comptes supprimés.
    """
    mismatches = {}
    for label, params in PERIMETER_CASES.items():
        expected = list_total(client, **params)
        actual = len(rows_of(export(client, **params)))
        if actual != expected:
            mismatches[label] = f"liste {expected} vs export {actual}"

    assert not mismatches, f"Périmètre divergent entre liste et export : {mismatches}"

    # un filtre discriminant doit réduire le fichier, sinon la comparaison
    # ci-dessus serait satisfaite par un export qui ignore tout
    everything = list_total(client)
    filtered = list_total(client, debtorsOnly=True)
    if filtered >= everything:
        pytest.skip("`debtorsOnly` ne réduit pas le jeu — cas non discriminant")


def test_06_invalid_parameters_are_rejected_like_on_the_list(client):
    """L'export partage la validation de la liste : une valeur invalide sort en 400."""
    for params in ({"debtorsOnly": "maybe"}, {"sort": {"column": "last_name", "type": "asc"}}):
        response = export(client, **params)
        assert response.status_code == 400, (
            f"{params} : attendu 400, reçu {response.status_code} — "
            "l'export a-t-il perdu la validation de la liste ?"
        )


def test_07_every_row_has_the_same_field_count_as_the_header(client):
    """Cohérence structurelle du CSV sur la donnée du moment.

    ⚠️ L'export n'entoure JAMAIS un champ de guillemets. Tant qu'aucun champ ne
    contient de virgule, de guillemet ou de saut de ligne, le fichier reste bien
    formé — c'est ce qu'on vérifie ici. Dès qu'un tel champ apparaît, ce step
    skippe plutôt que d'échouer : il faudra d'abord trancher le comportement
    attendu (échapper, ou refuser la valeur), ce que ce fichier ne présume pas.
    """
    response = export(client)
    width = len(header_of(response))

    risky = []
    skip, limit = 0, MAX_LIMIT
    while True:
        page = client.get(
            f"/p/customers/api/1/site/{SITE}/customers", params={"limit": limit, "skip": skip}
        )
        assert page.status_code == 200
        body = page.json()
        for row in body["data"]:
            for field in EXPORTED_TEXT_FIELDS:
                value = row.get(field)
                if isinstance(value, str) and any(c in value for c in RISKY_CHARS):
                    risky.append((row["id"], field))
        if not body["data"] or skip + limit >= body["total"]:
            break
        skip += limit

    if risky:
        pytest.skip(
            f"{len(risky)} champ(s) contiennent un séparateur ou un guillemet "
            f"(ex. {risky[:2]}) : l'échappement CSV doit être spécifié avant d'asserter."
        )

    bad = [r for r in rows_of(response) if len(r) != width]
    assert not bad, (
        f"{len(bad)} ligne(s) n'ont pas {width} champs alors qu'aucune valeur ne "
        "contient de séparateur — le CSV est mal formé"
    )
