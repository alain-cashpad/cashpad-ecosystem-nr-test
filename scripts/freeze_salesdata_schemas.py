"""Fige la structure des réponses salesdata (tests/schemas/salesdata/<action>.json).

À relancer seulement quand un changement de structure est VOULU (champ ajouté et validé,
champ retiré d'un commun accord), puis relire le diff avant de committer :

    uv run --with httpx --with python-dotenv --with pytest python scripts/freeze_salesdata_schemas.py

Mesure sur les `FREEZE_COUNT` dernières archives (80) de la cible `NR_TARGET` (staging par
défaut), plus que les 12 du test : sur 12 archives, des champs réels mais rares manquaient
(catégorie des mouvements de caisse, contexte des remises, détail des paiements de session,
mesuré le 2026-10-02). Un champ est « requis » s'il est présent et non nul dans CHAQUE objet
parent rencontré.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tests"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

import _salesdata as S  # noqa: E402

FREEZE_COUNT = 80
S.SCOPE_COUNT = FREEZE_COUNT

for action in S.VERSIONS:
    shape = S.structure(action)
    (S.SCHEMAS_DIR / f"{action}.json").write_text(json.dumps(shape, indent=2, ensure_ascii=False, sort_keys=True) + "\n")
    optional = [p for p, e in shape.items() if not e["required"]]
    print(f"{action:17} {len(shape):4} champs, {len(optional)} optionnels")
