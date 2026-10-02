# Anomalies relevées pendant l'écriture des tests

Relevées le 2026-10-02 sur le staging (`cashpad-8007`, site 4652), sauf mention. **Aucune
n'est figée par un test** : les tests restent verts tant que le comportement actuel ne bouge
pas, et chaque en-tête de test concerné les rappelle. Les écarts entre la doc Notion et les
réponses salesdata sont détaillés à part : [salesdata-doc-vs-bov2.md](salesdata-doc-vs-bov2.md).

## Partner API

| # | Où | Anomalie | Vu dans |
|---|---|---|---|
| 1 | `salesdata/archive_content` | Ne valide aucun paramètre : `sequential_id` absent, non entier ou inconnu → toujours 400 « internal communication error ». Les autres actions répondent `AnyRequired` / `NumberBase` | `test_nr_salesdata_archive_content` |
| 2 | `salesdata/*` (5 actions par archive) | Sur une archive inconnue, la stack trace du serveur est renvoyée au partenaire dans `data.backtrace`, y compris quand le message est correct (« Archive not found ») | `test_nr_salesdata_*` (`test_input_errors`) |
| 3 | `salesdata/archive_content` | `cashmovements[].transaction_id` jamais servi, alors que la caisse porte un `transactionId` sur chaque mouvement (9 sur 9) et que la doc le documente : donnée perdue | `test_nr_salesdata_archive_content` (`test_11`) |
| 4 | `salesdata/*` sans identifiants | 403 « The capability "sales" is not supported. Supported capabilities are: payment, stock, menu » : message trompeur pour une requête non authentifiée | sonde manuelle |
| 5 | `orders/precheck_order?check_stocks=true` | Sur un refus de stock (422 « No stock »), `checks.connection.succeeded` vaut aussi `false` alors que la caisse répond | `test_nr_partners_stock_state` |
| 6 | `payments/check?table=N` | Renvoie le PLUS ANCIEN ticket ouvert de la table, sans signaler qu'il y en a d'autres (comportement à confirmer comme voulu) | `test_nr_partners_check_live_receipt` (`test_05`) |

## Partners : configuration et notifications

| # | Où | Anomalie | Vu dans |
|---|---|---|---|
| 7 | cache des configs de connecteurs (`connector.utils.ts`) | Liste des connecteurs actifs gardée 30 min, configs 2 h, en mémoire **par pod**, vidées seulement par une édition BO/API : après un UPDATE SQL, des connecteurs désactivés (`flunch`, `drakkar`, `ilristo`) restaient notifiés. Avec plusieurs pods, une édition BO ne viderait que le pod qui la reçoit (non vérifié) | `test_nr_partners_receipt_event_notification` (`test_03`) |
| 8 | `new-archive-created` | L'archive 423, déjà connue, a été notifiée de nouveau lors d'une synchro où elle n'était pas nouvelle (voulu ou renvoi à chaque synchro : non tranché) | reconnaissance du 2026-10-02, 18:22 |
| 9 | connecteur `ubereats` (site 4652) | Actif, `receiptEventNotification: true`, mais aucun appel ni aucune ligne de log pour un `receiptCreated` (non implémenté pour ce connecteur ? non vérifié) | reconnaissance du 2026-10-02, 18:31 |
| 10 | config staging de `ilristo` et `obypay` | URL de **production** partenaire depuis le staging : `gatewayapi-prd.ilristorante.fr`, `management-api.obypay.com` | logs staging, base `partners` |

## Analytics (digested-data public)

| # | Où | Anomalie | Vu dans |
|---|---|---|---|
| 11 | `samePeriodLastYear` | Libellé `filters.time` « du 1 sept. 2025 au 29 sept. 2025 » pour une période qui finit le 30 ; les données, elles, sont celles du 1er au 30 (affichage ou borne exclusive : non tranché) | `test_nr_digested_data_public_api` (`test_04`) |
| 12 | jeton `digested-data.json` | Un jeton qui commence déjà par « Bearer » donne `400 AUTH_TOKEN_MISSING` (préfixe doublé) : piège d'outillage, contourné dans `_nr.digested_data()` | `_nr.py` |

## Pour mémoire, déjà expliquées

| # | Où | Constat | Statut |
|---|---|---|---|
| 13 | `worker-digested-data` | BOV2KABAN-2195 : `CustomerId` (`NullUuid`) sans `MarshalJSON` → `getLiveReceipt` sans `items`, paiement à table Sunday / Flunch cassé en prod le 2026-10-01 (08:30 → 10:14) | corrigé par BOV2KABAN-2344 ; gardé par `test_nr_partners_check_live_receipt` |
| 14 | rollback du 2026-10-01 | `digested-data` ramené sans `static-model` : 357 corps internal-rpc refusés (`paramsRaw`) | gardé par `test_nr_internal_rpc_contracts` |
| 15 | site 4652, `useMenuTaxDistribution: true` | Dans le code lu, seul `check` lit ce flag ; `products_summary` et l'analytics n'en dépendent pas | non vérifié avec le flag à `false` |
| 16 | caisse `cashpad-8007` | Son web proxy pointait sur la préprod : les tickets poussés depuis le staging notifiaient la préprod (site 1018). Repointée sur le staging le 2026-10-02 | configuration d'environnement |
