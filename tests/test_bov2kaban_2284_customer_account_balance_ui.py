from __future__ import annotations

"""
Test de non-régression généré par /cp-test — ticket BOV2KABAN-2284
Customer detail view displays the same value for On account and Balance

Fige le comportement OBSERVÉ et VALIDÉ le 2026-09-09 sur le staging
(host allowlisté : staging.cashpad.app) :

    https://staging.cashpad.app/site/{SITE}/customers/(customer:{CUSTOMER_ID}/info)

Le bug : le bloc « Account » du panneau de détail affichait la même valeur dans
« On account » et dans « Balance » (les deux à la valeur de `balance`). Au
2026-09-09 les deux tuiles portent bien deux valeurs distinctes.

## Ce qui est figé, et pourquoi ce n'est pas « les deux valeurs diffèrent »

Assertion naïve possible : `on_account != balance`. Elle est faible — elle repasse
au vert dès que les deux champs diffèrent, y compris si l'UI les a interverti, et
elle casse toute seule le jour où le client de test se retrouve légitimement avec
`account == balance`.

Ce fichier fige donc le **mapping** : chaque tuile affichée est comparée au champ
d'API qui doit l'alimenter (`account` pour « On account », `balance` pour
« Balance »), lu au même instant. Aucun montant n'est écrit en dur : le réplica
staging est réalimenté par des pulls, les valeurs bougent.

Les montants du ticket (On account 1 035,39 € / Balance 1 102,89 €) correspondaient
le 2026-09-09 à `account: 1035390` et `balance: 1102890` — l'API sert des
**millièmes d'euro**, d'où la division par 1000 dans `api_amount`.

## Trois surfaces, trois steps

* `test_01` — les deux tuiles du panneau portent des valeurs distinctes (le
  symptôme littéral du ticket). Skippé si la donnée du moment rend le cas non
  discriminant (`account == balance` côté API) : ce serait alors un faux échec.
* `test_02` — chaque tuile vaut le champ d'API correspondant (le vrai garde-fou :
  interdit aussi bien la duplication que l'interversion).
* `test_03` — la ligne de liste du même client affiche le même couple que le
  panneau. La liste n'était pas touchée par le ticket, mais c'est la surface d'à
  côté qui lit les deux mêmes champs : une régression de mapping y sortirait aussi.

Lecture seule : le parcours ne fait que lire. Aucune écriture métier.

Prérequis, une fois :
    uv run --with playwright playwright install chromium

Lancer :
    uv run --with pytest --with pytest-playwright --with python-dotenv \
      pytest tests/test_bov2kaban_2284_customer_account_balance_ui.py -v

    # à l'œil, pour investiguer
    ... pytest tests/test_bov2kaban_2284_customer_account_balance_ui.py -v --headed --slowmo 300
"""

import os
import re
from urllib.parse import urlparse

import pytest
from dotenv import load_dotenv

load_dotenv()


# ── Garde-fou anti-prod : la vérification ne cible que le staging ──
HOST_ALLOWLIST = {"staging.cashpad.app"}

SITE = 4652
# « Cashpad NR auto test Prenom » — le client du ticket. Choisi parce qu'il porte
# un acompte : c'est ce qui écarte `account` de `balance` et rend le cas visible.
CUSTOMER_ID = "ccc857d8-ff2f-49c7-b671-21c6df101c9e"

# Libellé de tuile → champ d'API qui doit l'alimenter.
TILE_TO_API_FIELD = {"On account": "account", "Balance": "balance"}

# ── Sondes DOM, validées le 2026-09-09 ────────────────────────────────────────

# Les trois tuiles du bloc « Account » du panneau de détail.
#
# Ne PAS chercher la tuile par son libellé sur tout le document : « On account »
# et « Balance » sont AUSSI des en-têtes de colonnes AG Grid, avec le même texte.
# Une recherche globale tombe sur l'en-tête (piège rencontré en écrivant ce
# fichier : la sonde renvoyait `null` pour l'une et la bonne valeur pour l'autre,
# au gré de l'ordre du DOM). On reste donc scopé à `.outlet__account`.
JS_PANEL_TILES = """
() => {
  const stats = document.querySelectorAll('.outlet__account .account__stat');
  if (!stats.length) return null;
  const out = {};
  stats.forEach(s => {
    const l = s.querySelector('.account__label'), v = s.querySelector('.account__value');
    if (l && v) out[l.textContent.trim()] = v.textContent.trim();
  });
  return out;
}
"""

# Cellules de la ligne de liste du client, par `col-id`.
JS_ROW_CELLS = """
(id) => {
  const row = document.querySelector(`.ag-row[row-id="${id}"]`);
  if (!row) return null;
  const out = {};
  row.querySelectorAll('[col-id]').forEach(c => { out[c.getAttribute('col-id')] = c.textContent.trim(); });
  return out;
}
"""

# Fiche client servie par l'API, lue depuis le contexte de la page avec le JWT que
# l'app a stocké. `localStorage.getItem` rend la valeur JSON, guillemets inclus :
# sans `JSON.parse`, le header part malformé et nginx répond 500.
JS_API_CUSTOMER = """
async ([site, id]) => {
  let token = localStorage.getItem('token');
  try { token = JSON.parse(token); } catch (e) {}
  const r = await fetch(`/p/customers/api/1/site/${site}/customers/${id}`,
    { headers: { authorization: `Bearer ${token}`, accept: 'application/json' } });
  // Un 200 en text/html est la coquille de la SPA, pas l'API : on le refuse.
  const ct = r.headers.get('content-type') || '';
  if (r.status !== 200 || !ct.includes('json')) return { status: r.status, contentType: ct };
  return { status: 200, body: await r.json() };
}
"""

JS_HAS_ROWS = "() => document.querySelectorAll('.ag-row[row-id]').length > 0"


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


def displayed_amount(text: str) -> float:
    """« 1 035,39 € » → 1035.39.

    Les espaces de milliers sont des espaces insécables (U+00A0 / U+202F) : on
    retire tout ce qui n'est ni chiffre, ni séparateur, ni signe.
    """
    cleaned = re.sub(r"[^0-9,.\-]", "", text).replace(",", ".")
    assert cleaned not in ("", "-"), f"Montant illisible : {text!r}"
    return float(cleaned)


def api_amount(value: int) -> float:
    """L'API sert des millièmes d'euro : 1035390 → 1035.39."""
    return round(value / 1000, 2)


@pytest.fixture(scope="module")
def detail_panel(browser):
    """Session BO authentifiée, posée sur la fiche du client, panneau ouvert.

    Portée module : une seule connexion pour les trois steps, qui ne font que lire
    et ne modifient donc pas l'état de la page.
    """
    env = get_env()
    context = browser.new_context(viewport={"width": 1600, "height": 1000})
    page = context.new_page()

    url = f"{env['base']}/site/{SITE}/customers/(customer:{CUSTOMER_ID}/info)"
    page.goto(url, wait_until="domcontentloaded")

    # L'app redirige vers /auth ; le mot de passe n'est jamais journalisé.
    page.wait_for_url("**/auth**", timeout=30_000)
    page.locator('input[type="password"]').wait_for(timeout=30_000)
    text_inputs = page.locator('form input:not([type="password"])')
    text_inputs.first.fill(env["login"])
    page.locator('input[type="password"]').fill(env["password"])
    page.get_by_role("button", name="Login").click()

    # Après login l'app repart sur la route demandée, panneau de détail compris.
    page.wait_for_url(f"**/site/{SITE}/customers**", timeout=60_000)
    if CUSTOMER_ID not in page.url:
        page.goto(url, wait_until="domcontentloaded")

    page.wait_for_function(JS_HAS_ROWS, timeout=60_000)
    # Les tuiles arrivent avec la fiche, après la grille : on les attend explicitement.
    page.wait_for_function(
        "() => !!document.querySelector('.outlet__account .account__value')", timeout=60_000
    )

    try:
        yield page
    finally:
        context.close()


def panel_tiles(page) -> dict:
    tiles = page.evaluate(JS_PANEL_TILES)
    assert tiles, "Bloc « Account » absent du panneau de détail"
    for label in TILE_TO_API_FIELD:
        assert label in tiles, f"Tuile « {label} » absente du bloc Account : {sorted(tiles)}"
    return tiles


def api_customer(page) -> dict:
    result = page.evaluate(JS_API_CUSTOMER, [SITE, CUSTOMER_ID])
    assert result["status"] == 200, f"Lecture API en échec : {result}"
    return result["body"]


def test_01_on_account_and_balance_are_two_distinct_values(detail_panel):
    """Le symptôme du ticket : les deux tuiles ne doivent plus afficher la même valeur.

    Skippé si la donnée du moment ne discrimine pas — `account == balance` est un
    état légitime (client sans acompte), et l'échec serait alors un artefact du
    jeu de données, pas une régression.
    """
    page = detail_panel
    customer = api_customer(page)

    if customer["account"] == customer["balance"]:
        pytest.skip(
            f"account == balance ({customer['account']}) sur ce client : "
            "cas non discriminant, voir test_02 pour le garde-fou de mapping"
        )

    tiles = panel_tiles(page)
    assert displayed_amount(tiles["On account"]) != displayed_amount(tiles["Balance"]), (
        f"« On account » et « Balance » affichent la même valeur ({tiles['On account']!r}) "
        f"alors que l'API sert account={customer['account']} et balance={customer['balance']} "
        "— régression de BOV2KABAN-2284"
    )


def test_02_each_tile_maps_to_its_own_api_field(detail_panel):
    """Chaque tuile vaut le champ d'API qui doit l'alimenter.

    Le vrai garde-fou : interdit la duplication d'un champ sur les deux tuiles
    comme leur interversion, sans figer aucun montant.
    """
    page = detail_panel
    customer = api_customer(page)
    tiles = panel_tiles(page)

    for label, field in TILE_TO_API_FIELD.items():
        assert displayed_amount(tiles[label]) == api_amount(customer[field]), (
            f"Tuile « {label} » affiche {tiles[label]!r} "
            f"au lieu de {api_amount(customer[field])} (champ API `{field}`)"
        )


def test_03_the_list_row_shows_the_same_pair_as_the_panel(detail_panel):
    """La ligne de liste du même client affiche le même couple que le panneau.

    Surface voisine, mêmes deux champs : une régression de mapping s'y verrait
    aussi. Les `col-id` de la grille portent les noms des champs d'API.
    """
    page = detail_panel
    tiles = panel_tiles(page)

    cells = page.evaluate(JS_ROW_CELLS, CUSTOMER_ID)
    assert cells, f"Ligne du client {CUSTOMER_ID} absente de la grille"

    for label, col_id in TILE_TO_API_FIELD.items():
        assert col_id in cells, f"Colonne `{col_id}` absente de la ligne : {sorted(cells)}"
        assert displayed_amount(cells[col_id]) == displayed_amount(tiles[label]), (
            f"Colonne `{col_id}` = {cells[col_id]!r} "
            f"mais tuile « {label} » = {tiles[label]!r} — liste et panneau divergent"
        )
