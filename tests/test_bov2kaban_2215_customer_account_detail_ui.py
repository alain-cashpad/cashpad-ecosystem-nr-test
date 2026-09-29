from __future__ import annotations

"""
Test de non-régression généré par /cp-test — ticket BOV2KABAN-2215
[FRONT] Build customer account detail view with balances, activity and ticket detail

Fige le parcours OBSERVÉ et VALIDÉ le 2026-09-10 sur le staging
(host allowlisté : staging.cashpad.app) :

    https://staging.cashpad.app/site/{SITE}/customers/(customer:{id}/operations)

## Historique — pourquoi ce fichier existe

La vérification du **2026-09-08** rapportait le ticket `non conforme` (4/6 AC),
sur deux échecs qui n'étaient PAS des bugs de cet écran :

* la tuile « On account » affichait `balance` au lieu d'`account` — défaut suivi
  par **BOV2KABAN-2284** ;
* le feed ne contenait aucune entrée `Ticket` — défaut d'API suivi par
  **BOV2KABAN-2214**.

Les deux ont été livrés depuis. Re-mesuré le **2026-09-10** : 6/6.

## Ce qui rend ces tests discriminants (à ne pas casser en les « simplifiant »)

* **AC1 se vérifie sur UN SEUL client du site.** `Cashpad NR auto test` est le
  seul compte où `account` ≠ `balance` ; sur les ~92 clients `[SEED …]` les deux
  champs sont égaux, et la régression de 2284 (les deux tuiles alimentées par
  `balance`) y passerait totalement inaperçue. D'où le mapping tuile ↔ champ
  d'API plutôt qu'un `on_account != balance`, et le skip si la donnée du moment
  ne discrimine plus.
* **L'onglet « Loyalty points » est vide sur ce même client.** Un test qui
  vérifierait la restriction du feed uniquement sur lui validerait un onglet
  vide, ce qui passerait aussi avec un filtre cassé. Chaque onglet n'est donc
  asserté que si l'API annonce des entrées de ce kind, et le test exige qu'au
  moins deux onglets aient été réellement discriminants.
* **Les sondes DOM sont scopées à `.outlet__account`.** « On account » et
  « Balance » sont AUSSI des en-têtes de colonnes AG Grid : une recherche par
  libellé sur tout le document tombe sur l'en-tête (cf. BOV2KABAN-2284).

## Écarts connus, NON figés ici

Hors périmètre des acceptance criteria — ce sont des défauts ouverts, pas des
comportements à préserver :

* **les entrées de fidélité rendent les points comme une devise** : le brut
  `19000` (= 19 points) s'affiche « 19,00 € ». Les 3 entrées somment bien aux
  57 points de la tuile, mais le symbole € sur une ligne de points est faux.
* `Employee` vaut `—` sur toutes les entrées (`userId` null en amont).

La tuile « Points », elle, est correcte depuis le 2026-09-10 (`57` et non plus
`57000` non formaté) : `test_01` la vérifie comme les deux autres.

Lecture seule : le parcours ne fait que lire et naviguer. Aucune écriture métier.

Prérequis, une fois :
    uv run --with playwright playwright install chromium

Lancer :
    uv run --with pytest --with pytest-playwright --with python-dotenv \
      pytest tests/test_bov2kaban_2215_customer_account_detail_ui.py -v

    # à l'œil, pour investiguer
    ... pytest tests/test_bov2kaban_2215_customer_account_detail_ui.py -v --headed --slowmo 300
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

# Seul compte du site à porter un long historique mixte ET `account` ≠ `balance`
# au 2026-09-10 (748 tickets + 9 opérations de compte). Chemin rapide : les
# fixtures re-résolvent dynamiquement si la donnée a bougé.
KNOWN_RICH_CUSTOMER = "ccc857d8-ff2f-49c7-b671-21c6df101c9e"

# Libellé de tuile → champ d'API qui doit l'alimenter.
# Les libellés sont lus en `textContent` : la CSS les rend en capitales
# (« ON ACCOUNT »), mais le texte du DOM garde sa casse d'origine.
TILE_TO_API_FIELD = {"On account": "account", "Balance": "balance", "Points": "loyaltyPoints"}

# Libellé d'onglet de kind → valeur `kind` de l'API → libellé rendu en colonne `type`.
KIND_TABS = {
    "Account": ("account", "Account"),
    "Loyalty points": ("loyaltyPoints", "Loyalty"),
    "Tickets": ("ticket", "Ticket"),
}

# Correspondance inverse (valeur `kind` de l'API → libellé rendu en colonne
# `type`), utilisée par `test_03` pour comparer l'ordre UI à l'ordre API.
KIND_TABS_BY_API = {api_kind: row_label for api_kind, row_label in KIND_TABS.values()}

# Tout contrôle du panneau qui laisserait créer / éditer / annuler (AC6).
MUTATING_CONTROL = re.compile(
    r"(add|new|creat|edit|modif|delete|remov|cancel|annul|updat|save|debit|credit|adjust|top ?up|recharg)",
    re.I,
)

# ── Sondes DOM, validées le 2026-09-10 ────────────────────────────────────────

# Les trois tuiles du bloc « Account », avec la classe de modifier portée par la
# valeur — c'est elle qui distingue un solde négatif d'un positif (AC2).
JS_PANEL_TILES = """
() => {
  const stats = document.querySelectorAll('.outlet__account .account__stat');
  if (!stats.length) return null;
  const out = {};
  stats.forEach(s => {
    const l = s.querySelector('.account__label'), v = s.querySelector('.account__value');
    if (l && v) out[l.textContent.trim()] = {
      text: v.textContent.trim(),
      cls: v.className,
      color: getComputedStyle(v).color,
    };
  });
  return out;
}
"""

# Lignes du feed réellement rendues (AG Grid virtualise : c'est le viewport, pas
# le feed entier). Les cellules d'une même ligne sont réparties entre plusieurs
# conteneurs, d'où le regroupement par `row-index`.
JS_FEED_ROWS = """
() => {
  const content = document.querySelector('.outlet__content');
  if (!content) return null;
  const map = new Map();
  content.querySelectorAll('.ag-row').forEach(r => {
    const i = r.getAttribute('row-index');
    const cells = [...r.querySelectorAll('.ag-cell')];
    if (!cells.length) return;
    const o = map.get(i) || {};
    cells.forEach(c => {
      const id = c.getAttribute('col-id');
      if (id === 'detail') {
        const a = c.querySelector('a');
        o.hasLink = !!a;
        o.href = a ? a.getAttribute('href') : null;
      } else {
        o[id] = c.textContent.trim();
      }
    });
    map.set(i, o);
  });
  return [...map.entries()].sort((a, b) => a[0] - b[0]).map(([, o]) => o);
}
"""

# Tous les contrôles du panneau de détail (AC6).
JS_OUTLET_CONTROLS = """
() => {
  const outlet = document.querySelector('.outlet');
  if (!outlet) return null;
  return [...outlet.querySelectorAll(
    'button, a, input, select, textarea, [role=button], [contenteditable=true]'
  )].map(e => ({
    tag: e.tagName.toLowerCase(),
    text: (e.textContent || '').trim().slice(0, 60),
    cls: (e.className || '').toString().slice(0, 80),
    label: e.getAttribute('title') || e.getAttribute('aria-label') || '',
  }));
}
"""

# Les valeurs du bloc Account sont-elles éditables ? (AC6)
JS_TILES_EDITABLE = """
() => [...document.querySelectorAll('.outlet__account .account__value')].map(v => ({
  editable: v.isContentEditable,
  hasField: !!v.querySelector('input, select, textarea'),
}))
"""

# Appel API depuis le contexte de la page, avec le JWT stocké par l'app.
# `localStorage.getItem` rend la valeur JSON, guillemets inclus : sans
# `JSON.parse`, le header part malformé et nginx répond 500.
JS_API_GET = """
async (path) => {
  let token = localStorage.getItem('token');
  try { token = JSON.parse(token); } catch (e) {}
  const r = await fetch(path, { headers: { authorization: `Bearer ${token}`, accept: 'application/json' } });
  const ct = r.headers.get('content-type') || '';
  // Un 200 en text/html est la coquille de la SPA, pas l'API : on le refuse.
  if (!ct.includes('json')) return { status: r.status, contentType: ct };
  return { status: r.status, body: await r.json() };
}
"""

JS_HAS_ROWS = "() => document.querySelectorAll('.ag-row[row-id]').length > 0"
JS_HAS_TILES = "() => !!document.querySelector('.outlet__account .account__value')"

# Les onglets de kind apparaissent AVANT que la grille du feed ne soit peuplée :
# attendre `.filters__button` ne suffit pas, on lirait des cellules vides. On
# attend donc une cellule `type` réellement remplie.
JS_HAS_FEED = """
() => {
  const cells = document.querySelectorAll('.outlet__content .ag-row [col-id=type]');
  return cells.length > 0 && [...cells].some(c => c.textContent.trim() !== '');
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


def displayed_amount(text: str) -> float:
    """« 1 035,39 € » → 1035.39, « -1,72 € » → -1.72.

    Les espaces de milliers sont insécables (U+00A0 / U+202F) : on retire tout ce
    qui n'est ni chiffre, ni séparateur, ni signe.
    """
    cleaned = re.sub(r"[^0-9,.\-]", "", text).replace(",", ".")
    assert cleaned not in ("", "-"), f"Montant illisible : {text!r}"
    return float(cleaned)


def api_amount(value) -> float:
    """L'API sert des millièmes d'euro pour les soldes : 1035390 → 1035.39."""
    return round(float(value) / 1000, 2)


def api_get(page, path: str):
    result = page.evaluate(JS_API_GET, path)
    assert result.get("status") == 200, f"Lecture API en échec sur {path} : {result}"
    return result["body"]


@pytest.fixture(scope="module")
def bo(browser):
    """Contexte navigateur authentifié sur le BO staging.

    Portée module : une seule connexion pour tout le fichier. Chaque test ouvre
    l'onglet dont il a besoin dans ce contexte (le JWT vit dans le localStorage
    de l'origine, donc partagé).
    """
    env = get_env()
    context = browser.new_context(viewport={"width": 1600, "height": 1000})
    page = context.new_page()

    url = f"{env['base']}/site/{SITE}/customers"
    page.goto(url, wait_until="domcontentloaded")

    # L'app redirige vers /auth ; le mot de passe n'est jamais journalisé.
    page.wait_for_url("**/auth**", timeout=30_000)
    page.locator('input[type="password"]').wait_for(timeout=30_000)
    page.locator('form input:not([type="password"])').first.fill(env["login"])
    page.locator('input[type="password"]').fill(env["password"])
    page.get_by_role("button", name="Login").click()

    page.wait_for_url(f"**/site/{SITE}/customers**", timeout=60_000)
    page.wait_for_function(JS_HAS_ROWS, timeout=60_000)

    try:
        yield {"context": context, "env": env, "page": page}
    finally:
        context.close()


def open_customer(bo, customer_id: str, sub: str = "operations"):
    """Ouvre la fiche d'un client et attend que carte et feed soient rendus."""
    page = bo["context"].new_page()
    page.goto(
        f"{bo['env']['base']}/site/{SITE}/customers/(customer:{customer_id}/{sub})",
        wait_until="domcontentloaded",
    )
    page.wait_for_function(JS_HAS_TILES, timeout=60_000)
    if sub == "operations":
        page.wait_for_function(JS_HAS_FEED, timeout=60_000)
    return page


def list_customers(page) -> list:
    """Tous les clients du site, paginés (le service plafonne `limit` à 50)."""
    rows, skip = [], 0
    while True:
        body = api_get(page, f"/p/customers/api/1/site/{SITE}/customers?limit=50&skip={skip}")
        rows.extend(body["data"])
        if not body["data"] or len(rows) >= body["total"]:
            return rows
        skip += 50


@pytest.fixture(scope="module")
def rich_customer(bo) -> str:
    """Un client dont la fiche discrimine : `account` ≠ `balance` ET des tickets.

    Sans ces deux propriétés, AC1 et AC3 passeraient au vert sur les régressions
    mêmes qu'ils visent (tuiles dupliquées, feed sans ticket).
    """
    page = bo["page"]

    def qualifies(cid: str) -> bool:
        customer = api_get(page, f"/p/customers/api/1/site/{SITE}/customers/{cid}")
        if customer["account"] == customer["balance"]:
            return False
        feed = api_get(
            page, f"/p/customers/api/1/site/{SITE}/customers/{cid}/operations?limit=1&kind=ticket"
        )
        return feed["total"] > 0

    if qualifies(KNOWN_RICH_CUSTOMER):
        return KNOWN_RICH_CUSTOMER

    for row in list_customers(page):
        if row["account"] != row["balance"] and qualifies(row["id"]):
            return row["id"]

    pytest.skip(
        "Aucun client du site n'a à la fois `account` ≠ `balance` et des tickets — "
        "jeu de données non discriminant pour les AC 1 et 3. À re-seeder avant de conclure."
    )


def test_01_account_card_shows_credit_balance_and_loyalty_points(bo, rich_customer):
    """AC1 : ouvrir une ligne affiche la carte avec crédit, solde et points.

    Le garde-fou n'est PAS « les trois tuiles existent » mais « chaque tuile vaut
    le champ d'API qui doit l'alimenter » : c'est ce qui interdit la régression de
    BOV2KABAN-2284 (les deux premières tuiles alimentées par `balance`) et son
    symétrique, l'interversion.
    """
    page = open_customer(bo, rich_customer)
    try:
        tiles = page.evaluate(JS_PANEL_TILES)
        assert tiles, "Bloc « Account » absent du panneau de détail"

        customer = api_get(page, f"/p/customers/api/1/site/{SITE}/customers/{rich_customer}")

        for label, field in TILE_TO_API_FIELD.items():
            assert label in tiles, f"Tuile « {label} » absente : {sorted(tiles)}"
            shown = displayed_amount(tiles[label]["text"])
            # `loyaltyPoints` est un décompte, pas un montant : pas de /1000.
            expected = (
                float(customer[field]) if field == "loyaltyPoints" else api_amount(customer[field])
            )
            assert shown == expected, (
                f"Tuile « {label} » affiche {tiles[label]['text']!r} (soit {shown}) "
                f"au lieu de {expected} (champ API `{field}`)"
            )
    finally:
        page.close()


def test_02_negative_balance_is_rendered_differently(bo, rich_customer):
    """AC2 : un solde négatif se distingue visuellement d'un solde positif.

    Comparaison de DEUX fiches réelles plutôt qu'assertion sur une couleur en dur :
    ce qui doit être figé, c'est la DISTINCTION, pas la valeur du rouge.
    """
    page = bo["page"]
    negatives = [c for c in list_customers(page) if c["balance"] < 0]
    if not negatives:
        pytest.skip("Aucun client à solde négatif sur le site — AC2 non discriminante")

    negative_page = open_customer(bo, negatives[0]["id"])
    positive_page = open_customer(bo, rich_customer)
    try:
        negative = negative_page.evaluate(JS_PANEL_TILES)["Balance"]
        positive = positive_page.evaluate(JS_PANEL_TILES)["Balance"]

        assert displayed_amount(negative["text"]) < 0, (
            f"Le client choisi n'affiche pas un solde négatif : {negative['text']!r}"
        )
        assert displayed_amount(positive["text"]) > 0, (
            f"Le client témoin n'affiche pas un solde positif : {positive['text']!r}"
        )
        assert (negative["cls"], negative["color"]) != (positive["cls"], positive["color"]), (
            "Solde négatif et solde positif sont rendus à l'identique "
            f"(classe {negative['cls']!r}, couleur {negative['color']!r})"
        )
    finally:
        negative_page.close()
        positive_page.close()


def test_03_feed_merges_account_operations_and_tickets(bo, rich_customer):
    """AC3 : le feed rend opérations de compte et tickets dans une seule liste chronologique.

    Garde-fou du correctif de BOV2KABAN-2214 : le 2026-09-08, aucune entrée
    `Ticket` n'atteignait cet écran. Deux preuves :
      a. les deux familles cohabitent dans l'onglet « All » ;
      b. l'ordre rendu suit exactement celui servi par l'API — l'écran ne
         re-trie pas, ne perd ni n'intercale.
    """
    page = open_customer(bo, rich_customer)
    try:
        rows = page.evaluate(JS_FEED_ROWS)
        assert rows, "Le feed est vide alors que le client a été choisi pour son historique"

        types = {r.get("type") for r in rows}
        assert "Ticket" in types, (
            f"Aucune entrée `Ticket` rendue (types vus : {sorted(types)}) — "
            "régression du join ventes (BOV2KABAN-2214) ?"
        )
        assert "Account" in types, f"Aucune opération de compte rendue : {sorted(types)}"

        # (b) parité d'ordre avec l'API, sur le préfixe réellement rendu
        feed = api_get(
            page,
            f"/p/customers/api/1/site/{SITE}/customers/{rich_customer}/operations?limit=50",
        )["data"]
        expected = [KIND_TABS_BY_API.get(e["type"], e["type"]) for e in feed][: len(rows)]
        assert [r.get("type") for r in rows] == expected, (
            "L'ordre rendu diverge de celui servi par l'API — "
            f"UI {[r.get('type') for r in rows]} vs API {expected}"
        )
    finally:
        page.close()


def test_04_each_kind_tab_restricts_the_feed(bo, rich_customer):
    """AC4 : chaque onglet de kind restreint le feed aux entrées correspondantes.

    Un onglet n'est asserté que si l'API annonce des entrées de ce kind : sur un
    kind vide, « aucune ligne » passerait aussi bien avec un filtre cassé. Le test
    exige donc qu'au moins deux onglets aient été réellement discriminants.
    """
    page = open_customer(bo, rich_customer)
    try:
        discriminating = []
        for tab_label, (api_kind, row_label) in KIND_TABS.items():
            total = api_get(
                page,
                f"/p/customers/api/1/site/{SITE}/customers/{rich_customer}"
                f"/operations?limit=1&kind={api_kind}",
            )["total"]

            # On attend la RÉPONSE de l'appel filtré, pas un état des lignes :
            # attendre « toutes les lignes sont du bon kind » rendrait l'assertion
            # ci-dessous tautologique (un filtre cassé sortirait en timeout au lieu
            # d'un échec lisible).
            with page.expect_response(
                lambda r: "/operations" in r.url and f"kind={api_kind}" in r.url,
                timeout=30_000,
            ):
                page.get_by_role("button", name=tab_label, exact=True).click()
            page.wait_for_timeout(1200)  # laisser AG Grid repeindre
            rows = page.evaluate(JS_FEED_ROWS)

            if total == 0:
                assert not rows, (
                    f"L'onglet « {tab_label} » rend {len(rows)} ligne(s) alors que "
                    f"l'API n'annonce aucune entrée `{api_kind}`"
                )
                continue

            assert rows, f"L'onglet « {tab_label} » est vide alors que l'API annonce {total} entrée(s)"
            offenders = {r.get("type") for r in rows} - {row_label}
            assert not offenders, (
                f"L'onglet « {tab_label} » rend aussi des entrées {sorted(offenders)}"
            )
            discriminating.append(tab_label)

        assert len(discriminating) >= 2, (
            f"Un seul onglet discriminant ({discriminating}) — le jeu de données ne "
            "prouve pas que le filtre fonctionne. À re-seeder avant de conclure."
        )
    finally:
        page.close()


def test_05_ticket_entry_opens_its_detail_and_account_operation_does_not(bo, rich_customer):
    """AC5 : sélectionner un ticket ouvre son détail ; une opération de compte, non.

    Le drilldown est porté par `receiptSequentialId` : la ligne `Ticket` expose un
    lien `receipt:<seq>`, la ligne `Account` n'en a pas. On vérifie les deux sens —
    l'ouverture ET l'absence d'ouverture.
    """
    page = open_customer(bo, rich_customer)
    try:
        rows = page.evaluate(JS_FEED_ROWS)
        tickets = [r for r in rows if r.get("type") == "Ticket"]
        accounts = [r for r in rows if r.get("type") == "Account"]
        assert tickets, "Aucune ligne `Ticket` rendue : AC5 non discriminante"
        assert accounts, "Aucune ligne `Account` rendue : AC5 non discriminante"

        # une opération de compte n'offre aucun lien de détail
        assert not any(r.get("hasLink") for r in accounts), (
            "Une opération de compte expose un lien de détail alors qu'elle ne "
            "doit rien ouvrir"
        )

        # un ticket en offre un, keyé sur son `receiptSequentialId`
        ticket = tickets[0]
        assert ticket.get("hasLink"), "La ligne `Ticket` n'expose aucun lien de détail"
        match = re.search(r"receipt:(\d+)", ticket["href"] or "")
        assert match, f"Lien de détail inattendu : {ticket['href']!r}"
        sequential_id = match.group(1)

        page.click(f'.outlet__content .ag-row a[href*="receipt:{sequential_id}"]')
        page.wait_for_url(f"**receipt:{sequential_id}**", timeout=30_000)
        page.wait_for_function(
            "() => !!document.querySelector('[class*=receipt]')", timeout=30_000
        )

        # le panneau ouvert est bien CE ticket : parité du montant avec la ligne
        receipt = api_get(
            page, f"/p/digested-data/api/1/site/{SITE}/receipts/{sequential_id}"
        )["receipt"]
        assert displayed_amount(ticket["amount"]) == pytest.approx(
            receipt["finalAmountWithTax"]
        ), (
            f"Le ticket {sequential_id} ouvre sur un montant "
            f"{receipt['finalAmountWithTax']} alors que la ligne annonce "
            f"{ticket['amount']!r} — mauvaise résolution de référence"
        )

        # la liste reste visible pendant que le détail est ouvert
        assert page.evaluate(JS_HAS_ROWS), "La liste a disparu à l'ouverture du détail"
    finally:
        page.close()


def test_06_no_control_mutates_operations_or_balances(bo, rich_customer):
    """AC6 : aucun contrôle ne permet de créer, éditer ou annuler, ni d'éditer les soldes.

    Le panneau est en lecture seule : ses contrôles sont tous de navigation
    (onglets, filtres, liens de reçu, pagination de la grille).
    """
    page = open_customer(bo, rich_customer)
    try:
        controls = page.evaluate(JS_OUTLET_CONTROLS)
        assert controls, "Aucun contrôle trouvé — la sonde vise-t-elle le bon conteneur ?"

        offenders = [
            c
            for c in controls
            if MUTATING_CONTROL.search(c["text"])
            or MUTATING_CONTROL.search(c["cls"])
            or MUTATING_CONTROL.search(c["label"])
        ]
        assert not offenders, f"Contrôle(s) de mutation dans le panneau : {offenders}"

        # les valeurs de la carte ne sont pas saisissables
        for tile in page.evaluate(JS_TILES_EDITABLE):
            assert not tile["editable"] and not tile["hasField"], (
                f"Une valeur de la carte Account est éditable : {tile}"
            )
    finally:
        page.close()
