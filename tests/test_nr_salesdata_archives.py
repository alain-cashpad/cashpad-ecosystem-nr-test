from __future__ import annotations

"""
Test de non-régression — salesdata `archives` (liste des archives, une par clôture)

    GET {base}/api/salesdata/v2/{INSTALLATION_ID}/archives[?start_sequential_id=N]
    GET http://<CASHPAD_ID>.vpn.osilia.com:9091/reports/get_archives?updated_since_version=0   (oracle)

LECTURE SEULE.

| Test | Règle |
|---|---|
| test_01 | enveloppe v2.17, `timezone` ; chaque archive a `id`, `sequential_id` entier unique, `range_begin_date` ≤ `range_end_date` (ISO UTC) |
| test_02 | `start_sequential_id` est une borne INCLUSIVE : la page commence à N et = la liste complète filtrée |
| test_03 | `start_sequential_id` au-delà de la dernière archive → 200 et liste vide (pas d'erreur) |
| test_04 | les dernières archives de la caisse sont dans le BO, même `id` et mêmes dates (VPN) |
| test_05 | mauvais token → 404 |

Aucun filtre de date : `archives` n'accepte que `start_sequential_id` (skill
bov2-partners-api). Dates de la caisse en UTC (`20261001T122219`), pas en heure locale.
Observé VERT le 2026-10-02 sur le staging (424 archives, 420 → 423 pour
start_sequential_id=420).
"""

import re

from dotenv import load_dotenv

load_dotenv()

from _salesdata import SCOPE_COUNT, archives, assert_wrong_token_refused, call, data, device, pos_utc

ISO_UTC = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")


def test_01_archive_list_shape():
    status, payload = call("archives")
    assert status == 200 and payload.get("timezone"), f"archives : {status} {str(payload)[:200]}"
    rows = archives()
    seqs = [a["sequential_id"] for a in rows]
    assert len(seqs) == len(set(seqs)), "sequential_id en double"
    bad = [a for a in rows if not (a.get("id") and isinstance(a["sequential_id"], int)
                                   and ISO_UTC.match(a.get("range_begin_date") or "")
                                   and ISO_UTC.match(a.get("range_end_date") or "")
                                   and a["range_begin_date"] <= a["range_end_date"])]
    assert not bad, f"{len(bad)} archive(s) mal formée(s), ex. {bad[0]}"


def test_02_start_sequential_id_is_inclusive():
    start = archives()[-4]["sequential_id"]
    page = data("archives", start_sequential_id=start)
    expected = [a["sequential_id"] for a in archives() if a["sequential_id"] >= start]
    assert sorted(a["sequential_id"] for a in page) == expected, (
        f"start_sequential_id={start} : {[a['sequential_id'] for a in page]}, attendu {expected}")


def test_03_start_beyond_the_last_archive_is_empty():
    beyond = archives()[-1]["sequential_id"] + 1000
    assert data("archives", start_sequential_id=beyond) == [], f"start_sequential_id={beyond} : liste non vide"


def test_04_latest_pos_archives_match():
    pos = sorted(device("reports/get_archives?updated_since_version=0").get("archives") or [],
                 key=lambda a: a["sequentialId"])[-SCOPE_COUNT:]
    bo = {a["sequential_id"]: a for a in archives()}
    diffs = []
    for a in pos:
        b = bo.get(a["sequentialId"])
        if not b:
            diffs.append(f"{a['sequentialId']} : sur la caisse, absente du BO")
        elif b["id"].lower() != a["id"].lower():
            diffs.append(f"{a['sequentialId']} : id caisse {a['id']} ≠ BO {b['id']}")
        elif (b["range_begin_date"], b["range_end_date"]) != (pos_utc(a["rangeBeginDate"]), pos_utc(a["rangeEndDate"])):
            diffs.append(f"{a['sequentialId']} : dates caisse {pos_utc(a['rangeBeginDate'])}→{pos_utc(a['rangeEndDate'])} "
                         f"≠ BO {b['range_begin_date']}→{b['range_end_date']}")
    assert not diffs, "\n".join(diffs)


def test_05_wrong_token_is_refused():
    assert_wrong_token_refused("archives")
