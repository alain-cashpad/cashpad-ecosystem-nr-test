"""
Socle partagé des scripts d'outillage Partner API (dossier `scripts/`).

Contrairement à `tests/`, ces scripts ÉCRIVENT. Ce module centralise ce qui ne
doit pas diverger d'un script à l'autre : la table des cibles autorisées et le
chargement des identifiants.

La table `TARGETS` est le garde-fou anti-prod. Elle vit ICI et nulle part
ailleurs : dupliquée, elle finirait par gagner une entrée de production dans un
seul des fichiers. Aucun script d'écriture ne doit définir sa propre table.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PARTNERS_FILE = Path.home() / ".config" / "cashpad" / "partners.json"

# Cibles autorisées pour les scripts d'écriture.
#
# La PRODUCTION est volontairement ABSENTE, pas seulement déconseillée : elle
# n'est pas atteignable. `argparse` rejette toute valeur hors de ces clés, donc
# une faute de frappe ne peut pas envoyer un seed ou un crédit en prod.
# N'ajoutez pas d'entrée prod ici — un script d'écriture n'y a rien à faire.
TARGETS = {
    "bov1-preprod": "https://preprod.cashpad.net",
    "bov2-staging": "https://staging.cashpad.app",
    "bov2-preprod": "https://preprod.cashpad.app",
}


def load_credentials(partner: str) -> tuple[str, str]:
    """Couple (apiuser_email, apiuser_token).

    Priorité aux variables d'environnement APIUSER_EMAIL / APIUSER_TOKEN (mêmes
    noms que le .env des tests), sinon ~/.config/cashpad/partners.json.
    Le token n'est jamais affiché, ni en sortie ni dans les messages d'erreur.
    """
    email = os.getenv("APIUSER_EMAIL")
    token = os.getenv("APIUSER_TOKEN")
    if email and token:
        return email, token

    if not PARTNERS_FILE.exists():
        sys.exit(
            "Identifiants introuvables : ni APIUSER_EMAIL/APIUSER_TOKEN dans "
            f"l'environnement, ni {PARTNERS_FILE}"
        )

    partners = json.loads(PARTNERS_FILE.read_text()).get("partners", {})
    entry = partners.get(partner)
    if not entry:
        known = sorted(k for k in partners if not k.startswith("_"))
        sys.exit(f"Partenaire {partner!r} absent de {PARTNERS_FILE}. Connus : {known}")
    if not entry.get("email") or not entry.get("token"):
        sys.exit(f"Partenaire {partner!r} : email ou token vide dans {PARTNERS_FILE}")
    return entry["email"], entry["token"]


def add_target_arguments(parser, *, partner_default: str = "obypay") -> None:
    """Ajoute les arguments de ciblage communs à tous les scripts d'écriture."""
    parser.add_argument(
        "--target", required=True, choices=sorted(TARGETS),
        help="plateforme et environnement visés (la production n'est pas atteignable)",
    )
    parser.add_argument("--alias", required=True, help="installation_id du site (ex. cashpad-8007)")
    parser.add_argument(
        "--partner", default=partner_default,
        help=f"clé dans partners.json (défaut {partner_default})",
    )


def fetch_customers(client, base: str, alias: str, auth: dict) -> list[dict]:
    """Liste des clients du site. Lecture seule — sert à choisir les cibles d'une écriture."""
    url = f"{base}/api/customers/v1/{alias}/get_customers"
    response = client.get(url, params=auth)
    if response.status_code != 200:
        sys.exit(f"get_customers a répondu HTTP {response.status_code} : {response.text[:200]}")
    body = response.json()
    if not body.get("succeeded"):
        sys.exit(f"get_customers : {json.dumps(body, ensure_ascii=False)[:200]}")
    return body.get("customers", [])
