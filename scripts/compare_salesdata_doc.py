"""Compare la doc Notion « Sales retrieval » (tests/schemas/salesdata/notion-doc.json) aux
structures figées des réponses (tests/schemas/salesdata/<action>.json).

Hors ligne, aucune requête. Pour chaque action : champs documentés jamais servis, champs
servis non documentés, types qui divergent. Les modèles (`Receipt`, `Tax`…) sont développés
en chemins complets ; un modèle cité mais non défini dans la doc (`Period`,
`ProductCategory`) reste une feuille.

    python3 scripts/compare_salesdata_doc.py
"""

import json
from pathlib import Path

DIR = Path(__file__).resolve().parent.parent / "tests" / "schemas" / "salesdata"
doc = {k: v for k, v in json.loads((DIR / "notion-doc.json").read_text()).items() if not k.startswith("_")}
MODELS = {}
for page in doc.values():
    for name, rows in page["sections"].items():
        if name not in ("Return schema", "Modèle de données"):
            MODELS.setdefault(name, rows)
PRIM = {"boolean": {"bool"}, "string": {"str"}, "string uuid": {"str"}, "uuid": {"str"}, "datetime": {"str"},
        "date": {"str"}, "integer": {"int"}, "decimal": {"int", "float"}, "object": {"dict"}, "To be documented": None}


def expand(rows, prefix, out, depth=0):
    for name, typ in rows:
        path = f"{prefix}.{name}" if prefix else name
        array = typ.endswith("[]") or typ == "array[object]"
        base = typ[:-2] if typ.endswith("[]") else ("object" if typ == "array[object]" else typ)
        if array and not path.endswith("[]"):
            out[path] = {"list"}
            path += "[]"
        if base in PRIM:
            out[path] = PRIM[base]
        else:
            out[path] = {"dict"}
            if base in MODELS and depth < 6:
                expand(MODELS[base], path, out, depth + 1)
    return out


def roots(paths):
    return [p for p in paths if not any(p != q and p.startswith(q) for q in paths)]


for action, page in doc.items():
    sections = page["sections"]
    documented = expand(sections.get("Return schema") or sections.get("Modèle de données"), "", {})
    observed = json.loads((DIR / f"{action}.json").read_text())
    print(f"\n## {action} — doc v{page['version']}")
    print("  documentés, jamais servis :", roots(sorted(p for p in documented if p not in observed)))
    print("  servis, non documentés    :", roots(sorted(p for p in observed if p not in documented)))
    print("  type différent            :", sorted(
        f"{p} (doc {sorted(t)}, servi {[x for x in observed[p]['types'] if x != 'null']})"
        for p, t in documented.items() if t and p in observed
        and set(x for x in observed[p]["types"] if x != "null") - t))
