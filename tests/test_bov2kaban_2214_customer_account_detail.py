from __future__ import annotations

"""
Test de non-régression généré par /cp-test — ticket BOV2KABAN-2214
[BACK] Expose customer account detail with balances and unified activity

Fige le comportement OBSERVÉ et VALIDÉ le 2026-09-10 sur le staging
(host allowlisté : staging.cashpad.app), sur les deux endpoints BO-facing :

    GET {STAGING_BASE_URL}/p/customers/api/1/site/{SITE}/customers/{id}
    GET {STAGING_BASE_URL}/p/customers/api/1/site/{SITE}/customers/{id}/operations
        ?kind=&skip=&limit=

Routage et auth : mêmes pièges que `test_bov2kaban_2212_customers_list.py` —
préfixe `/p/` obligatoire (sinon 200 + HTML de la SPA Angular), et JWT sso via
`POST /p/sso/public/1/sign-in`, pas `BOV2_STAGING_TOKEN`.

## Historique — pourquoi ce fichier existe

La vérification du **2026-09-08** rapportait le ticket `non conforme` (2/6 AC) sur
deux échecs :

* le feed ne contenait **aucune entrée `ticket`** (180 opérations, 0 ticket) —
  `getListForCustomer` lisait `customer_operations` seul, le join manquait ;
* `kind` n'était **pas au contrat** — `kind=ticket`, `kind=maybe` et un témoin de
  paramètre inconnu renvoyaient tous les mêmes entrées en 200.

Re-mesuré le **2026-09-09** après redéploiement : les deux sont corrigés.
`test_03` et `test_04` sont les garde-fous de ces deux correctifs — une
régression rendrait de nouveau le feed amputé de ses tickets, ou `kind`
silencieux.

Le même jour, la comparaison **BOV1 preprod ↔ BOV2 staging** a révélé un
troisième défaut, qui faisait retomber le ticket à **5/6** :

* les deux plateformes s'accordent sur **750 tickets** pour ce client (`archive_content`,
  `sequential_id` identiques des deux côtés) ;
* 2 sont annulés (1473, 1509) et légitimement exclus — `total` = 748 est donc juste ;
* mais le feed ne rendait que **740 entrées distinctes** : il servait 748 lignes dont
  **8 doublons**, et **8 tickets non annulés n'étaient jamais servis** (342, 389,
  439-442, 537, 546).

Cause : le tri portait sur `date` seule, sans tie-breaker, alors que 80 groupes
d'horodatages sont ex æquo (477 lignes, jusqu'à 14 par groupe). La fenêtre
`skip`/`limit` était donc non déterministe : elle répétait des lignes de bord et
en perdait autant. Plus la page était petite, plus la perte était grande (36 sur
740 en pages de 10, la taille par défaut de l'écran).

**Re-mesuré le 2026-09-10 : corrigé, le ticket passe à 6/6.** Les parcours
complets en pages de 50 ET de 10 rendent désormais **757 entrées distinctes pour
`total` = 757**, sans doublon, et deux parcours indépendants sont identiques
ligne à ligne. Les 80 groupes ex æquo sont toujours dans le jeu de données, donc
le test reste discriminant : c'est bien un tri stable, pas une donnée favorable.
`test_03b` n'est plus un `xfail` — c'est le garde-fou de ce correctif, et il
revient au rouge si le tie-breaker disparaît.

## Parité BOV1 ↔ BOV2 vérifiée le 2026-09-09

Sur `preprod.cashpad.net` (hors allowlist `/cp-test`, cible fournie
explicitement par le dev) avec le même couple partenaire `obypay` :

* `get_customer` : **39/39 champs identiques**, zéro écart de valeur — dont
  `account` (1035390), `balance` (1102890) et `loyaltyPoints`. L'AC2 est donc
  cross-validée contre BOV1, pas seulement contre elle-même.
* ⚠️ l'**enveloppe diffère** : BOV2 sert l'objet sous `customers` (pluriel),
  BOV1 sous `customer` (singulier). Rupture pour un partenaire qui migre.
* `archive_content` : mêmes 750 receipts, mêmes `sequential_id`, aucun receipt
  présent d'un seul côté.
* écarts de payload hors périmètre de ce ticket, non figés ici : BOV2 annonce
  systématiquement plus d'`items` que BOV1 sur les vieux receipts (18 vs 6,
  15 vs 5, 9 vs 5 — 205 receipts concernés), `cancelled` est peuplé côté BOV2 et
  absent côté BOV1, `location.external_id` n'existe que côté BOV1.

## Écarts connus, NON figés ici

Volontairement hors assertions — ce sont des écarts vs la section Solution du
ticket, pas des comportements à préserver :

* **`amount` mélange deux unités dans le même champ** : les opérations `account`
  sont en millièmes d'euro (`43170` → 43,17 €) alors que les entrées `ticket`
  sont en euros décimaux (`12.4`). Piège direct pour le front. Le test compare
  donc les montants de tickets en euros, et ne touche pas aux montants `account`.
* **pas de `cursor`** : la pagination est l'offset Feathers `skip`/`limit`/`total`,
  et `cursor=abc` est rejeté en 400 `AdditionalProperties`. Le ticket documente un
  `cursor` et un « next cursor » qui n'existent pas.
* `limit` est plafonné à 50, ce que le ticket ne documente pas.
* nommage des entrées : `type` (et non `kind`), `description` (et non `label`),
  `userId` (et non `employee`, et `null` sur tout l'échantillon observé).

`test_04` fige en revanche le **rejet** de `kind=account_operation` : c'est la
valeur que la section Solution du ticket documente, l'API attend `account` et
`loyaltyPoints`. C'est l'observé qui est figé, pas le libellé du ticket.

Golden ciblé : `status_code` + invariants liés aux acceptance criteria. Aucun
compte exact n'est figé — le jeu de données du site de test évolue.

Lecture seule : uniquement des GET, plus le POST de `sign-in`. Aucune écriture.

Lancer :
    uv run --with pytest --with httpx --with python-dotenv \
      pytest tests/test_bov2kaban_2214_customer_account_detail.py -v
"""

import os
from collections import Counter
from datetime import datetime
from urllib.parse import urlparse

import httpx
import pytest
from dotenv import load_dotenv

load_dotenv()


# ── Garde-fou anti-prod : la vérification ne cible que le staging ──
HOST_ALLOWLIST = {"staging.cashpad.app"}

# Site vérifié le 2026-09-09 (CP-STAGING-ALAIN / cashpad-8007) et son témoin,
# utilisé uniquement pour prouver le cloisonnement par site.
SITE = 4652
CONTROL_SITE = 4757

MAX_LIMIT = 50

# Les trois valeurs réellement acceptées par `kind` (l'enum du service).
# `ticket` est le kind issu du join ventes ; les deux autres sont les opérations
# de compte, que le ticket regroupe sous le seul libellé `account_operation`.
KIND_TICKET = "ticket"
ACCOUNT_KINDS = ("account", "loyaltyPoints")
ALL_KINDS = (KIND_TICKET,) + ACCOUNT_KINDS

# Compte porteur d'un long historique mixte au 2026-09-09 ("Cashpad NR auto
# test"). Utilisé seulement comme chemin rapide : s'il n'a plus de tickets, la
# fixture balaie le site pour en retrouver un.
KNOWN_CUSTOMER_WITH_TICKETS = "ccc857d8-ff2f-49c7-b671-21c6df101c9e"

# Les trois soldes que le détail doit porter (AC2).
BALANCE_FIELDS = ("account", "balance", "loyaltyPoints")

# Rien de ce qui ressemble à un relevé ou une facture ne doit apparaître (AC5).
FORBIDDEN_KIND_HINTS = ("statement", "invoice", "releve", "relevé", "facture")


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


def detail(client: httpx.Client, customer: str, site: int = SITE) -> httpx.Response:
    return client.get(f"/p/customers/api/1/site/{site}/customers/{customer}")


def operations(client: httpx.Client, customer: str, site: int = SITE, **params) -> httpx.Response:
    return client.get(
        f"/p/customers/api/1/site/{site}/customers/{customer}/operations", params=params
    )


def payload(response: httpx.Response) -> dict:
    """Corps JSON d'une réponse 200, avec le garde-fou de la SPA HTML servie en 200."""
    assert response.status_code == 200, f"HTTP {response.status_code} : {response.text[:200]}"
    content_type = response.headers.get("content-type", "")
    assert "application/json" in content_type, (
        f"content-type inattendu {content_type!r} — la requête est-elle retombée sur la SPA ?"
    )
    return response.json()


def collect_feed(client: httpx.Client, customer: str, **params) -> list:
    """Parcourt toutes les pages du feed et renvoie les entrées concaténées."""
    rows, skip = [], 0
    while True:
        body = payload(operations(client, customer, limit=MAX_LIMIT, skip=skip, **params))
        rows.extend(body["data"])
        if not body["data"] or len(rows) >= body["total"]:
            return rows
        skip += MAX_LIMIT


def as_datetime(value: str) -> datetime:
    """Parse une date ISO 8601 UTC telle que servie par l'API (`...Z`)."""
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def ticket_count(client: httpx.Client, customer: str) -> int:
    """Nombre d'entrées `ticket` d'un compte, lu via `total` (une seule ligne rapatriée)."""
    response = operations(client, customer, kind=KIND_TICKET, limit=1)
    return payload(response)["total"] if response.status_code == 200 else 0


@pytest.fixture(scope="module")
def customer_with_tickets(client: httpx.Client) -> str:
    """Un compte du site dont le feed contient à la fois des tickets et des opérations.

    C'est la condition pour que les AC 3, 4 et 6 soient discriminantes : sans
    entrée `ticket`, le test repasserait au vert sur la régression même qu'il est
    censé attraper (le join manquant du 2026-09-08).
    """
    if ticket_count(client, KNOWN_CUSTOMER_WITH_TICKETS) > 0:
        return KNOWN_CUSTOMER_WITH_TICKETS

    listing = payload(
        client.get(f"/p/customers/api/1/site/{SITE}/customers", params={"limit": MAX_LIMIT})
    )
    for row in listing["data"]:
        if ticket_count(client, row["id"]) > 0:
            return row["id"]

    pytest.skip(
        "Aucun compte du site ne porte d'entrée `ticket` — jeu de données non "
        "discriminant pour les AC 3, 4 et 6. À re-seeder avant de conclure."
    )


def test_01_customer_of_another_site_is_not_returned(client, customer_with_tickets):
    """AC1 : demander un client d'un autre site ne renvoie pas la fiche.

    Vérifié sur les DEUX endpoints : le 2026-09-08, le détail renvoyait 404 mais
    le feed 400 — incohérence corrigée depuis, les deux répondent 404.
    """
    for response, label in (
        (detail(client, customer_with_tickets, site=CONTROL_SITE), "détail"),
        (operations(client, customer_with_tickets, site=CONTROL_SITE), "feed"),
    ):
        assert response.status_code == 404, (
            f"{label} : un client hors site devrait répondre 404, reçu "
            f"{response.status_code} — {response.text[:160]}"
        )

    # Contre-épreuve : sur son propre site, la même fiche est servie.
    assert payload(detail(client, customer_with_tickets))["id"] == customer_with_tickets


def test_02_detail_carries_credit_balance_and_loyalty_points(client, customer_with_tickets):
    """AC2 : le détail porte le crédit de compte, le solde et les points de fidélité.

    `account` (l'encours) et `balance` (le solde) sont deux champs DISTINCTS servis
    en millièmes d'euro. On fige leur présence et leur type, pas leurs valeurs, ni
    le fait qu'ils diffèrent : la donnée du moment peut légitimement les rendre
    égaux.
    """
    body = payload(detail(client, customer_with_tickets))

    for field in BALANCE_FIELDS:
        assert field in body, f"Le détail ne porte pas `{field}` : {sorted(body)}"
        assert isinstance(body[field], (int, float)), (
            f"`{field}` devrait être numérique, reçu {body[field]!r}"
        )

    # métadonnées en lecture seule annoncées par le ticket
    assert set(body) >= {"id", "code", "dateCreated", "type", "deleted"}, sorted(body)


def test_03_feed_merges_account_operations_and_tickets_chronologically(
    client, customer_with_tickets
):
    """AC3 : le feed rend opérations de compte et tickets fusionnés, ordre chronologique.

    Garde-fou du correctif du 2026-09-09 (le join tickets manquait la veille).
    Trois preuves :
      a. les deux familles sont PRÉSENTES dans le même feed ;
      b. l'ordre est décroissant (le plus récent d'abord) sur tout le feed ;
      c. le feed est bien la RÉUNION des deux familles — donc une fusion, et non
         l'une des deux listes servie seule.
    """
    feed = collect_feed(client, customer_with_tickets)
    assert feed, "Le feed est vide alors que le compte a été choisi pour son historique"

    # (a) les deux familles cohabitent
    kinds = {entry["type"] for entry in feed}
    assert KIND_TICKET in kinds, (
        "Aucune entrée `ticket` dans le feed — le join ventes a-t-il régressé ? "
        f"(kinds observés : {sorted(kinds)})"
    )
    assert kinds & set(ACCOUNT_KINDS), (
        f"Aucune opération de compte dans le feed (kinds observés : {sorted(kinds)})"
    )

    # (b) le plus récent d'abord, sur l'intégralité du feed
    dates = [as_datetime(entry["date"]) for entry in feed]
    for previous, current in zip(dates, dates[1:]):
        assert previous >= current, (
            f"Feed non trié en décroissant : {previous.isoformat()} précède {current.isoformat()}"
        )

    # (c) réunion exacte des deux familles
    per_kind = {}
    for kind in ALL_KINDS:
        per_kind[kind] = {entry["id"] for entry in collect_feed(client, customer_with_tickets, kind=kind)}
    union = set().union(*per_kind.values())
    assert {entry["id"] for entry in feed} == union, (
        "Le feed non filtré n'est pas la réunion des trois kinds — "
        "des entrées sont perdues ou dupliquées par la fusion"
    )

    # forme des entrées (nommage réel, cf. « écarts connus » en tête de fichier)
    assert set(feed[0]) >= {"id", "type", "date", "amount", "receiptSequentialId"}, sorted(feed[0])


def test_03b_paginating_the_feed_yields_no_duplicate_and_no_loss(client, customer_with_tickets):
    """Le parcours paginé du feed rend chaque entrée une fois et une seule.

    Garde-fou du correctif du 2026-09-10 (tri secondaire sur `id`). C'est la
    condition pour que l'AC3 tienne côté client : un consommateur qui pagine doit
    pouvoir reconstituer l'intégralité de l'historique. `total` a toujours été
    correct (il exclut bien les tickets annulés) — c'était la FENÊTRE qui dérapait.

    Quatre preuves, sans référence externe :
      a. le jeu de données est DISCRIMINANT — il porte encore des horodatages ex
         æquo à cheval sur les frontières de page. Sans ça, le test repasserait au
         vert sur la régression même qu'il attrape ;
      b. aucun doublon sur un parcours donné, et distinct == `total` ;
      c. le jeu obtenu ne dépend pas de la taille de page ;
      d. l'ORDRE est reproductible entre deux parcours identiques — c'est ce qui
         distingue un tri réellement stable d'un coup de chance sur la donnée.
    """
    reported = payload(operations(client, customer_with_tickets, kind=KIND_TICKET, limit=1))["total"]

    def walk(size: int) -> list:
        ids, skip = [], 0
        while True:
            body = payload(
                operations(
                    client, customer_with_tickets, kind=KIND_TICKET, limit=size, skip=skip
                )
            )
            ids.extend(entry["id"] for entry in body["data"])
            if not body["data"] or len(ids) >= body["total"]:
                return ids
            skip += size

    # (a) sans dates ex æquo débordant d'une page, le tri instable ne se voit pas
    dates = [entry["date"] for entry in collect_feed(client, customer_with_tickets, kind=KIND_TICKET)]
    tied = sum(count for count in Counter(dates).values() if count > 1)
    if tied == 0:
        pytest.skip(
            "Aucun horodatage ex æquo dans le feed — le jeu de données ne peut pas "
            "révéler une pagination instable. À re-seeder avant de conclure."
        )

    # (b) pas de doublon, et le parcours couvre exactement `total`
    walked = walk(MAX_LIMIT)
    duplicates = len(walked) - len(set(walked))
    assert duplicates == 0, (
        f"{duplicates} doublon(s) sur un parcours en pages de {MAX_LIMIT} — "
        "tri instable sur les dates ex æquo (le tie-breaker a-t-il sauté ?)"
    )
    assert len(set(walked)) == reported, (
        f"`total` annonce {reported} entrées, le parcours n'en rend que "
        f"{len(set(walked))} distinctes — {reported - len(set(walked))} ticket(s) injoignable(s)"
    )

    # (c) le résultat ne doit pas dépendre de la taille de page. En pages de 10,
    # les frontières sont bien plus nombreuses : c'est là que la perte culminait.
    small = walk(10)
    assert len(small) == len(set(small)), (
        f"{len(small) - len(set(small))} doublon(s) en pages de 10 alors que le "
        f"parcours en pages de {MAX_LIMIT} est propre — instabilité aux frontières"
    )
    assert set(small) == set(walked), (
        f"Le parcours en pages de 10 rend {len(set(small))} entrées distinctes contre "
        f"{len(set(walked))} en pages de {MAX_LIMIT} — la pagination perd des lignes"
    )

    # (d) deux parcours identiques doivent rendre le MÊME ordre, pas seulement le
    # même ensemble : c'est la signature d'un tri déterministe.
    assert walk(10) == small, (
        "Deux parcours successifs en pages de 10 rendent un ordre différent — "
        "le tri n'est pas déterministe sur les horodatages ex æquo"
    )


def test_04_filtering_on_a_single_kind_returns_only_that_kind(client, customer_with_tickets):
    """AC4 : filtrer le feed sur un `kind` ne renvoie que les entrées de ce kind.

    Garde-fou du second correctif du 2026-09-09 : la veille, `kind` était absent du
    contrat et silencieusement ignoré. Deux preuves, pour ne pas confondre « filtre
    inerte » et « filtre correct sans donnée à filtrer » :
      a. le paramètre est DÉCLARÉ — une valeur invalide est rejetée en 400 `Enum`,
         là où un paramètre inconnu le serait en `AdditionalProperties` ;
      b. chaque kind ne rend que ses propres entrées, et la somme couvre le feed.
    """
    # (a) déclaré au contrat, et distinct d'un paramètre inconnu
    invalid = operations(client, customer_with_tickets, kind="maybe")
    assert invalid.status_code == 400, (
        f"`kind=maybe` renvoie {invalid.status_code} au lieu de 400 — "
        "le paramètre est-il redevenu inconnu et silencieusement ignoré ?"
    )
    assert invalid.json()["data"] == {"kind": "Enum"}, invalid.json()

    unknown = operations(client, customer_with_tickets, totallyBogusParam="maybe")
    assert unknown.status_code == 400, (
        f"Un paramètre inconnu devrait être rejeté, reçu {unknown.status_code}"
    )
    assert unknown.json()["data"] == {"totallyBogusParam": "AdditionalProperties"}, unknown.json()

    # `account_operation`, la valeur documentée par le ticket, N'EST PAS l'enum réel.
    documented = operations(client, customer_with_tickets, kind="account_operation")
    assert documented.status_code == 400, (
        "`kind=account_operation` (valeur de la section Solution) est aujourd'hui "
        f"rejeté en 400 ; reçu {documented.status_code}. Si ce step casse, c'est "
        "que l'enum a été aligné sur le ticket — mettre le fichier à jour."
    )

    # (b) chaque filtre est homogène et non vide
    seen = set()
    for kind in ALL_KINDS:
        entries = collect_feed(client, customer_with_tickets, kind=kind)
        offenders = {entry["type"] for entry in entries} - {kind}
        assert not offenders, f"`kind={kind}` renvoie aussi des entrées {sorted(offenders)}"
        seen |= {entry["id"] for entry in entries}

    assert seen == {entry["id"] for entry in collect_feed(client, customer_with_tickets)}


def test_05_no_statement_or_invoice_entry_appears(client, customer_with_tickets):
    """AC5 : aucune entrée de relevé ni de facture dans le feed (lot ultérieur)."""
    feed = collect_feed(client, customer_with_tickets)

    kinds = {entry["type"] for entry in feed}
    assert kinds <= set(ALL_KINDS), (
        f"Kinds inattendus dans le feed : {sorted(kinds - set(ALL_KINDS))} — "
        "des relevés ou factures sont-ils arrivés dans le lot courant ?"
    )

    for entry in feed:
        blob = " ".join(str(value).lower() for value in entry.values())
        hits = [hint for hint in FORBIDDEN_KIND_HINTS if hint in blob]
        assert not hits, f"L'entrée {entry['id']} évoque {hits} : {entry}"


def test_06_ticket_detail_is_reachable_from_the_feed_reference(client, customer_with_tickets):
    """AC6 : le détail d'un ticket est récupérable depuis la référence rendue par le feed.

    La référence est `receiptSequentialId` (et `id` de la forme `ticket:<seq>`).
    Elle se résout sur le service `digested-data`, et la parité du montant prouve
    qu'on atterrit sur le BON ticket — pas juste sur un 200.

    Rappel d'unités : les entrées `ticket` portent des euros décimaux, ce qui les
    rend directement comparables à `finalAmountWithTax`. Les opérations `account`,
    elles, sont en millièmes — ne pas étendre cette comparaison au reste du feed.
    """
    tickets = collect_feed(client, customer_with_tickets, kind=KIND_TICKET)
    assert tickets, "Aucune entrée `ticket` : AC6 non discriminante"

    for entry in tickets[:3]:
        reference = entry["receiptSequentialId"]
        assert reference is not None, f"L'entrée ticket {entry['id']} ne porte pas de référence"
        assert entry["id"] == f"ticket:{reference}", (
            f"Forme d'identifiant inattendue : {entry['id']!r} pour la référence {reference}"
        )

        receipt = payload(
            client.get(f"/p/digested-data/api/1/site/{SITE}/receipts/{reference}")
        )["receipt"]

        assert float(entry["amount"]) == pytest.approx(receipt["finalAmountWithTax"]), (
            f"Le ticket {reference} résout sur un montant {receipt['finalAmountWithTax']} "
            f"alors que le feed annonce {entry['amount']} — mauvaise résolution de référence"
        )
