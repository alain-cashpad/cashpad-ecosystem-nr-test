from __future__ import annotations

"""
Test de non-régression généré par /cp-test — ticket BOV2KABAN-2203
[BACK][GET ARCHIVE CONTENT] Expose customer data in payload

Fige le comportement OBSERVÉ et VALIDÉ le 2026-09-09 sur le staging
(host allowlisté : staging.cashpad.app), endpoint public partner salesdata :

    GET {STAGING_BASE_URL}/api/salesdata/v2/{INSTALLATION_ID}/archive_content
        ?apiuser_email=...&apiuser_token=...&sequential_id={N}

Auth = credentials partner (apiuser_email / apiuser_token) — schéma propre à cet
endpoint public salesdata. Aligné sur test_bov2kaban_2121 et
test_cp_sales_data_archives_content_compare.py.

## Ce que ce fichier garde

Le ticket a connu un défaut précis, corrigé entre le 2026-09-08 et le 2026-09-09 :
`receipt.customer` exposait la valeur du `code` client **sous le nom
`external_id`**, et n'émettait jamais `code`. BOV1 émet `{code, id, name}` ; BOV2
émettait `{external_id, id, name}` — jeux de clés disjoints, valeurs égales 34/34.

C'est donc le **nom des clés** qui est figé ici, pas seulement leur présence :
c'est là qu'est passée la régression, et un test qui se contenterait de
« customer est non vide » ne l'aurait jamais vue.

`test_01` vérifie aussi qu'au moins un `code` est **non nul** : une régression qui
émettrait `code: null` partout passerait une simple vérification de présence de clé.

## Deux critères volontairement non figés

* **« A receipt carrying a loyalty card returns loyaltycard »** — non observable au
  2026-09-09 : la clé est absente sur 192/192 tickets, **des deux côtés** (BOV1
  compris). Aucun ticket du jeu de données ne porte de carte, donc rien ne
  distingue « implémenté mais jamais exercé » de « non implémenté ». Écrire une
  assertion ici produirait un échec permanent ou un faux vert, pas un garde-fou.
  À reprendre quand une vente avec carte fidélité existera dans le jeu.
* **`customer.name` en comparaison BOV1** — les chaînes diffèrent sur 34/34, mais
  c'est **BOV1 qui est dégénéré** : son `combined_name` accumule le suffixe
  ` - <company>` à chaque update (5 répétitions dans l'échantillon du 2026-09-09).
  BOV2 renvoie la valeur propre et est le côté correct (arbitrage dev du
  2026-09-08). Figer l'égalité des `name` reviendrait à exiger le bug de BOV1.

Écart hors AC relevé et non figé : BOV1 expose `transaction_id` sur certains
mouvements de caisse, BOV2 non.

## Comparaison BOV1 : opt-in explicite

`preprod.cashpad.net` est **hors de l'allowlist `/cp-test`** (`staging.cashpad.app`
seul). Les steps de parité ne s'exécutent donc **que** si `BOV1_BASE_URL` est
renseignée dans `.env` — sinon ils skippent. C'est délibéré : la sortie
d'allowlist doit rester un geste explicite, pas un effet de bord du lancement de
la suite.

Lecture seule : le parcours ne fait que des GET.

Lancer :
    uv run --with pytest --with httpx --with python-dotenv \
      pytest tests/test_bov2kaban_2203_archive_content_customer.py -v

⚠️ Le balayage porte sur 69 archives (~69 GET, ~140 avec la parité BOV1) : compter
une poignée de dizaines de secondes. Restreindre avec SEQ_FROM / SEQ_TO au besoin.
"""

import collections
import os
from urllib.parse import urlparse

import httpx
import pytest
from dotenv import load_dotenv

load_dotenv()


from _target import partner_env

# Plage d'archives du device de test, telle que balayée à la vérification.
DEFAULT_SEQ_FROM, DEFAULT_SEQ_TO = 340, 408

# Jeu de clés de `receipt.customer` observé, et identique à BOV1.
EXPECTED_RECEIPT_CUSTOMER_KEYS = {"code", "id", "name"}

# La clé fautive de la régression du 2026-09-08 : elle ne doit jamais revenir.
FORBIDDEN_RECEIPT_CUSTOMER_KEYS = {"external_id", "externalId"}


def get_env() -> dict:
    """Cible, alias et couple partenaire — cf. `_target.py` (NR_TARGET)."""
    env = partner_env()

    env["seq_from"] = int(os.getenv("SEQ_FROM", DEFAULT_SEQ_FROM))
    env["seq_to"] = int(os.getenv("SEQ_TO", DEFAULT_SEQ_TO))
    # Hors allowlist : absente par défaut, les steps de parité skippent alors.
    env["bov1_base_url"] = os.getenv("BOV1_BASE_URL")
    return env


def fetch_archive(base: str, env: dict, seq: int) -> dict | None:
    """Une archive. `None` si la plateforme ne la connaît pas (plages non alignées)."""
    url = f"{base.rstrip('/')}/api/salesdata/v2/{env['installation_id']}/archive_content"
    response = httpx.get(
        url,
        params={
            "apiuser_email": env["apiuser_email"],
            "apiuser_token": env["apiuser_token"],
            "sequential_id": seq,
        },
        timeout=60,
    )
    assert response.status_code == 200, (
        f"seq {seq} sur {urlparse(base).hostname} : statut {response.status_code}\n"
        f"{response.text[:300]}"
    )
    body = response.json()
    # Enveloppe {succeeded, version, data}, commune aux deux plateformes.
    data = body.get("data")
    if not isinstance(data, dict) or not data.get("id"):
        return None
    return data


def sweep(base: str, env: dict) -> dict[int, dict]:
    return {
        seq: archive
        for seq in range(env["seq_from"], env["seq_to"] + 1)
        if (archive := fetch_archive(base, env, seq)) is not None
    }


def linked_receipts(archive: dict) -> list[dict]:
    """Tickets porteurs d'un objet customer non vide."""
    return [r for r in (archive.get("receipts") or []) if r.get("customer")]


def customer_id_multiset(archive: dict) -> collections.Counter:
    """Multiset des `customer.id` des mouvements de caisse.

    Multiset, **jamais** comparaison positionnelle : l'ordre des mouvements diffère
    entre plateformes et une comparaison par index sortait 30 faux écarts.
    """
    return collections.Counter(
        m["customer"]["id"]
        for m in (archive.get("cashmovements") or [])
        if m.get("customer")
    )


@pytest.fixture(scope="module")
def env() -> dict:
    return get_env()


@pytest.fixture(scope="module")
def bov2(env) -> dict[int, dict]:
    archives = sweep(env["base_url"], env)
    assert archives, f"Aucune archive sur la plage {env['seq_from']}–{env['seq_to']}"
    return archives


@pytest.fixture(scope="module")
def bov1(env) -> dict[int, dict]:
    """Parité BOV1 — hors allowlist, donc strictement opt-in (cf. en-tête)."""
    if not env["bov1_base_url"]:
        pytest.skip(
            "BOV1_BASE_URL absente de .env : comparaison de parité non exécutée "
            "(preprod BOV1 est hors de l'allowlist /cp-test, opt-in explicite)"
        )
    return sweep(env["bov1_base_url"], env)


def test_01_receipt_customer_exposes_id_code_name_and_never_external_id(bov2):
    """AC1 : un ticket lié à un client expose `customer` avec id, code, name.

    `external_id` est absent — comme sur BOV1, et le réplica clients BOV2 ne porte
    aucun champ de ce nom : `code` est le seul porteur de la valeur. C'est la
    correction du défaut du 2026-09-08, et ce step est là pour qu'il ne revienne pas.
    """
    linked = [r for a in bov2.values() for r in linked_receipts(a)]
    assert linked, "Aucun ticket lié à un client sur la plage — jeu non discriminant"

    non_null_codes = 0
    for receipt in linked:
        customer = receipt["customer"]
        keys = set(customer)

        forbidden = keys & FORBIDDEN_RECEIPT_CUSTOMER_KEYS
        assert not forbidden, (
            f"Ticket {receipt['id']} : clé(s) {sorted(forbidden)} de retour sur "
            "receipt.customer — régression du mapping code/external_id (BOV2KABAN-2203)"
        )
        assert keys == EXPECTED_RECEIPT_CUSTOMER_KEYS, (
            f"Ticket {receipt['id']} : jeu de clés {sorted(keys)} "
            f"au lieu de {sorted(EXPECTED_RECEIPT_CUSTOMER_KEYS)}"
        )
        assert customer.get("id"), f"Ticket {receipt['id']} : customer.id vide"
        if customer.get("code"):
            non_null_codes += 1

    # Une régression qui émettrait `code: null` partout passerait un simple test
    # de présence de clé : on exige au moins une valeur réelle.
    assert non_null_codes, (
        f"`code` présent mais nul sur les {len(linked)} tickets liés — "
        "le champ n'est pas alimenté"
    )


def test_02_receipt_without_customer_is_absent_or_null_and_raises_no_error(bov2):
    """AC2 : un ticket sans client ne produit pas d'erreur, `customer` absent ou nul.

    L'absence d'erreur est déjà acquise : `fetch_archive` exige un 200 sur chaque
    archive. Ce step vérifie la forme du champ sur les tickets non liés.
    """
    unlinked = [
        r
        for a in bov2.values()
        for r in (a.get("receipts") or [])
        if not r.get("customer")
    ]
    assert unlinked, "Aucun ticket sans client sur la plage — jeu non discriminant"

    for receipt in unlinked:
        assert receipt.get("customer") in (None, {}), (
            f"Ticket {receipt['id']} : customer ni absent ni nul ({receipt.get('customer')!r})"
        )


def test_03_cash_movement_linked_to_a_customer_exposes_id(bov2):
    """AC3 : un mouvement de caisse lié à un client expose `customer` avec au moins `id`.

    « au moins » est pris au mot : on exige `id`, sans figer le jeu de clés exact
    (observé `{id}` seul au 2026-09-09), pour ne pas interdire un enrichissement.
    """
    linked = [
        m
        for a in bov2.values()
        for m in (a.get("cashmovements") or [])
        if m.get("customer")
    ]
    assert linked, "Aucun mouvement de caisse lié à un client — jeu non discriminant"

    for movement in linked:
        assert movement["customer"].get("id"), (
            f"Mouvement {movement.get('id')} : customer sans id "
            f"({sorted(movement['customer'])})"
        )


def test_04_archives_are_the_same_on_both_platforms(bov1, bov2):
    """AC5, préalable : « for the same archive ».

    Même device alimente les deux plateformes, donc les uuid d'archive doivent
    coïncider. Sans ce contrôle, une comparaison champ à champ ne prouve rien.
    """
    common = sorted(set(bov1) & set(bov2))
    assert common, "Aucune archive commune aux deux plateformes"

    mismatches = [
        (seq, bov1[seq].get("id"), bov2[seq].get("id"))
        for seq in common
        if bov1[seq].get("id") != bov2[seq].get("id")
    ]
    assert not mismatches, f"uuid d'archive divergents : {mismatches[:5]}"


def test_05_receipt_customer_id_and_code_match_bov1(bov1, bov2):
    """AC5 : `id` et `code` du client identiques à BOV1, ticket par ticket.

    `name` est délibérément hors du champ de ce step — cf. l'en-tête du fichier :
    la divergence vient d'un bug BOV1, l'exiger figerait ce bug.
    """
    common = sorted(set(bov1) & set(bov2))
    compared = 0
    diffs = []

    for seq in common:
        c1 = {r["id"]: r["customer"] for r in linked_receipts(bov1[seq])}
        c2 = {r["id"]: r["customer"] for r in linked_receipts(bov2[seq])}
        assert set(c1) == set(c2), (
            f"seq {seq} : tickets liés à un client différents entre plateformes "
            f"(BOV1 seul : {sorted(set(c1) - set(c2))[:3]}, "
            f"BOV2 seul : {sorted(set(c2) - set(c1))[:3]})"
        )
        for rid in c1:
            compared += 1
            for field in ("id", "code"):
                if c1[rid].get(field) != c2[rid].get(field):
                    diffs.append((seq, rid, field, c1[rid].get(field), c2[rid].get(field)))

    assert compared, "Aucun ticket lié à un client en commun — comparaison vide"
    assert not diffs, f"{len(diffs)} écart(s) BOV1↔BOV2 sur id/code : {diffs[:5]}"


def test_06_cash_movement_customers_match_bov1(bov1, bov2):
    """AC5 : même multiset de `customer.id` sur les mouvements de caisse."""
    common = sorted(set(bov1) & set(bov2))
    diffs = []

    for seq in common:
        m1, m2 = customer_id_multiset(bov1[seq]), customer_id_multiset(bov2[seq])
        if m1 != m2:
            diffs.append((seq, sorted((m1 - m2).items())[:3], sorted((m2 - m1).items())[:3]))

    assert not diffs, f"{len(diffs)} archive(s) au multiset divergent : {diffs[:3]}"
