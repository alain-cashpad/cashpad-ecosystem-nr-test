# Salesdata : doc Notion vs réponses BOV2

Constat du 2026-10-02, staging, `cashpad-8007` (site 4652), sur les 80 dernières archives.
Doc : [Sales retrieval](https://cashpad.notion.site/Sales-retrieval-9519cd05bd714f0fa7dd1de375b399b9),
extraite dans `tests/schemas/salesdata/notion-doc.json`. Rejouer, hors ligne :

```bash
python3 scripts/compare_salesdata_doc.py
```

« Jamais servi » veut dire absent des 80 archives, pas forcément absent du code : un champ
lié à une fonction que le site n'utilise pas (distributeur de boissons, inventaire de caisse,
avoirs, fidélité externe) peut exister ailleurs. Les tests `test_nr_salesdata_*` ne vérifient
PAS la conformité à la doc : ils figent ce que BOV2 sert (`tests/schemas/salesdata/<action>.json`).

## Erreurs de structure de la doc (sûres)

| Action | Doc | BOV2 sert |
|---|---|---|
| `users_summary` | `data.sales` objet, `data.total_sales` liste | l'inverse : `sales` liste (une ligne par vendeur), `total_sales` objet |
| `products_summary` | `data.total_sales` liste, `data.sales` lignes par lieu / mode | `total_sales` objet ; **pas de `data.sales`** |
| `sales_summary` | `nb_products` entier | chaîne (`"1.0"`) |
| `cashcontainers` | `date.archive` | `data.archive` (coquille) |
| `cashcontainers` | `summary.method` / `summary.amount_total` | `summary[]` est une liste |
| `archive_content` | `drinkdispensersevents` puis `drinkdispenserevents` | les deux orthographes dans la même page ; aucune servie |

Versions : la doc annonce 2.10 (2.12 pour `users_summary` et `cashcontainers`) ; BOV2 sert
2.17, et 2.15 pour `archive_content`.

## Servis, non documentés

| Action | Champs |
|---|---|
| toutes | `context` (`site_id`, `server_name`, `administrative_code`) ; `timezone` (sauf `archive_content`) |
| `archive_content` | `receipts[].delivery_id` (BOV2KABAN-2223), `receipts[].customer.code` / `.name` (BOV2KABAN-2203) |
| `cashcontainers` | `sessions[].movements[].transactions[].amount` |

## Documentés, jamais servis sur 80 archives

| Action | Champs | Probable |
|---|---|---|
| `sales_summary` | `sales[].location`, `consumptionmode`, `period`, `receipt` ; idem sous `total_sales` | toujours `null` ou absents : ventilation non implémentée ? |
| `archive_content` | `cashmanager_snapshots`, `drinkdispenser*`, `receipts[].loyaltycard`, `receipts[].external_loyalty`, `payments[].lunch_voucher`, `consumptionmode.staff`, `discount.offered`, `discount.context.{loyalty, loss, reward_*}`, `items[].discount.*`, `addons[].product` | fonctions non utilisées sur le site, à vérifier dans le code |
| `cashcontainers` | `cashcontainer.user`, `cashcontainer.terminal`, `sessions[].inventory`, `main_inventory`, `payments[].creditnotes`, `transactions[].creditnote` | inventaires et avoirs non utilisés sur le site ? |
| `users_summary` | `inventories` | idem |

`external_loyalty` a son test (BOV2KABAN-2121) : jamais présent sur ces 80 archives, il ne
l'est que sur les tickets portant une fidélité externe.

## Perdu entre la caisse et BOV2

| Action | Champ | Constat |
|---|---|---|
| `archive_content` | `cashmovements[].transaction_id` | la caisse porte un `transactionId` sur 9 mouvements sur 9 (12 archives) ; BOV2 ne le sert jamais, alors que la doc le documente. Relevé par `test_nr_salesdata_archive_content`, non figé |
