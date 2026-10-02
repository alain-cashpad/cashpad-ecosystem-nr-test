# cashpad-ecosystem-nr-test

Harness de non-régression cross-service de l'écosystème Cashpad. Chaque fichier de `tests/` fige un comportement **observé et validé en réel** sur le staging, pour détecter les régressions ultérieures.

Ce repo ne contient **que des tests**. Aucun code applicatif, aucun secret : les identifiants vivent dans un `.env` local, jamais committé.

---

## Trois familles de tests

| Famille | Origine | Nommage |
|---|---|---|
| Collections Postman converties | export d'une collection Postman → tests E2E + modèles Pydantic inférés | `test_cp_<collection>.py` |
| Vérifications de tickets | commande `/cp-test` du vault SDD, un fichier par ticket vérifié | `test_<jira_id_lower>_<slug>.py` |
| Tests portés | réécriture des anciens repos `cashpad-bov2-non-reg-partners-api` et `cashpad-bov2-non-reg-deliverect` | `test_nr_<domaine>_<slug>.py` |

Les trois tournent avec le même `.env` et les mêmes conventions de nommage de variables.

### Tests portés (`test_nr_*`)

Réécrits le 2026-09-29 depuis les deux anciens repos, aux conventions de celui-ci. Socle commun : [tests/_nr.py](tests/_nr.py), au-dessus de `_target.py`.

| Fichier | Ancien test | Écrit ? |
|---|---|---|
| `test_nr_partners_model_payment_methods` | `get_payment_methods` | non |
| `test_nr_partners_order_precheck` | `precheck`, `partner_order_precheck` | non (precheck sans ticket) |
| `test_nr_partners_order_wrong_total` | `partner_order_wrong_total_amount` | commande `failed`, sans ticket |
| `test_nr_deliverect_order_rejections` | `deliverect_order_unknown_(sub)product`, `…_wrong_total_amount` | commandes `failed`, sans ticket (`wrong_total` sous garde) |
| `test_nr_partners_order_simple` | `order`, `partner_order`, `installation_id_mapping` | **ticket payé** |
| `test_nr_partners_order_menu` | `partner_order_with_menu` | **ticket payé** |
| `test_nr_partners_course_request` | `partner_course_request` | **ticket ouvert** |
| `test_nr_partners_payments` | `inject_single_payment`, `…_negative_payment`, `inject_multiple_payments` | **3 tickets + paiements** |
| `test_nr_salesdata_<endpoint>` (×6 : `archives`, `archive_content`, `sales_summary`, `products_summary`, `users_summary`, `cashcontainers`) | aucun : un fichier par endpoint salesdata — structure figée des champs (`test_00`, `tests/schemas/salesdata/`), enveloppe et version, cohérence interne, recoupement avec les autres endpoints et la caisse (VPN), erreurs d'entrée, mauvais token. Socle `tests/_salesdata.py`. Structure à refiger par `scripts/freeze_salesdata_schemas.py` (changement VOULU seulement) ; écarts avec la doc Notion : `scripts/compare_salesdata_doc.py`, constat dans `docs/salesdata-doc-vs-bov2.md` | non (lecture seule) |
| `test_nr_internal_rpc_contracts` | aucun : contrats entre services — sollicite les internal-rpc par des appels publics, puis cherche dans les logs les corps refusés et les appels internes en erreur (rollback du 2026-10-01) | non (lecture seule) ; logs Elasticsearch |
| `test_nr_partners_stock_state` | aucun : `stocks/v1/state` = état de la caisse (`orders/get_products_states`), et `precheck_order?check_stocks=true` qui refuse un produit désactivé | non (precheck sans ticket) ; VPN pour test_01 |
| `test_nr_smoke_post_deploy` | aucun : smoke **juste après un déploiement** (`make smoke`) — services up sur une seule build, `check` live et archivé, dernière archive digérée, signatures d'erreur du 2026-10-01 | non (lecture seule) ; pas de prod |
| `test_nr_digested_data_public_api` | aucun : API analytics publique (ventes par produit et paiements par moyen = BO, top N, `samePeriodLastYear` = requête directe un an plus tôt) | non (lecture seule) ; jeton digested-data, sinon skip |
| `test_nr_salesdata_revenue_reconciliation` | aucun : chaîne caisse → BO → analytics sur les 12 dernières archives (CA, HT, tickets, TVA par taux), repris du skill `bov2-revenue-reconciliation` | non (lecture seule) ; VPN et jeton digested-data, sinon skip |
| `test_nr_partners_receipt_event_notification` | aucun : première notification SORTANTE (`order_new_receipt_event` vers `delarte`), lue dans les logs Elasticsearch | **1 ticket ouvert** ; exige le web proxy de la caisse sur la cible |
| `test_nr_partners_check_live_receipt` | aucun : incident prod du 2026-10-01 (`check` d'un ticket live, `getLiveReceipt` sans `items`) | **4 tickets ouverts** |
| `test_nr_deliverect_orders` | `deliverect_order`, `…_with_menu`, `…_with_product_options` | **3 tickets payés** |
| `test_nr_deliverect_order_missing_fee_products` | `…_no_delivery_fees_product`, `…_no_service_charge_product` | **modifie la config du connecteur**, restaurée en `finally` |

Différences voulues avec les anciens repos :

- **Routes de la doc Notion** pour la Partner API (`/api/<capability>/<vN>/<alias>/[cashpad/]<action>`, verbe et paramètres documentés). Les anciens tests partenaires du repo Deliverect passaient par la route native `/p/partners/public/1/…`, non documentée : abandonnée. Le webhook Deliverect, qui n'est pas la Partner API, garde sa route.
- **Un statut attendu qui n'arrive pas fait échouer le test.** Les anciens sautaient leurs assertions en silence (`if order_treated:`).
- **La config du connecteur est lue puis restaurée**, jamais réécrite depuis un fichier figé.
- **Chaque en-tête distingue l'observé du porté** : ce qui a été ré-observé le 2026-09-29 et ce qui est repris de l'ancien repo sans re-mesure (lecture caisse, liste BO des commandes).

`test_nr_partners_payments` a été **rouge sur le staging** du 2026-09-29 au 2026-10-01 : `getLiveReceipt` sans `items` (BOV2KABAN-2195 sans BOV2KABAN-2344), le défaut parti en prod le 2026-10-01. **Vert depuis le 2026-10-02** (2344 déployé). Choix acté : il échoue franchement, sans xfail.

**Notifications sortantes non couvertes** (déclenchement manuel, aucun test ne peut les produire seul) : `stock_sync` (changement de stock remonté par la caisse), `menu_push_auto` (modification du menu / référentiel), `order_notify_readiness` (commande partenaire passée « prête » sur la caisse ou le KDS), `new-archive-created` (clôture d'archive). Seule `order_new_receipt_event` l'est (`test_nr_partners_receipt_event_notification`). Au 2026-10-02, obypay staging (site 4652) pointe sur `management-api.obypay.com`, l'API qu'appelle aussi la prod.

**Anomalies relevées sans être figées** (défauts BOV2, configurations douteuses, comportements à confirmer) : [docs/anomalies.md](docs/anomalies.md).

Les payloads Deliverect vivent dans `tests/payloads/deliverect/*.json.tmpl` : identifiants, dates et location sont substitués à chaque run (`_nr.deliverect_order`).

### Tests générés par `/cp-test`

`/cp-test <JIRA-ID>` rejoue en réel le comportement décrit par un ticket BOV2 contre le staging, rend un verdict, et — **uniquement si le verdict est `conforme`** — propose de générer le test qui fige ce comportement.

Le test fige **l'observé validé**, pas une re-spécification du ticket. Il est donc écrit après coup, à partir de réponses réelles capturées, et son en-tête porte la date de la vérification.

### Les tests qui écrivent

Inventaire au 2026-09-29. Tout ce qui n'y figure pas est en lecture seule, ou n'écrit que sur un UUID inexistant / des identifiants invalides (`2192`, `2262`, rejets `test_nr_*`).

| Fichier | Ce qu'un run écrit | Garde |
|---|---|---|
| `2191_create_customer` | un client jetable | `writes_guard` |
| `2193_delete_customer` | un client `CPTEST2193` créé puis supprimé (cf. ci-dessous) | `writes_guard` |
| `2194_add_credit_operation` | un client jetable crédité de montants symboliques, supprimé en `finally` | `writes_guard` |
| `2280_update_customer_patch` | un client jetable modifié | `writes_guard` |
| `2216_customer_update`, `2217_customer_edit_form_ui` | un client jetable modifié par le BO | aucune |
| `2200_customer_account_operations` | une entrée d'export prédéfini + un objet dans le bucket | aucune |
| `test_nr_*` sous `tickets_guard` | des **tickets** sur la caisse, une config Deliverect modifiée puis restaurée | `NR_ALLOW_WRITES=1` |

`writes_guard` laisse passer sur le staging et bloque ailleurs sans `NR_ALLOW_WRITES=1` ; `tickets_guard` bloque partout sans `NR_ALLOW_WRITES=1`.

#### `test_bov2kaban_2193_delete_customer.py`

Vérifier qu'une suppression supprime exige un client réel. Chaque exécution **crée un client `CPTEST2193` puis le supprime**. Coût par run = un client soft-deleted de plus sur l'installation ciblée. Aucun client préexistant n'est touché, et le teardown du fixture est idempotent : rien n'est laissé actif, même si le test échoue en cours de route.

Deux pièges du banc, appris à ses dépens le 2026-09-04 :

- **La synchro device est asynchrone.** Un client créé apparaît dans `get_customers` *avant* sa synchro, avec `version: 0` et un état transitoire (son `externalId` est encore là, il disparaîtra). Attendre la présence dans la liste ne suffit pas : il faut attendre `version > 0`, et pour une écriture ultérieure, `version > version_précédente`.
- **La file de synchro décroche sous charge.** Une création isolée converge en ~3 s, mais trois cycles create+delete enchaînés laissent la troisième création bloquée à `version: 0` au-delà de 60 s. C'est pourquoi un **seul** test couvre tout le cycle de vie (lecture → route documentée → suppression réelle) au lieu de trois fonctions avec trois fixtures : un client par run, et le fichier passe de 75 s à 11 s. Ne pas re-découper ce test sans re-mesurer.

---

## Prérequis

Pas de `pyproject.toml` : les dépendances se passent à l'exécution via `uv`, et sont tenues à **un seul endroit**, le [Makefile](Makefile) (`DEPS`, `UI_DEPS`).

| Dépendance | Utilisée par |
|---|---|
| `pytest` | tous |
| `httpx` | tests HTTP (tous sauf le test DB) |
| `python-dotenv` | tous |
| `pydantic` | tests issus de Postman (`test_cp_*`, `test_test.py`) |
| `pytest-dependency` | `test_cp_multipush`, `test_cp_sync_manager_multipush_all` (chaînage `@pytest.mark.dependency`) |
| `psycopg[binary]` | `test_bov2kaban_2111` uniquement (accès DB réplica) |
| `openpyxl` | `test_bov2kaban_2200` (lecture de l'export xlsx) — sans lui, **la collecte de `tests/` entier échoue** |
| `playwright==1.63.0`, `pytest-playwright==0.9.0` | tests d'interface `*_ui.py` uniquement (fixture `page`) |

Accès réseau : **VPN** pour les tests qui lisent une caisse (`:9091`) ; compte BO dans l'environnement pour les routes `/p/…` (cf. « Configuration »).

---

## Lancer les tests

Deux lancements **séparés** : les tests d'interface (navigateur) et le reste. Ils n'ont ni les mêmes dépendances, ni la même durée, ni les mêmes causes de panne — un Chromium manquant ne doit pas masquer un défaut d'API.

| Commande | Ce qui tourne | Durée (2026-09-29) |
|---|---|---|
| `make test` | tout `tests/` **sauf** `*_ui.py` et `test_test.py` ; tests sous garde skippés | ~5 min |
| `make ui-browsers` | installe le Chromium de `PLAYWRIGHT_VERSION` — **une fois**, et après chaque changement de version | ~1 min |
| `make test-ui` | les 4 tests d'interface `*_ui.py` (`2213`, `2215`, `2217`, `2284`) | ~1 min 30 |
| `make test-writes` | les `test_nr_*` avec `NR_ALLOW_WRITES=1` : **crée des tickets sur la caisse** et modifie puis restaure la config Deliverect | ~2 min |
| `make smoke` | `test_nr_smoke_post_deploy` seul, juste après un déploiement, sur la plateforme déployée | ~10 s |
| `make test-all` | `test` puis `test-ui` | ~6 min 30 |

Arguments pytest : `make test PYTEST_ARGS="-k 2190 -x"` (défaut `-v`). Cible préprod : `NR_TARGET=preprod make test` (tests via `_target.py` / `_nr.py` seulement).

Sans `make`, l'équivalent brut (même liste de dépendances que le Makefile) :

```bash
# tout sauf l'UI
uv run --with pytest --with httpx --with python-dotenv --with pydantic \
  --with pytest-dependency --with "psycopg[binary]" --with openpyxl \
  pytest tests/ --ignore=tests/test_test.py --ignore-glob='tests/*_ui.py' -v

# UI seule
uv run --with pytest --with httpx --with python-dotenv \
  --with "playwright==1.63.0" --with "pytest-playwright==0.9.0" \
  pytest tests/*_ui.py -v

# un fichier
uv run --with pytest --with httpx --with python-dotenv \
  pytest tests/test_bov2kaban_2190_get_customers.py -v
```

`PYTEST_VERBOSITY=1` active les traces détaillées des tests issus de Postman.

> `uv` uniquement — pas de `pip`, pas de venv à gérer à la main.

### Tests d'interface : figer Playwright

Playwright et ses navigateurs vont **par version**. Un `--with pytest-playwright` non figé tire le dernier Playwright, qui réclame un Chromium absent : `BrowserType.launch: Executable doesn't exist at …/chromium_headless_shell-XXXX` — toute l'UI part en ERROR, sans rien avoir testé. D'où `PLAYWRIGHT_VERSION` / `PYTEST_PLAYWRIGHT_VERSION` dans le Makefile. Pour monter de version : changer les deux variables, puis `make ui-browsers`.

### Point d'attention : `test_test.py` est cassé

`tests/test_test.py` ne s'importe pas — `SyntaxError: f-string: expecting '}'`, défaut de la génération Postman. Une collecte sur `tests/` entier s'interrompt donc **avant de lancer quoi que ce soit**, d'où le `--ignore`. À corriger ou à supprimer ; c'était de toute façon un fichier de bac à sable (collection « TEST »).

### État de référence — run du 2026-09-29 (staging)

Ce qu'un run « normal » donne à cette date, pour distinguer une régression d'un rouge connu.

`make test` : **111 ✅ · 19 ❌ · 12 ERROR · 44 skip · 4 xfail**.

| Rouge connu | Cause | Nature |
|---|---|---|
| `test_cp_*` (6 collections, 18 ❌) | variables absentes : `bov1_host`, `bov2_host`, `site_id`, `slug`, `bov2_token`, `cashpad_id`, `organization_id`… (cf. `.env.example`) | configuration |
| `2121` (6 ERROR) | vise la caisse **8000** (`INSTALLATION_ID=cashpad-8000-kkdf`) : rouge si `INSTALLATION_ID=cashpad-8007` | configuration |
| `2200` (6 ERROR) | les exports prédéfinis passent en `failed` sur le staging (exports 404–406) ; le test attend `bucketKey` 90 s au lieu de voir l'échec | **défaut staging** |
| `2216` (intermittent) | 1 échec sur 3 relances, sur un test différent à chaque fois (`test_01`, `test_03`) | **banc instable** |
| `test_nr_partners_payments` (sous `make test-writes`) | `400 internal communication error` sur ticket ouvert — lecture live worker → caisse, cf. en-tête du fichier ; vert en préprod | **défaut staging** |

`make test-ui` : **14 ✅ · 2 ❌ · 6 skip**.

| Rouge connu | Cause |
|---|---|
| `2213::test_07_default_columns_match_the_specified_set` | les colonnes par défaut de la grille clients ne sont plus celles figées |
| `2284::test_03_the_list_row_shows_the_same_pair_as_the_panel` | le client `ccc857d8-…` (« Cashpad NR auto test ») n'apparaît pas dans la grille |

Retirés le 2026-09-29 parce qu'ils ne correspondaient plus au comportement actuel (trace dans l'en-tête de chaque fichier) : l'assertion « `update_customer` écrase les champs » de `2193` (PATCH depuis BOV2KABAN-2280) ; les cas 400 de `2194::test_06` (format d'erreur Feathers sans clé `error`) ; `2216::test_02` (4 champs éditables acceptés mais non enregistrés : `type`, `email`, `city`, `language` — non tranché entre évolution et régression) ; le cas `lastName` de `2280::test_02` (correspondance `lastName` → `name`).

---

## `scripts/` — outillage

Contrairement à `tests/`, ces scripts **écrivent**. Ils sont lancés à la main, jamais en CI.

### `seed_customers.py`

Crée N comptes clients de test (50 par défaut) via la Partner API, pour disposer d'un jeu de données à interroger.

```bash
# plan, aucun appel réseau
uv run --with httpx scripts/seed_customers.py \
  --target bov1-preprod --alias cashpad-8007 --dry-run

# 50 clients
uv run --with httpx scripts/seed_customers.py \
  --target bov1-preprod --alias cashpad-8007
```

Chaque exécution produit des clients **neufs** : `externalId`, `code` et `email` portent un run-id horodaté (`seed-<YYYYMMDD-HHMMSS>-NNN`), qui sert aussi à retrouver un lot après coup. Relancer le script n'écrase et ne dédoublonne rien.

Identifiants : `APIUSER_EMAIL` / `APIUSER_TOKEN`, sinon `~/.config/cashpad/partners.json` via `--partner` (défaut `obypay`). Aucun token n'est affiché.

Garde-fous, dans le même esprit que la skill `bov2-partners-api` :

- `--target` est **obligatoire et sans défaut** — aucune cible par omission ;
- les cibles de **production sont absentes de la table**, pas seulement déconseillées : `argparse` refuse la valeur, un seed de comptes clients ne peut pas partir en prod par faute de frappe ;
- `--dry-run` montre le plan sans émettre un appel.

Cibles disponibles : `bov1-preprod`, `bov2-staging`, `bov2-preprod`.

> Note périmée, corrigée le 2026-09-04 : ce paragraphe affirmait que `create_customer` était cassé sur BOV2 (cf. BOV2KABAN-2191) et que seul `bov1-preprod` aboutissait. **Ce n'est plus vrai** — `POST .../create_customer` sur `bov2-staging` répond 201 `{"succeeded":true,"customerId":"…"}` et le client se synchronise en ~3 s. Vérifié en créant plusieurs clients sur `cashpad-8007`.

### `seed_customer_operations.py`

Crédite des opérations (argent ou points de fidélité) sur les comptes clients. Pendant naturel du précédent : l'un crée les comptes, l'autre les alimente.

```bash
# plan, aucun appel réseau
uv run --with httpx scripts/seed_customer_operations.py \
  --target bov1-preprod --alias cashpad-8007 --dry-run

# 3 opérations sur chaque client issu d'un seed
uv run --with httpx scripts/seed_customer_operations.py \
  --target bov1-preprod --alias cashpad-8007

# que de la fidélité, sur un client précis
uv run --with httpx scripts/seed_customer_operations.py \
  --target bov1-preprod --alias cashpad-8007 \
  --customer-id <uuid> --type points --amount-min 5 --amount-max 50
```

Options : `--per-customer` (3), `--type money|points|mixed`, `--amount-min`/`--amount-max` **en unités lisibles** (euros ou points), `--external-id-prefix` (`seed-`), `--customer-id` répétable, `--all`, `--delay`, `--seed`.

Par défaut le script ne touche **que les clients issus d'un seed** (`externalId` commençant par `seed-`). Créditer tout le site demande `--all`, explicitement.

⚠️ **`add_credit_operation` est un `GET` qui écrit** — il crédite de la valeur réelle. Filtrer sur le verbe HTTP ne protège de rien ; c'est pourquoi la skill `bov2-partners-api` l'exclut de son allowlist d'actions.

⚠️ **`transaction_id` n'est pas idempotent** (vérifié sur BOV1 preprod le 2026-09-03) : rejouer le même identifiant crée une seconde opération et recrédite le compte. Aucun filet contre un double envoi — ne pas relancer un run interrompu sans contrôler les soldes.

**Échelles**, documentées et vérifiées en réel. `amount` part ×1000 sur le fil (`5000` = 5 € ou 5 points) ; le script prend les montants en unités lisibles et convertit. En relecture c'est asymétrique : `balance` et `account` restent en ×1000, alors que `loyaltyPoints` est ramené en unités — deux échelles dans le même objet client.

### `_partner_api.py`

Socle partagé : table des cibles autorisées, chargement des identifiants, arguments de ciblage communs. La table `TARGETS` vit **là et nulle part ailleurs** — dupliquée, elle finirait par gagner une entrée de production dans un seul des fichiers.

---

## Configuration : `.env` à la racine

Chargé par `load_dotenv()` dans chaque fichier. Les variables sont déclarées en minuscules dans le code (`required = ["apiuser_email", ...]`) et lues en MAJUSCULES via `os.getenv(key.upper())`.

Modèle à copier : [.env.example](.env.example) (`cp .env.example .env`, puis remplir). `.env` est dans `.gitignore`. Une variable **déjà exportée dans le shell** est prise telle quelle : `load_dotenv()` n'écrase pas l'environnement, et `uv run` en hérite.

### Ce qu'il faut renseigner, par famille

| Pour lancer… | Variables | Sans elles |
|---|---|---|
| **tests portés `test_nr_*`** — Partner API | aucune si `~/.config/cashpad/partners.json` contient le partenaire (`NR_PARTNER`, défaut `obypay`) ; sinon `APIUSER_EMAIL`, `APIUSER_TOKEN` | `EnvironmentError` |
| `test_nr_*` — étapes BO (liste des commandes d'un connecteur, config Deliverect) | `BOV2_STAGING_LOGIN`, `BOV2_STAGING_PASSWORD` — et `BOV2_PREPROD_LOGIN`, `BOV2_PREPROD_PASSWORD` avec `NR_TARGET=preprod` ; repli `BOV2_TOKEN` | étape **skippée** |
| `test_nr_*` — lecture caisse | **VPN** actif ; `CASHPAD_ID` optionnel (défaut `cashpad-8007`) | échec de connexion |
| `test_nr_*` — tests qui créent un ticket ou modifient une config | `NR_ALLOW_WRITES=1` | module **skippé** |
| `test_nr_*` — autre cible | `NR_TARGET=preprod` (défaut `staging`), `PREPROD_BASE_URL` optionnel | — |
| **tests `/cp-test` customers** (`2190`…`2194`, `2280`) | idem Partner API ci-dessus (via `_target.py`) | `EnvironmentError` |
| tests `/cp-test` BO customers (`2200`, `2212`…`2218`, `2284`) | `STAGING_BASE_URL`, `BOV2_STAGING_LOGIN`, `BOV2_STAGING_PASSWORD` | skip |
| **tests d'interface** `*_ui.py` (`make test-ui`) | les mêmes (`STAGING_BASE_URL`, `BOV2_STAGING_LOGIN`, `BOV2_STAGING_PASSWORD`) + un Chromium installé par `make ui-browsers` | skip / ERROR `Executable doesn't exist` |
| `test_bov2kaban_2262`, `2121`, `2203`, `2223` | `STAGING_BASE_URL`, `INSTALLATION_ID`, `APIUSER_EMAIL`, `APIUSER_TOKEN` | `EnvironmentError` |
| **collections Postman `test_cp_*`** | `BOV2_HOST`, `BOV2_TOKEN` (JWT du front, expire), `SITE_ID`, `SLUG`, `CASHPAD_ID`, … (cf. « Autres variables ») | `EnvironmentError` |
| `test_bov2kaban_2111` (DB réplica) | `BOV2_STAGING_DB_URL` | skip |

Deux jetons homonymes à ne pas confondre : **`BOV2_TOKEN`** (utilisé par les `test_cp_*` et en repli par `_nr.py` sur les routes BO `/p/partners/api/…`) est le **JWT du front**, celui que le dashboard obtient au sign-in ; **`BOV2_STAGING_TOKEN`** est le bearer des routes `public/*` analytics. Aucun des deux ne vaut sur la Partner API `/api/<capability>/…`.

### Auth Partner API (query string)

La Partner API legacy s'authentifie par un couple `(email, token)` **dans la query string** — pas de header bearer. C'est un partenaire, pas un site : le même couple vaut pour toutes ses installations.

| Variable | Rôle |
|---|---|
| `APIUSER_EMAIL` | `apiuser_email` du partenaire |
| `APIUSER_TOKEN` | `apiuser_token` du partenaire |
| `INSTALLATION_ID` | alias du site ciblé (ex. `cashpad-8007`) |
| `STAGING_BASE_URL` | base du staging, ex. `https://staging.cashpad.app` |

### Auth services BOV2 (bearer)

| Variable | Rôle |
|---|---|
| `BOV2_TOKEN` | JWT du front (celui du dashboard), utilisé par les `test_cp_*` sur les routes BO `/p/partners/api/…` ; expire. Les routes `public/*` analytics prennent `BOV2_STAGING_TOKEN` |
| `BOV2_HOST`, `BOV1_HOST`, `HOST` | hosts ciblés par les comparaisons BOV1 ↔ BOV2 |

⚠️ Les deux schémas ne sont **pas** interchangeables : `BOV2_TOKEN` ne fonctionne pas sur `/api/<capability>/…`, et le couple partenaire ne fonctionne pas sur `/<service>/public/1/…`.

### Autres variables

| Variable | Utilisée par | Note |
|---|---|---|
| `SITE_ID`, `SLUG`, `CASHPAD_ID` | `test_cp_order_sequence`, `test_cp_partners_order_simple` | |
| `BC_CASHPAD_ID`, `TARGET_01_CASHPAD_ID`, `TARGET_02_CASHPAD_ID`, `ORGANIZATION_ID` | tests multipush / sync-manager | |
| `SEQUENTIAL_ID` | `test_bov2kaban_2121` | optionnel, défaut `486` |
| `NOCAP_APIUSER_EMAIL`, `NOCAP_APIUSER_TOKEN` | `test_bov2kaban_2190` | optionnel — partenaire installé **sans** la capability testée, pour vérifier le rejet 403 |
| `APIUSER_EMAIL`, `APIUSER_TOKEN`, `INSTALLATION_ID`, `STAGING_BASE_URL` | `test_bov2kaban_2190`, `2192`, `2193` | les quatre sont **requises** par les tests customers ; `EnvironmentError` si l'une manque |
| `BOV2_STAGING_DB_URL` | `test_bov2kaban_2111` | accès DB privilégié ; le test skippe si absent |
| `NR_TARGET` | tests via `_target.py` / `_nr.py` | `staging` (défaut) ou `preprod` ; la prod n'existe pas dans la table |
| `NR_ALLOW_WRITES` | modules en écriture | `1` pour autoriser les tests qui écrivent (`writes_guard` hors staging, `tickets_guard` partout) |
| `BOV2_STAGING_LOGIN`, `BOV2_STAGING_PASSWORD` (`BOV2_PREPROD_*` en préprod) | `test_nr_*` qui lisent la liste des commandes d'un connecteur ou sa config | compte BO : `_nr.bo_token()` obtient le JWT du front par `POST /p/sso/public/1/sign-in`, comme les tests customers `2212`… |
| `BOV2_TOKEN` | idem, en repli | JWT copié du front (expire) ; guillemets de `localStorage` retirés. Sans aucun des deux, l'étape BO est **skippée** |
| `CASHPAD_ID` | `test_nr_*` qui lisent la caisse | hôte VPN `<CASHPAD_ID>.vpn.osilia.com:9091` ; défaut = `INSTALLATION_ID` (`cashpad-8007`). VPN requis |
| `PYTEST_VERBOSITY` | tests Postman | traces détaillées |

Une variable requise manquante lève `EnvironmentError` avec la liste des noms attendus. Les variables optionnelles font `pytest.skip` sur le step concerné.

---

## Règles de sûreté

Non négociables, elles s'appliquent à tout nouveau test :

- **Staging uniquement.** Le host cible est vérifié contre une allowlist explicite avant tout appel réseau. Jamais la prod : elle contient des données client réelles.
- **Lecture seule par défaut.** Les tests observent, ils ne mutent pas l'état des sites. Un test qui a besoin d'écrire doit être discuté avant d'être ajouté, et figurer dans l'inventaire « Les tests qui écrivent » ci-dessus, avec sa garde. Les tests portés qui **créent un ticket ou modifient une config** (`test_nr_*`, décidé le 2026-09-29) sont sous `tickets_guard()` : **skippés sur toutes les cibles, staging compris, sauf `NR_ALLOW_WRITES=1`** — un ticket poussé est fiscal et ne s'annule pas par l'API.
- **`add_credit_operation` et `delete_customer` sont des `GET` qui écrivent.** Le premier crédite des euros ou des points de fidélité sur un compte client ; le second supprime le client, et sur BOV2 il le fait quel que soit le verbe (`GET`, `POST`, `PUT` compris — vérifié 2026-09-04, BOV2KABAN-2193). **Filtrer sur le verbe HTTP ne protège de rien : c'est le nom de l'action qu'il faut contrôler.** `add_credit_operation` reste interdit depuis ce repo.
- **Aucun secret dans le code ni dans les fixtures.** Tout passe par `.env`.

---

## Conventions d'un nouveau test

Le modèle de référence est [tests/test_bov2kaban_2190_get_customers.py](tests/test_bov2kaban_2190_get_customers.py).

1. **En-tête** : docstring `Test de non-régression généré par /cp-test — ticket <JIRA-ID>`, titre du ticket, **date de la vérification**, endpoint exact appelé, schéma d'auth, et ce qui a été observé ce jour-là (volumétrie, valeurs clés).
2. **Config** : `load_dotenv()` puis une fonction `get_env()` avec sa liste `required` en minuscules ; `EnvironmentError` si une variable manque.
3. **Un appel réseau, partagé** : fixture `scope="module"` pour la réponse principale, afin que les steps ne rappellent pas l'API en boucle.
4. **Une fonction `test_NN_<step>()` par critère vérifié**, docstring référençant l'acceptance criterion (`AC1`, `AC2`, …).
5. **Golden ciblé** : `status_code` + uniquement les champs liés aux acceptance criteria. Pas de snapshot complet de la réponse — trop fragile.
6. **Messages d'assertion explicites** : le message doit dire ce qui a été reçu et ce qui était attendu, pour qu'un échec en CI se diagnostique sans relire le code.

### Figer une sémantique plutôt qu'un jeu de données

Un golden littéral casse à la première vente sur le site de test. Quand c'est possible, dériver l'attendu des données lues au même instant.

`test_bov2kaban_2190` illustre le procédé sur la borne de `updated_since_version` : plutôt que de coder en dur les versions observées, il relit la liste complète, en dérive quatre pivots (min, médiane, max, max+1000) et vérifie que chaque appel filtré renvoie exactement `[v for v in versions if v >= pivot]`. C'est la **borne inclusive** qui est verrouillée, et elle le reste quel que soit le contenu du site.

À l'inverse, une ancre verbatim reste justifiée sur une donnée **immuable** — `test_bov2kaban_2121` fige le contenu d'une archive fiscale clôturée, qui par construction ne bougera plus.
