from __future__ import annotations

"""
Test de non-régression — salesdata `archive_content` (contenu complet d'une archive)

    GET {base}/api/salesdata/v2/{INSTALLATION_ID}/archive_content?sequential_id=<seq>
    GET http://<CASHPAD_ID>.vpn.osilia.com:9091/reports/get_archive_content?id=<seq>   (oracle)

LECTURE SEULE. Périmètre : les 12 dernières archives du BO. Les champs propres à un
ticket (loyalty, customer, delivery_id) ont leurs tests : 2121, 2203, 2223.

| Test | Règle |
|---|---|
| test_00 | structure : aucun champ figé (`schemas/salesdata/archive_content.json`) ne disparaît ni ne change de type ; un champ nouveau est seulement affiché |
| test_01 | enveloppe v2.15 (une version derrière les autres actions) ; `id` et dates = ceux d'`archives` |
| test_02 | `total` (TTC, nb_receipts, nb_cancelled_receipts) = somme des tickets |
| test_03 | chaque ticket non annulé : Σ paiements = `total_with_taxes` |
| test_04 | `payments` de l'archive (par moyen, nb_operations) = paiements des tickets non annulés |
| test_05 | tickets du BO = tickets de la caisse : mêmes id, sequential_id, montant, annulation (VPN) |
| test_06 | erreurs d'entrée : sans sequential_id, non entier, archive inconnue → 400 (jamais 500) |
| test_07 | mauvais token → 404 |
| test_08 | caisse ↔ BO, CHAQUE ticket, 16 champs (`RECEIPT_FIELDS`) : dates, propriétaire, lieu, mode, client, couverts, table, annulation et motif, notes, delivery_id, montant… (VPN) |
| test_09 | caisse ↔ BO, CHAQUE ligne : produit, quantité, prix unitaire, menu, addons, et `final_price` RECALCULÉ depuis la caisse (VPN) |
| test_10 | caisse ↔ BO, paiements de chaque ticket : moyen, montant, date, utilisateur (VPN) |
| test_11 | caisse ↔ BO, mouvements de caisse : moyen, montant, date, client, description (VPN) |
| test_12 | caisse ↔ BO, TVA de l'archive par taux (HT et TVA) et utilisateur de clôture (VPN) |

## Caisse ↔ BO : conventions (mesurées le 2026-10-02, 12 archives, 78 tickets, 212 lignes)

| Champ BO | Caisse | Conversion |
|---|---|---|
| dates | `20260929T194657` | UTC, → ISO `…Z` |
| `owner`, `location`, `consumptionmode`, `customer`, `user` (objets) | identifiant seul | on compare l'`id` |
| `table` | `locationNumber` | BO = caisse / 1000 (millièmes : la table 10.1 vaut 10100) |
| `notes` | `note` (une chaîne) | `[note]` |
| `items[].addons[].quantity` | `addons[].quantity` | BO = caisse × 1000 |
| `items[].final_price` | — | (prix + addons payants) × quantité × (1 − `discountPercentage` / 1000), arrondi au centime ; SANS la remise du ticket. La caisse a `valueInclTaxes`, d'une autre nature (remise du ticket déduite ; valeur hors menu pour un composant) : non comparé |
| TVA de l'archive | `taxes` (chaîne JSON) : `brut` = HT, `taxes` = TVA × 10⁶ | arrondis à l'entier, en millièmes |

`discountPercentage` est en DIXIÈMES de % (10 = 1 %) : 212 lignes sur 212 avec cette
lecture, 210 avec une lecture en %.

🔴 Écart relevé le 2026-10-02, NON figé : les mouvements de caisse portent un
`transactionId` sur la caisse (9 sur 9), que BOV2 ne sert pas — alors que la doc Notion
documente `cashmovements[].transaction_id`. test_11 ne le compare pas.

⚠️ Relevé le 2026-10-02, non figé (le test ne fige que le 400) : archive_content ne valide
AUCUN paramètre — absent, non entier ou inconnu, tout répond 400 « internal communication
error », avec la stack trace du serveur dans `data.backtrace` ; les autres actions
répondent `AnyRequired` / `NumberBase`.
Observé VERT le 2026-10-02 sur le staging (412 → 423).
"""

import collections
import json
from decimal import ROUND_HALF_UP, Decimal

import pytest
from dotenv import load_dotenv

load_dotenv()

from _salesdata import assert_fields, assert_input_errors, assert_wrong_token_refused, by_seq, data, device, pos_utc, scope


@pytest.fixture(scope="module")
def contents() -> dict[int, dict]:
    return {seq: data("archive_content", sequential_id=seq) for seq in scope()}


def kept(content: dict) -> list[dict]:
    return [r for r in content.get("receipts") or [] if not r.get("cancelled")]


def test_00_fields():
    assert_fields("archive_content")


def test_01_archive_matches_the_list(contents):
    listed = by_seq()
    diffs = [f"{seq} : {c.get('id')} {c.get('range_begin_date')}→{c.get('range_end_date')}"
             for seq, c in contents.items()
             if (c.get("sequential_id"), c.get("id"), c.get("range_begin_date"), c.get("range_end_date"))
             != (seq, listed[seq]["id"], listed[seq]["range_begin_date"], listed[seq]["range_end_date"])]
    assert not diffs, "archive_content ≠ archives :\n" + "\n".join(diffs)


def test_02_total_is_the_sum_of_receipts(contents):
    diffs = []
    for seq, c in contents.items():
        total = c.get("total") or {}
        cancelled = sum(1 for r in c.get("receipts") or [] if r.get("cancelled"))
        got = (total.get("total_with_taxes"), total.get("nb_receipts"), total.get("nb_cancelled_receipts"))
        expected = (sum(r["total_with_taxes"] for r in kept(c)), len(kept(c)), cancelled)
        if got != expected:
            diffs.append(f"{seq} : total (TTC, tickets, annulés) {got} ≠ Σ tickets {expected}")
    assert not diffs, "\n".join(diffs)


def test_03_each_receipt_is_fully_paid(contents):
    diffs = [f"{seq} ticket {r['sequential_id']} : Σ paiements {sum(p['amount'] for p in r.get('payments') or [])} "
             f"≠ total {r['total_with_taxes']}"
             for seq, c in contents.items() for r in kept(c)
             if sum(p["amount"] for p in r.get("payments") or []) != r["total_with_taxes"]]
    assert not diffs, "\n".join(diffs[:10])


def test_04_archive_payments_are_the_receipt_payments(contents):
    diffs = []
    for seq, c in contents.items():
        expected = collections.defaultdict(lambda: [0, 0])
        for r in kept(c):
            for p in r.get("payments") or []:
                line = expected[p["paymentmethod"]["id"].upper()]
                line[0] += p["amount"]
                line[1] += 1
        got = {p["paymentmethod"]["id"].upper(): [p["amount"], p["nb_operations"]] for p in c.get("payments") or []}
        if got != dict(expected):
            diffs.append(f"{seq} : payments {got} ≠ paiements des tickets {dict(expected)}")
    assert not diffs, "\n".join(diffs)


def test_05_receipts_match_the_pos(contents):
    diffs = []
    for seq, c in contents.items():
        pos = (device(f"reports/get_archive_content?id={seq}").get("archive") or {}).get("receipts") or []
        bo = {r["id"].lower(): (r["sequential_id"], r["total_with_taxes"], bool(r.get("cancelled")))
              for r in c.get("receipts") or []}
        device_rows = {r["id"].lower(): (r["sequentialId"], r["amountTotal"], bool(r.get("cancelled"))) for r in pos}
        if bo != device_rows:
            only = sorted(set(bo) ^ set(device_rows))[:3]
            changed = [k for k in set(bo) & set(device_rows) if bo[k] != device_rows[k]][:3]
            diffs.append(f"{seq} : {len(bo)} tickets BO / {len(device_rows)} caisse, d'un seul côté {only}, "
                         f"différents {[(k, bo[k], device_rows[k]) for k in changed]}")
    assert not diffs, "\n".join(diffs)


def test_06_input_errors():
    assert_input_errors("archive_content", unknown_message=None, validates_input=False)


def test_07_wrong_token_is_refused():
    assert_wrong_token_refused("archive_content", sequential_id=scope()[-1])


# ── Caisse ↔ BO, champ par champ (conventions : cf. en-tête) ──

def low(value):
    return value.lower() if isinstance(value, str) else value


def ref(obj):
    """Identifiant d'un objet BO (`{id, name, external_id}`), ou None."""
    return low(obj.get("id")) if isinstance(obj, dict) else low(obj)


RECEIPT_FIELDS = {  # champ BO : (lecture caisse, lecture BO)
    "sequential_id": (lambda p: p["sequentialId"], lambda b: b["sequential_id"]),
    "period_id": (lambda p: p.get("periodId"), lambda b: b.get("period_id")),
    "date_created": (lambda p: pos_utc(p.get("dateCreated")), lambda b: b.get("date_created")),
    "date_closed": (lambda p: pos_utc(p.get("dateClosed")), lambda b: b.get("date_closed")),
    "date_pickup": (lambda p: pos_utc(p.get("datePickup")), lambda b: b.get("date_pickup")),
    "owner": (lambda p: low(p.get("owner")), lambda b: ref(b.get("owner"))),
    "location": (lambda p: low(p.get("location")), lambda b: ref(b.get("location"))),
    "consumptionmode": (lambda p: low(p.get("consumptionMode")), lambda b: ref(b.get("consumptionmode"))),
    "customer": (lambda p: low(p.get("customer")), lambda b: ref(b.get("customer"))),
    "nb_seats": (lambda p: p.get("nbSeats") or 0, lambda b: b.get("nb_seats")),
    "table": (lambda p: (p.get("locationNumber") or 0) / 1000, lambda b: b.get("table")),
    "cancelled": (lambda p: bool(p.get("cancelled")), lambda b: bool(b.get("cancelled"))),
    "cancellation_reason": (lambda p: p.get("cancellationReason"), lambda b: b.get("cancellation_reason")),
    "notes": (lambda p: [p["note"]] if p.get("note") else [], lambda b: [n for n in b.get("notes") or [] if n]),
    "delivery_id": (lambda p: p.get("deliveryId") or None, lambda b: b.get("delivery_id")),
    "total_with_taxes": (lambda p: p.get("amountTotal"), lambda b: b.get("total_with_taxes")),
}


def final_price(item: dict) -> int:
    """`final_price` BO recalculé depuis une ligne de la caisse (cf. en-tête)."""
    addons = sum((a.get("priceInclTaxes") or 0) * (a.get("quantity") or 0) for a in item.get("addons") or [])
    raw = Decimal(item["priceInclTaxes"] + addons) * item["quantity"] / 1000 \
        * (1 - Decimal(item.get("discountPercentage") or 0) / 1000)
    return int((raw / 10).quantize(Decimal(1), rounding=ROUND_HALF_UP) * 10)


ITEM_FIELDS = {
    "product": (lambda p: low(p.get("product")), lambda b: ref(b.get("product"))),
    "quantity": (lambda p: p.get("quantity"), lambda b: b.get("quantity")),
    "unit_price": (lambda p: p.get("priceInclTaxes"), lambda b: b.get("unit_price")),
    "final_price": (final_price, lambda b: b.get("final_price")),
    "menu": (lambda p: low(p.get("menu")), lambda b: low(b.get("menu"))),
    "addons": (lambda p: sorted((low(a["productAddon"]), (a.get("quantity") or 0) * 1000) for a in p.get("addons") or []),
               lambda b: sorted((ref(a.get("addon")), a.get("quantity")) for a in b.get("addons") or [])),
}


@pytest.fixture(scope="module")
def pairs(contents) -> list[tuple[int, dict, dict]]:
    """(archive, archive caisse, archive BO) ; skip sans VPN."""
    return [(seq, device(f"reports/get_archive_content?id={seq}").get("archive") or {}, c) for seq, c in contents.items()]


def receipt_pairs(pairs):
    for seq, pos, bo in pairs:
        by_id = {r["id"].lower(): r for r in bo.get("receipts") or []}
        for p in pos.get("receipts") or []:
            b = by_id.get(p["id"].lower())
            if b:  # les tickets manquants sont signalés par test_05
                yield seq, p, b


def compare(fields: dict, pos: dict, bo: dict, where: str, out: list):
    for name, (read_pos, read_bo) in fields.items():
        if read_pos(pos) != read_bo(bo):
            out.append(f"{where} {name} : caisse {read_pos(pos)!r} ≠ BO {read_bo(bo)!r}")


def test_08_receipt_fields_match_the_pos(pairs):
    diffs = []
    for seq, p, b in receipt_pairs(pairs):
        compare(RECEIPT_FIELDS, p, b, f"{seq}/{p['sequentialId']}", diffs)
    assert not diffs, f"{len(diffs)} écart(s) :\n" + "\n".join(diffs[:15])


def test_09_item_fields_match_the_pos(pairs):
    diffs, lines = [], 0
    for seq, p, b in receipt_pairs(pairs):
        by_id = {i["id"].lower(): i for i in b.get("items") or []}
        missing = [i["id"] for i in p.get("items") or [] if i["id"].lower() not in by_id]
        if missing or len(by_id) != len(p.get("items") or []):
            diffs.append(f"{seq}/{p['sequentialId']} : lignes caisse {len(p.get('items') or [])} / BO {len(by_id)}, absentes {missing[:3]}")
        for item in p.get("items") or []:
            if item["id"].lower() in by_id:
                lines += 1
                compare(ITEM_FIELDS, item, by_id[item["id"].lower()], f"{seq}/{p['sequentialId']}/{item['id'][:8]}", diffs)
    assert lines, "aucune ligne comparée"
    assert not diffs, f"{len(diffs)} écart(s) sur {lines} lignes :\n" + "\n".join(diffs[:15])


def test_10_payments_match_the_pos(pairs):
    diffs = []
    for seq, p, b in receipt_pairs(pairs):
        pos = sorted((low(x["method"]), x["amount"], pos_utc(x["date"]), low(x["user"])) for x in p.get("payments") or [])
        bo = sorted((ref(x["paymentmethod"]), x["amount"], x["date"], ref(x["user"])) for x in b.get("payments") or [])
        if pos != bo:
            diffs.append(f"{seq}/{p['sequentialId']} : caisse {pos} ≠ BO {bo}")
    assert not diffs, "\n".join(diffs[:10])


def test_11_cash_movements_match_the_pos(pairs):
    diffs = []
    for seq, pos, bo in pairs:
        device_rows = sorted((low(m["method"]), m["amount"], pos_utc(m["date"]), low(m.get("customer")), m.get("description") or "")
                             for m in pos.get("cashMovements") or [])
        bo_rows = sorted((ref(m["paymentmethod"]), m["amount"], m["date"], ref(m.get("customer")), m.get("description") or "")
                         for m in bo.get("cashmovements") or [])
        if device_rows != bo_rows:
            diffs.append(f"{seq} : caisse {device_rows} ≠ BO {bo_rows}")
    assert not diffs, "\n".join(diffs)


def test_12_archive_vat_and_user_match_the_pos(pairs):
    diffs = []
    for seq, pos, bo in pairs:
        raw = pos.get("taxes")
        taxes = json.loads(raw) if isinstance(raw, str) else raw or []
        device_vat = {t["rate"]: (round(t["brut"]), round(t["taxes"] / 1000)) for t in taxes}
        bo_vat = {t["rate"]: (t["total_without_taxes"], t["amount"]) for t in (bo.get("total") or {}).get("taxes") or []}
        if device_vat != bo_vat:
            diffs.append(f"{seq} : TVA (HT, TVA) par taux caisse {device_vat} ≠ BO {bo_vat}")
        if low(pos.get("user")) != ref(bo.get("user")):
            diffs.append(f"{seq} : utilisateur caisse {pos.get('user')} ≠ BO {ref(bo.get('user'))}")
    assert not diffs, "\n".join(diffs)
