"""
Cible d'exécution des tests Partner API : `NR_TARGET=staging` (défaut) | `preprod`.

La table `TARGETS` est le garde-fou anti-prod de `tests/`. Elle vit ICI et nulle
part ailleurs, même principe que `scripts/_partner_api.py` : dupliquée dans
chaque fichier, elle finirait par gagner une entrée de production dans un seul.
La PRODUCTION est absente, pas seulement déconseillée — elle contient des
données client réelles.

Résolution :
    base       {NR_TARGET}_BASE_URL (ex. STAGING_BASE_URL), sinon TARGETS ;
               le host est vérifié contre TARGETS avant tout appel réseau
    alias      INSTALLATION_ID, sinon `cashpad-8007` (site de vérification)
    identif.   APIUSER_EMAIL / APIUSER_TOKEN, sinon ~/.config/cashpad/partners.json
               sous la clé NR_PARTNER (défaut `obypay`) — le couple partenaire
               est le même sur toutes les plateformes

Écritures : hors staging, un module qui ÉCRIT (create/update/delete/credit) est
skippé sauf `NR_ALLOW_WRITES=1`. Écrire en préprod reste un geste explicite,
jamais l'effet de bord d'un changement de cible.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import urlparse

import pytest

TARGETS = {
    "staging": "https://staging.cashpad.app",
    "preprod": "https://preprod.cashpad.app",
}

DEFAULT_ALIAS = "cashpad-8007"
DEFAULT_PARTNER = "obypay"
PARTNERS_FILE = Path.home() / ".config" / "cashpad" / "partners.json"


def target() -> str:
    name = os.getenv("NR_TARGET", "staging")
    if name not in TARGETS:
        raise EnvironmentError(f"NR_TARGET={name!r} inconnu — attendu : {sorted(TARGETS)}")
    return name


def base_url() -> str:
    name = target()
    base = (os.getenv(f"{name.upper()}_BASE_URL") or TARGETS[name]).rstrip("/")
    host = urlparse(base).hostname
    expected = urlparse(TARGETS[name]).hostname
    assert host == expected, f"Host hors allowlist pour {name} : {host!r} — refus d'exécuter"
    return base


def _credentials() -> tuple[str, str]:
    email, token = os.getenv("APIUSER_EMAIL"), os.getenv("APIUSER_TOKEN")
    if email and token:
        return email, token
    partner = os.getenv("NR_PARTNER", DEFAULT_PARTNER)
    if not PARTNERS_FILE.exists():
        raise EnvironmentError(f"Ni APIUSER_EMAIL/APIUSER_TOKEN, ni {PARTNERS_FILE}")
    entry = json.loads(PARTNERS_FILE.read_text()).get("partners", {}).get(partner) or {}
    if not entry.get("email") or not entry.get("token"):
        raise EnvironmentError(f"Partenaire {partner!r} absent ou incomplet dans {PARTNERS_FILE}")
    return entry["email"], entry["token"]


def partner_env() -> dict:
    """Base, alias et couple partenaire de la cible courante. Le token n'est jamais affiché."""
    email, token = _credentials()
    return {
        "base_url": base_url(),
        "installation_id": os.getenv("INSTALLATION_ID", DEFAULT_ALIAS),
        "apiuser_email": email,
        "apiuser_token": token,
    }


def writes_guard() -> pytest.MarkDecorator:
    """`pytestmark` des modules qui écrivent : skippés hors staging sans NR_ALLOW_WRITES=1."""
    blocked = target() != "staging" and os.getenv("NR_ALLOW_WRITES") != "1"
    return pytest.mark.skipif(
        blocked, reason=f"module en écriture sur {target()} — NR_ALLOW_WRITES=1 pour l'autoriser"
    )
