from __future__ import annotations

"""
Test de non-régression généré par /cp-test — ticket BOV2KABAN-2213
[FRONT] Build customer accounts listing view with KPIs, search, filters and columns

Fige le parcours OBSERVÉ et VALIDÉ le 2026-09-08 sur le staging
(host allowlisté : staging.cashpad.app) :

    https://staging.cashpad.app/site/{SITE}/customers

Seul test **navigateur** du repo. Les autres fichiers sont des tests HTTP ; celui-ci
pilote l'écran, parce que les acceptance criteria portent sur du rendu (indicateurs,
compteur de filtres, scroll, état vide) et non sur des réponses d'API.

## Répartition des rôles dans le fichier

* **Interactions** (saisie, clics) → locators Playwright, qui émettent de vrais
  événements. C'est indispensable : des clics synthétiques via `evaluate` cochent
  les cases sans déclencher les handlers Angular, ce qui conduit à de faux
  constats de panne.
* **Lectures d'état** (indicateurs, lignes AG Grid, overlay) → `page.evaluate`,
  avec les sélecteurs validés pendant la vérification. La liste est une AG Grid
  virtualisée : ne pas compter les lignes du DOM comme si c'était le total.

## Deux critères volontairement non couverts

* **Le sélecteur de colonnes** (AC5). Non figé ici : je n'ai pas réussi à le
  piloter de façon fiable en automatisation pendant la vérification (la case se
  cochait sans que la colonne bouge), et c'est le dev qui l'a validé à la main.
  Écrire une assertion sur un comportement que je n'ai pas observé fonctionner
  produirait un échec permanent, pas un garde-fou. À reprendre par quelqu'un qui
  fait bouger une colonne dans un vrai navigateur, puis à figer ici.
* **Le marqueur sur les lignes filtrées** (AC4). Le filtre lui-même est figé par
  `test_04`, mais pas de marqueur visuel : au 2026-09-08 les lignes du jeu
  supprimé étaient rigoureusement identiques aux actives (même structure DOM,
  même icône `user-outlined.svg`, aucun barré ni atténuation). Le dev considère le
  critère satisfait ; figer « pas de marqueur » reviendrait à interdire qu'on en
  ajoute un. Ce step reste donc silencieux sur ce point, à dessein.

Écarts relevés à la vérification et non figés (ce sont des écarts vs la section
Solution, pas des comportements à préserver) : le sélecteur de colonnes omet
« account credit » et propose « Last name » à la place ; le filtre de statut
s'appelle « Deleted accounts » (colonne `deleted`, soft-delete) là où la spec écrit
« disabled accounts » (bit `flags`, paramètre `includeDisabled`) — deux états
distincts ; Échap ne ferme pas le sélecteur de colonnes.

Lecture seule : le parcours ne fait que lire. Aucune écriture métier.

Prérequis, une fois :
    uv run --with playwright playwright install chromium

Lancer :
    uv run --with pytest --with pytest-playwright --with python-dotenv \
      pytest tests/test_bov2kaban_2213_customers_listing_ui.py -v

    # à l'œil, pour investiguer
    ... pytest tests/test_bov2kaban_2213_customers_listing_ui.py -v --headed --slowmo 300
"""

import os
from urllib.parse import urlparse

import pytest
from dotenv import load_dotenv

load_dotenv()


# ── Garde-fou anti-prod : la vérification ne cible que le staging ──
HOST_ALLOWLIST = {"staging.cashpad.app"}

SITE = 4652
CONTROL_SITE = 4757

# Libellés des trois indicateurs d'en-tête, tels qu'affichés.
INDICATORS = ("CUSTOMER ACCOUNTS", "OUTSTANDING DEBTOR AMOUNT", "OUTSTANDING CREDITOR AMOUNT")

# Terme qui ne matche aucun client, pour l'état vide.
NO_MATCH_TERM = "zzz-aucun-client-zzz"

# ── Sondes DOM, validées le 2026-09-08 ────────────────────────────────────────

# Valeur d'un indicateur, à partir de son libellé.
JS_INDICATOR = """
(label) => {
  const l = [...document.querySelectorAll('*')].find(
    e => e.children.length === 0 && e.textContent.trim().toUpperCase() === label);
  if (!l) return null;
  const box = l.closest('div').parentElement;
  const v = [...box.querySelectorAll('*')].find(
    e => e.children.length === 0 && e !== l && /[0-9]/.test(e.textContent));
  return v ? v.textContent.trim() : null;
}
"""

# État de la grille : lignes chargées, plus haut index rendu, overlay éventuel.
# `maxRowIndex` est la seule mesure fiable du nombre de lignes chargées — le DOM
# n'en contient qu'une fenêtre (virtualisation).
JS_GRID = """
() => {
  const root = document.querySelector('.ag-root');
  if (!root) return null;
  const rows = [...root.querySelectorAll('.ag-row[row-index]')];
  const idx = rows.map(r => Number(r.getAttribute('row-index')));
  const overlay = root.querySelector('.ag-overlay');
  const paging = root.querySelector('.ag-paging-panel');
  return {
    domRows: new Set(rows.map(r => r.getAttribute('row-id'))).size,
    maxRowIndex: idx.length ? Math.max(...idx) : null,
    overlayText: overlay && overlay.offsetParent !== null
      ? overlay.textContent.replace(/\\s+/g, ' ').trim() : null,
    pagingVisible: !!paging && paging.offsetParent !== null,
    headerColIds: [...root.querySelectorAll('.ag-header-row [col-id]')].map(c => c.getAttribute('col-id')),
  };
}
"""

# Total et agrégats servis par l'API, lus depuis le contexte de la page avec le
# JWT que l'app a stocké. `localStorage.getItem` rend la valeur JSON, guillemets
# inclus : sans `JSON.parse`, le header part malformé et nginx répond 500.
JS_API_TOTALS = """
async (site) => {
  let token = localStorage.getItem('token');
  try { token = JSON.parse(token); } catch (e) {}
  const r = await fetch(`/p/customers/api/1/site/${site}/customers?limit=50`,
    { headers: { authorization: `Bearer ${token}`, accept: 'application/json' } });
  if (r.status !== 200) return { status: r.status };
  const b = await r.json();
  return { status: 200, total: b.total, aggregates: b.aggregates };
}
"""

# Présence de lignes de données. Sert d'attente : voir `wait_for_rows`.
JS_HAS_ROWS = "() => document.querySelectorAll('.ag-row[row-id]').length > 0"

# Descend la grille jusqu'en bas, autant de fois que nécessaire.
JS_SCROLL_TO_BOTTOM = """
async () => {
  const vp = document.querySelector('.ag-body-viewport');
  if (!vp) return null;
  for (let i = 0; i < 12; i++) {
    vp.scrollTop = vp.scrollHeight;
    vp.dispatchEvent(new Event('scroll', { bubbles: true }));
    await new Promise(r => setTimeout(r, 700));
  }
  return { scrollTop: vp.scrollTop, scrollHeight: vp.scrollHeight, clientHeight: vp.clientHeight };
}
"""


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
def listing(browser):
    """Session BO authentifiée, posée sur la liste des comptes clients du site.

    Portée module : une seule connexion pour tous les steps. Chaque step remet la
    recherche et les filtres à zéro en entrant, pour rester indépendant de l'ordre.
    """
    env = get_env()
    context = browser.new_context(viewport={"width": 1600, "height": 1000})
    page = context.new_page()

    page.goto(f"{env['base']}/site/{SITE}/customers", wait_until="domcontentloaded")

    # L'app redirige vers /auth ; le mot de passe n'est jamais journalisé.
    page.wait_for_url("**/auth**", timeout=30_000)
    page.locator('input[type="password"]').wait_for(timeout=30_000)
    text_inputs = page.locator('form input:not([type="password"])')
    text_inputs.first.fill(env["login"])
    page.locator('input[type="password"]').fill(env["password"])
    page.get_by_role("button", name="Login").click()

    page.wait_for_url(f"**/site/{SITE}/customers**", timeout=60_000)
    wait_for_rows(page)

    try:
        yield page
    finally:
        context.close()


def wait_for_rows(page, timeout: int = 60_000) -> None:
    """Attend que la grille porte des lignes de données.

    Ne pas remplacer par `wait_for_selector('.ag-row[row-index]')` : AG Grid rend
    aussi des coquilles de lignes sans hauteur, que Playwright juge invisibles.
    L'attente expire alors sur une grille pourtant pleine — piège rencontré en
    écrivant ce fichier. On interroge donc le DOM directement.
    """
    page.wait_for_function(JS_HAS_ROWS, timeout=timeout)


def grid(page) -> dict:
    state = page.evaluate(JS_GRID)
    assert state is not None, "Grille AG Grid absente de la page"
    return state


def indicator(page, label: str) -> str | None:
    return page.evaluate(JS_INDICATOR, label)


def reset_view(page) -> None:
    """Remet la vue à son état neutre : recherche vide, aucun filtre actif."""
    search = page.locator('input[placeholder*="Search" i]')
    if search.input_value():
        search.fill("")
    if "1" in (page.get_by_role("button", name="Filters").inner_text() or ""):
        page.get_by_role("button", name="Filters").click()
        page.get_by_role("button", name="Reset all filters").click()
        page.get_by_role("button", name="Apply").click()
    wait_for_rows(page, timeout=30_000)
    page.wait_for_timeout(1_200)


def test_01_three_indicators_reflect_the_selected_site(listing):
    """AC1 : les trois indicateurs sont affichés au-dessus de la liste et reflètent le site.

    Les valeurs sont comparées à l'API lue au même instant — aucun montant n'est
    figé, le jeu de données évolue. Le rattachement au site est prouvé en
    rechargeant sur un site témoin : les trois indicateurs doivent suivre.
    """
    page = listing
    reset_view(page)

    api = page.evaluate(JS_API_TOTALS, SITE)
    assert api["status"] == 200, f"L'API de la liste répond {api['status']}"

    displayed = {label: indicator(page, label) for label in INDICATORS}
    for label, value in displayed.items():
        assert value, f"Indicateur « {label} » absent de l'en-tête"

    assert displayed["CUSTOMER ACCOUNTS"] == str(api["total"]), (
        f"Nombre de comptes affiché {displayed['CUSTOMER ACCOUNTS']!r} "
        f"≠ total API {api['total']}"
    )

    # bascule sur le site témoin : les indicateurs doivent changer avec lui
    env = get_env()
    page.goto(f"{env['base']}/site/{CONTROL_SITE}/customers", wait_until="domcontentloaded")
    page.wait_for_selector(".ag-root", timeout=60_000)
    page.wait_for_timeout(2_500)

    control_api = page.evaluate(JS_API_TOTALS, CONTROL_SITE)
    assert control_api["status"] == 200
    assert indicator(page, "CUSTOMER ACCOUNTS") == str(control_api["total"]), (
        "Les indicateurs ne suivent pas le site sélectionné"
    )

    page.goto(f"{env['base']}/site/{SITE}/customers", wait_until="domcontentloaded")
    wait_for_rows(page)


def test_02_search_narrows_the_list(listing):
    """AC2 : la recherche restreint la liste sur nom, société, email et téléphone.

    La cible est prise dans le jeu courant via l'API, puis cherchée dans l'UI
    champ par champ : c'est la sémantique qui est figée, pas un client précis.
    """
    page = listing
    reset_view(page)
    before = grid(page)["maxRowIndex"]

    target = page.evaluate(
        """
        async (site) => {
          let token = localStorage.getItem('token');
          try { token = JSON.parse(token); } catch (e) {}
          const r = await fetch(`/p/customers/api/1/site/${site}/customers?limit=50`,
            { headers: { authorization: `Bearer ${token}`, accept: 'application/json' } });
          const b = await r.json();
          const fields = ['lastName', 'firstName', 'company', 'email', 'phone'];
          return b.data.find(c => fields.every(f => c[f])) || null;
        }
        """,
        SITE,
    )
    if target is None:
        pytest.skip("Aucun compte ne renseigne les cinq champs — cas non discriminant")

    search = page.locator('input[placeholder*="Search" i]')
    for field in ("lastName", "company", "email", "phone"):
        search.fill(str(target[field]))
        page.wait_for_timeout(2_000)
        state = grid(page)
        assert state["overlayText"] is None, (
            f"search sur {field}={target[field]!r} ne renvoie rien : {state['overlayText']!r}"
        )
        assert state["maxRowIndex"] is not None
        assert state["maxRowIndex"] <= before, (
            f"search sur {field} n'a pas restreint la liste "
            f"({state['maxRowIndex']} lignes contre {before} sans filtre)"
        )

    search.fill("")
    page.wait_for_timeout(2_000)
    assert grid(page)["maxRowIndex"] == before, "La liste n'est pas restaurée après effacement"


def test_03_applying_a_filter_updates_the_list_and_the_active_count(listing):
    """AC3 : appliquer un filtre met à jour la liste et le compteur de filtres actifs."""
    page = listing
    reset_view(page)

    filters = page.get_by_role("button", name="Filters")
    assert "1" not in filters.inner_text(), "Un filtre est déjà actif avant le step"
    before = indicator(page, "CUSTOMER ACCOUNTS")

    filters.click()
    page.get_by_text("Companies", exact=True).click()
    page.get_by_role("button", name="Apply").click()
    page.wait_for_timeout(2_200)

    assert "1" in filters.inner_text(), (
        f"Le compteur de filtres actifs n'affiche pas 1 : {filters.inner_text()!r}"
    )
    after = indicator(page, "CUSTOMER ACCOUNTS")
    assert after != before, f"La liste n'a pas changé après filtrage (toujours {before})"

    filters.click()
    page.get_by_role("button", name="Reset all filters").click()
    page.get_by_role("button", name="Apply").click()
    page.wait_for_timeout(2_200)

    assert "1" not in filters.inner_text(), "Le compteur subsiste après Reset all filters"
    assert indicator(page, "CUSTOMER ACCOUNTS") == before, "Reset ne restaure pas la liste"


def test_04_account_status_filter_switches_to_the_soft_deleted_set(listing):
    """AC4 : les comptes supprimés sont absents jusqu'à application du filtre.

    Fige l'effet du filtre, pas son rendu — cf. l'en-tête du fichier sur le
    marqueur, volontairement non figé.

    Le jeu supprimé est vérifié DISJOINT du jeu par défaut via l'API : c'est ce
    qui distingue « le filtre agit » de « le filtre est ignoré », un piège réel
    (le paramètre `deleted` était inerte le matin du 2026-09-08).
    """
    page = listing
    reset_view(page)
    default_total = indicator(page, "CUSTOMER ACCOUNTS")

    filters = page.get_by_role("button", name="Filters")
    filters.click()
    page.get_by_text("Deleted accounts", exact=True).click()
    page.get_by_role("button", name="Apply").click()
    page.wait_for_timeout(2_500)

    assert "1" in filters.inner_text()
    deleted_total = indicator(page, "CUSTOMER ACCOUNTS")
    assert deleted_total != default_total, (
        f"Le filtre des comptes supprimés laisse la liste inchangée ({default_total}) — "
        "le paramètre `deleted` est-il redevenu inerte ?"
    )

    disjoint = page.evaluate(
        """
        async (site) => {
          let token = localStorage.getItem('token');
          try { token = JSON.parse(token); } catch (e) {}
          const h = { authorization: `Bearer ${token}`, accept: 'application/json' };
          const pull = async (qs) => {
            const ids = []; let skip = 0, total = null;
            for (let i = 0; i < 10; i++) {
              const r = await fetch(
                `/p/customers/api/1/site/${site}/customers?limit=50&skip=${skip}&${qs}`, { headers: h });
              if (r.status !== 200) return { error: r.status };
              const b = await r.json();
              total = b.total; ids.push(...b.data.map(c => c.id));
              if (!b.data.length || ids.length >= total) break;
              skip += 50;
            }
            return { total, ids };
          };
          const active = await pull('deleted=false');
          const removed = await pull('deleted=true');
          if (active.error || removed.error) return { error: active.error || removed.error };
          const set = new Set(active.ids);
          return { activeTotal: active.total, deletedTotal: removed.total,
                   overlap: removed.ids.filter(id => set.has(id)).length };
        }
        """,
        SITE,
    )
    assert "error" not in disjoint, f"Lecture API en échec : {disjoint}"
    assert disjoint["deletedTotal"] > 0, "Plus aucun compte supprimé sur ce site"
    assert disjoint["overlap"] == 0, (
        f"{disjoint['overlap']} compte(s) présent(s) dans les deux jeux — le filtre ne sépare pas"
    )

    reset_view(page)
    assert indicator(page, "CUSTOMER ACCOUNTS") == default_total


def test_05_scrolling_loads_every_row_without_numbered_pagination(listing):
    """AC6 : le scroll en bas charge plus de lignes, sans pagination numérotée.

    La grille est virtualisée : on ne compte pas les lignes du DOM mais le plus
    haut `row-index` rendu, qui doit atteindre `total - 1`.
    """
    page = listing
    reset_view(page)

    api = page.evaluate(JS_API_TOTALS, SITE)
    total = api["total"]
    assert total > 50, (
        f"Le site ne porte que {total} comptes : sous le premier lot de 50, "
        "le chargement à la demande n'est pas discriminant."
    )

    first_batch = grid(page)["maxRowIndex"]
    assert first_batch is not None and first_batch < total - 1, (
        "Toutes les lignes sont déjà rendues avant le scroll — plus de chargement par lots ?"
    )

    page.evaluate(JS_SCROLL_TO_BOTTOM)
    state = grid(page)
    assert state["maxRowIndex"] == total - 1, (
        f"Après scroll, la dernière ligne rendue est {state['maxRowIndex']} "
        f"au lieu de {total - 1}"
    )

    assert not state["pagingVisible"], "Un panneau de pagination AG Grid est visible"
    body_text = page.locator("body").inner_text()
    for forbidden in ("Previous", "Next", "per page", "par page"):
        assert forbidden not in body_text, f"Contrôle de pagination numérotée trouvé : {forbidden!r}"


def test_06_an_empty_result_shows_a_message(listing):
    """AC7 : un résultat vide affiche un message.

    Le libellé exact observé est « No customer accounts found ». Il est figé de
    façon souple (présence d'un message non vide) : le wording est du ressort de
    l'i18n et changera sans que ce soit une régression.
    """
    page = listing
    reset_view(page)

    page.locator('input[placeholder*="Search" i]').fill(NO_MATCH_TERM)
    page.wait_for_timeout(2_200)

    state = grid(page)
    assert state["maxRowIndex"] is None, (
        f"{state['maxRowIndex']} ligne(s) rendue(s) pour un terme sans correspondance"
    )
    assert state["overlayText"], "Aucun message affiché sur résultat vide"

    reset_view(page)
    assert grid(page)["maxRowIndex"] is not None, "La liste ne revient pas après effacement"


def test_07_default_columns_match_the_specified_set(listing):
    """Colonnes par défaut, telles qu'observées : nom, prénom, société, points, solde, participation.

    Le sélecteur lui-même n'est pas piloté ici (cf. l'en-tête du fichier) ; ce step
    fige seulement le jeu affiché à l'ouverture, qui est ce que décrit la spec.
    """
    page = listing
    reset_view(page)
    assert grid(page)["headerColIds"] == [
        "lastName",
        "firstName",
        "company",
        "loyaltyPoints",
        "balance",
        "companyParticipation",
    ]
