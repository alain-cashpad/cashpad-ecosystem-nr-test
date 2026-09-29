from __future__ import annotations

"""
Test de non-régression généré par /cp-test — ticket BOV2KABAN-2217
[FRONT] Build customer account edit form with per-field auto-save

Fige le parcours OBSERVÉ et VALIDÉ le 2026-09-10 sur le staging
(host allowlisté : staging.cashpad.app), onglet Information de la fiche client :

    https://staging.cashpad.app/site/{SITE}/customers/(customer:{id}/info)

⚠️ **Ce fichier ÉCRIT — mais il est auto-suffisant.** Comme
`test_bov2kaban_2216`, il **crée son propre compte** au setup (Partner API
`create_customer`) et le **soft-delete au teardown** (`delete_customer`) : deux
exécutions n'accumulent rien, et aucun compte de fixture d'un autre fichier
n'est jamais visé — en particulier pas `Cashpad NR auto test`, dont dépendent
`test_bov2kaban_2212`, `2214` et `2215`.

## Trois pièges d'automatisation, chacun capable de produire un faux échec

1. **Les inputs sont `readOnly: true` au repos.** C'est un garde anti-autofill
   (`kr-no-autofill`) qui bascule à `false` au clic, PAS un formulaire verrouillé.
   Lire le DOM sans interagir fait conclure à tort que rien n'est éditable.
2. **`kr-select` et `kr-toggle` n'ouvrent rien sur événement synthétique.** Ils
   exigent de vrais événements utilisateur — d'où `page.click()` de Playwright
   plutôt qu'un `dispatchEvent`. Ils ne sont d'ailleurs pas exposés comme
   contrôles interactifs dans l'arbre d'accessibilité (simple texte, sans rôle),
   donc pas de `get_by_role` possible : on les vise par `formcontrolname`.
3. **Le formulaire sauvegarde au blur, sans bouton.** Vérifier l'écran ne suffit
   pas : ce fichier intercepte le trafic **PATCH** et asserte le nombre exact de
   requêtes et leur corps. C'est le seul moyen de distinguer « a sauvegardé ce
   champ » de « a sauvegardé tout le formulaire », et de prouver l'AC4 (aucune
   sauvegarde sur un champ inchangé), qui est une assertion d'ABSENCE.

## Écarts connus, NON figés ici

Hors périmètre des acceptance criteria :

* une `city` de plus de 255 caractères renvoie **500** en fuitant l'erreur
  Postgres brute (`value too long for type character varying(255)`) au lieu du
  payload d'erreur standard ;
* `companyParticipation` accepte `999` et `-5` côté API alors que le spinbutton
  affiche une plage 0–100 : aucun contrôle de plage serveur ;
* `language` accepte `'xx'` côté API alors que le select propose une liste fixe :
  aucun contrôle d'enum serveur ;
* le bloc Metadata affiche la date de création et l'identifiant technique mais
  **pas la référence externe**, que la section Solution du ticket liste.

Golden ciblé : nombre et corps des PATCH + relecture du compte. Aucune valeur
métier figée en dur — les valeurs sont générées à chaque run.

Prérequis, une fois :
    uv run --with playwright playwright install chromium

Lancer :
    uv run --with pytest --with pytest-playwright --with httpx --with python-dotenv \
      pytest tests/test_bov2kaban_2217_customer_edit_form_ui.py -v
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

# Champs texte du set éditable, visibles en mode Individual.
TEXT_FIELDS = ("lastName", "firstName", "email", "phone", "street", "zipCode", "city", "code")

# Répartition attendue des contrôles selon le type de compte (AC2).
INDIVIDUAL_ONLY = {"lastName", "firstName", "companyParticipation", "adult"}
COMPANY_ONLY = {"company", "active"}

# Enregistreur de PATCH posé sur la page : le formulaire n'a pas de bouton de
# sauvegarde, l'observable est donc le trafic réseau, pas un état d'écran.
JS_PATCH_RECORDER = """
() => {
  if (window.__patches) return;
  window.__patches = [];
  const origFetch = window.fetch;
  window.fetch = async function (input, init) {
    const method = ((init && init.method) || (input && input.method) || 'GET').toUpperCase();
    if (method === 'PATCH') {
      let body = null;
      try { body = init && init.body ? JSON.parse(init.body) : null; } catch (e) {}
      const entry = { url: typeof input === 'string' ? input : input.url, body, status: null };
      window.__patches.push(entry);
      const r = await origFetch.apply(this, arguments);
      entry.status = r.status;
      return r;
    }
    return origFetch.apply(this, arguments);
  };
  const origOpen = XMLHttpRequest.prototype.open;
  const origSend = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function (m, u) { this.__m = m; this.__u = u; return origOpen.apply(this, arguments); };
  XMLHttpRequest.prototype.send = function (b) {
    if (String(this.__m).toUpperCase() === 'PATCH') {
      let body = null; try { body = b ? JSON.parse(b) : null; } catch (e) {}
      const entry = { url: this.__u, body, status: null };
      window.__patches.push(entry);
      this.addEventListener('load', () => { entry.status = this.status; });
    }
    return origSend.apply(this, arguments);
  };
}
"""

JS_RESET_PATCHES = "() => { window.__patches.length = 0; }"
JS_READ_PATCHES = "() => window.__patches.map(p => ({ body: p.body, status: p.status }))"
JS_CONTROL_NAMES = """
() => [...document.querySelectorAll('.outlet__content [formcontrolname]')]
        .map(e => e.getAttribute('formcontrolname'))
"""
JS_FORM_READY = "() => !!document.querySelector('.outlet__content [formcontrolname]')"

# Contrôles éditables situés APRÈS le titre « Metadata » (AC6).
JS_METADATA_EDITABLES = """
() => {
  const content = document.querySelector('.outlet__content');
  const all = [...content.querySelectorAll('*')];
  const title = all.find(e => (e.textContent || '').trim() === 'Metadata' && !e.children.length);
  if (!title) return null;
  return all.slice(all.indexOf(title) + 1).filter(e =>
    ['INPUT', 'SELECT', 'TEXTAREA'].includes(e.tagName) ||
    e.hasAttribute('formcontrolname') ||
    e.getAttribute('contenteditable') === 'true'
  ).length;
}
"""


def get_env() -> dict:
    """Base staging, identifiants BO (formulaire) et partenaire (create/delete)."""
    names = (
        "STAGING_BASE_URL",
        "BOV2_STAGING_LOGIN",
        "BOV2_STAGING_PASSWORD",
        "APIUSER_EMAIL",
        "APIUSER_TOKEN",
        "INSTALLATION_ID",
    )
    values = {name: os.getenv(name) for name in names}
    missing = [name for name, value in values.items() if not value]
    if missing:
        pytest.skip(f"Variables manquantes dans .env : {missing}")

    base = values["STAGING_BASE_URL"].rstrip("/")
    host = urlparse(base).hostname
    assert host in HOST_ALLOWLIST, f"Host hors allowlist : {host!r} — refus d'exécuter"
    values["STAGING_BASE_URL"] = base
    return values


@pytest.fixture(scope="module")
def env() -> dict:
    return get_env()


@pytest.fixture(scope="module")
def api(env) -> httpx.Client:
    """Client API BO, utilisé pour relire le compte — l'écran ne se valide pas seul."""
    with httpx.Client(base_url=env["STAGING_BASE_URL"], timeout=60) as anon:
        response = anon.post(
            "/p/sso/public/1/sign-in",
            json={"username": env["BOV2_STAGING_LOGIN"], "password": env["BOV2_STAGING_PASSWORD"]},
        )
        assert response.status_code in (200, 201), (
            f"sign-in a échoué : HTTP {response.status_code} — {response.text[:200]}"
        )
        token = response.json().get("token")
        assert token, "sign-in n'a pas renvoyé de `token`"

    with httpx.Client(
        base_url=env["STAGING_BASE_URL"],
        timeout=60,
        headers={"authorization": f"Bearer {token}", "accept": "application/json"},
    ) as authed:
        yield authed


@pytest.fixture(scope="module")
def throwaway(env, api) -> str:
    """Compte créé pour ce run, soft-deleted à la fin. Cf. l'avertissement en tête."""
    partner = {"apiuser_email": env["APIUSER_EMAIL"], "apiuser_token": env["APIUSER_TOKEN"]}
    alias = env["INSTALLATION_ID"]
    run_id = f"nr2217-{uuid.uuid4().hex[:12]}"

    with httpx.Client(base_url=env["STAGING_BASE_URL"], timeout=60) as partner_client:
        created = partner_client.post(
            f"/api/customers/v1/{alias}/create_customer",
            params=partner,
            json={
                "firstName": "Form",
                "lastName": f"Probe [{run_id}]",
                # jamais vide : une company vide est rejetée `StringEmpty`
                "company": "Form Fixture",
                "street": "2 rue du Formulaire",
                "zipCode": "75003",
                "city": "Paris",
                "country": "FR",
                "code": run_id.upper().replace("-", ""),
                "email": f"{run_id}@example.invalid",
                "phone": "+33600000003",
                "externalId": run_id,
            },
        )
        # 201, pas 200 — `scripts/seed_customers.py` se trompe sur ce point
        assert created.status_code in (200, 201), (
            f"create_customer a répondu {created.status_code} : {created.text[:200]}"
        )
        body = created.json()
        assert body.get("succeeded"), f"create_customer : {body}"
        customer_id = body["customerId"]

        deadline = time.time() + 60
        while time.time() < deadline:
            if api.get(f"/p/customers/api/1/site/{SITE}/customers/{customer_id}").status_code == 200:
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


@pytest.fixture(scope="module")
def form(browser, env, throwaway):
    """Session BO posée sur l'onglet Information du compte jetable."""
    context = browser.new_context(viewport={"width": 1600, "height": 1000})
    page = context.new_page()

    url = f"{env['STAGING_BASE_URL']}/site/{SITE}/customers/(customer:{throwaway}/info)"
    page.goto(url, wait_until="domcontentloaded")

    page.wait_for_url("**/auth**", timeout=30_000)
    page.locator('input[type="password"]').wait_for(timeout=30_000)
    page.locator('form input:not([type="password"])').first.fill(env["BOV2_STAGING_LOGIN"])
    page.locator('input[type="password"]').fill(env["BOV2_STAGING_PASSWORD"])
    page.get_by_role("button", name="Login").click()

    page.wait_for_url(f"**/site/{SITE}/customers**", timeout=60_000)
    if throwaway not in page.url:
        page.goto(url, wait_until="domcontentloaded")
    page.wait_for_function(JS_FORM_READY, timeout=60_000)
    page.evaluate(JS_PATCH_RECORDER)

    try:
        yield page
    finally:
        context.close()


def account(api: httpx.Client, customer: str) -> dict:
    response = api.get(f"/p/customers/api/1/site/{SITE}/customers/{customer}")
    assert response.status_code == 200, f"Relecture du compte : HTTP {response.status_code}"
    return response.json()


def edit_text_field(page, name: str, value: str | None) -> list:
    """Clique le champ, saisit `value` (ou rien), sort, et rend les PATCH émis.

    `value=None` = entrer puis sortir sans modifier : c'est le cas de l'AC4.
    Le clic est indispensable — il lève le `readOnly` anti-autofill.
    """
    page.evaluate(JS_RESET_PATCHES)
    field = page.locator(f"[formcontrolname={name}]")
    field.click()
    if value is not None:
        field.fill(value)
    # sortir du champ déclenche la sauvegarde
    page.locator("body").click(position={"x": 5, "y": 5})
    page.wait_for_timeout(2500)
    return page.evaluate(JS_READ_PATCHES)


def test_01_every_editable_text_field_saves_from_the_form(form, api, throwaway):
    """AC1 (champs texte) : chaque champ du set éditable est modifiable depuis le formulaire.

    Le 200 ne suffit pas : on relit le compte derrière chaque saisie.
    """
    suffix = uuid.uuid4().hex[:6]
    values = {
        "lastName": f"Nom-{suffix}",
        "firstName": f"Prenom-{suffix}",
        "email": f"probe-{suffix}@example.invalid",
        "phone": "+33600007777",
        "street": f"{suffix} rue du Test",
        "zipCode": "69003",
        "city": f"Ville-{suffix}",
        "code": f"CODE{suffix.upper()}",
    }
    problems = {}
    for name in TEXT_FIELDS:
        patches = edit_text_field(form, name, values[name])
        stored = account(api, throwaway).get(name)
        if len(patches) != 1 or patches[0]["status"] != 200 or stored != values[name]:
            problems[name] = {"patches": patches, "stored": stored, "attendu": values[name]}

    assert not problems, f"Champs non sauvegardés depuis le formulaire : {problems}"


def test_02_leaving_a_modified_field_sends_exactly_one_single_field_save(form, api, throwaway):
    """AC3 : sortir d'un champ modifié le sauvegarde, seul et sans autre action.

    « Seul » est la moitié qui compte : un formulaire qui renverrait tout le
    modèle satisferait « ça sauvegarde » tout en écrasant les champs voisins.
    """
    new_city = f"Ville-{uuid.uuid4().hex[:6]}"
    patches = edit_text_field(form, "city", new_city)

    assert len(patches) == 1, f"Attendu 1 sauvegarde, reçu {len(patches)} : {patches}"
    assert patches[0]["status"] == 200, patches
    assert patches[0]["body"] == {"city": new_city}, (
        f"Le corps envoyé n'est pas mono-champ : {patches[0]['body']}"
    )
    assert account(api, throwaway)["city"] == new_city


def test_03_leaving_an_unmodified_field_saves_nothing(form, api, throwaway):
    """AC4 : entrer puis sortir d'un champ sans le modifier ne déclenche aucune sauvegarde.

    Assertion d'ABSENCE : elle n'a de sens que parce que le test précédent prouve
    que le même geste, sur un champ modifié, produit bien une requête.
    """
    before = account(api, throwaway)
    patches = edit_text_field(form, "city", None)

    assert patches == [], f"Un champ inchangé a déclenché {len(patches)} sauvegarde(s) : {patches}"
    assert account(api, throwaway) == before, "Le compte a changé sans modification de champ"


def test_04_switching_the_account_type_swaps_the_visible_fields(form, api, throwaway):
    """AC2 : changer le type de compte change les champs affichés."""
    form.get_by_role("button", name="Individual", exact=True).click()
    form.wait_for_timeout(2000)
    individual = set(form.evaluate(JS_CONTROL_NAMES))

    form.evaluate(JS_RESET_PATCHES)
    form.get_by_role("button", name="Company", exact=True).click()
    form.wait_for_timeout(2500)
    company = set(form.evaluate(JS_CONTROL_NAMES))
    patches = form.evaluate(JS_READ_PATCHES)

    assert INDIVIDUAL_ONLY <= individual, (
        f"Champs individuels manquants en mode Individual : {INDIVIDUAL_ONLY - individual}"
    )
    assert not (INDIVIDUAL_ONLY & company), (
        f"Champs individuels toujours visibles en mode Company : {INDIVIDUAL_ONLY & company}"
    )
    assert COMPANY_ONLY <= company, (
        f"Champs société manquants en mode Company : {COMPANY_ONLY - company}"
    )
    assert not (COMPANY_ONLY & individual), (
        f"Champs société visibles en mode Individual : {COMPANY_ONLY & individual}"
    )

    # le changement de type est lui-même sauvegardé
    assert any(p["body"] == {"type": 1} and p["status"] == 200 for p in patches), patches
    assert account(api, throwaway)["type"] == 1

    # on revient en Individual pour ne pas laisser l'état au test suivant
    form.get_by_role("button", name="Individual", exact=True).click()
    form.wait_for_timeout(2000)


def test_05_invalid_input_is_not_saved_and_the_field_is_restored(form, api, throwaway):
    """AC5 (volet « retour à la valeur précédente ») : une saisie invalide n'est pas sauvegardée.

    Le formulaire valide côté client : la valeur invalide n'est jamais émise et le
    champ retrouve sa valeur stockée.

    NB : le volet « l'erreur est signalée à l'utilisateur » n'est PAS figé ici —
    aucun message n'est affiché aujourd'hui, et c'est un sujet transverse à
    l'application, pas un comportement de ce ticket.
    """
    stored_before = account(api, throwaway)["email"]
    displayed_before = form.locator("[formcontrolname=email]").input_value()

    patches = edit_text_field(form, "email", "pas-un-email")

    assert patches == [], f"Une valeur invalide a été envoyée au serveur : {patches}"
    assert form.locator("[formcontrolname=email]").input_value() == displayed_before, (
        "Le champ ne revient pas à sa valeur précédente après une saisie invalide"
    )
    assert account(api, throwaway)["email"] == stored_before


def test_06_the_metadata_block_cannot_be_edited(form):
    """AC6 : le bloc Metadata est en lecture seule — aucun contrôle de saisie."""
    editables = form.evaluate(JS_METADATA_EDITABLES)

    assert editables is not None, "Bloc « Metadata » introuvable dans le formulaire"
    assert editables == 0, f"{editables} contrôle(s) éditable(s) dans le bloc Metadata"
