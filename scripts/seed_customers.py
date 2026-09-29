#!/usr/bin/env python3
"""
Seed de comptes clients via la Partner API Cashpad.

Crée N clients (50 par défaut) sur une installation donnée. Chaque exécution
produit des clients NEUFS : `externalId`, `code` et `email` portent un run-id
horodaté, donc relancer le script n'écrase ni ne dédoublonne rien.

    POST <host>/api/customers/v1/<alias>/create_customer
         ?apiuser_email=…&apiuser_token=…
    body = { firstName, lastName, company, street, zipCode, city, country,
             code, email, phone, externalId }

⚠️ Ce script ÉCRIT. Contrairement à la skill `bov2-partners-api` (lecture seule
par construction), il crée de la donnée. Trois garde-fous :

  * `--target` est OBLIGATOIRE et sans valeur par défaut — aucune cible ne peut
    être atteinte par omission ;
  * les cibles de PRODUCTION sont absentes de la table, pas seulement
    déconseillées : elles ne sont pas atteignables par ce script ;
  * `--dry-run` affiche le plan sans émettre un seul appel.

Identifiants : ~/.config/cashpad/partners.json (même fichier que la skill
`bov2-partners-api`), ou variables d'environnement APIUSER_EMAIL / APIUSER_TOKEN.
Aucun token n'est jamais affiché.

Exemples
--------
    # plan, aucun appel réseau
    python3 scripts/seed_customers.py --target bov1-preprod --alias cashpad-8007 --dry-run

    # 50 clients sur BOV1 preprod
    python3 scripts/seed_customers.py --target bov1-preprod --alias cashpad-8007

    # 10 clients, partenaire explicite, pause entre les appels
    python3 scripts/seed_customers.py --target bov1-preprod --alias cashpad-8007 \
        --count 10 --partner obypay --delay 0.2

Dépendances : httpx. Lancer avec uv :
    uv run --with httpx scripts/seed_customers.py --target … --alias …
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time

import httpx

from _partner_api import TARGETS, add_target_arguments, load_credentials

# Jeux de valeurs pour fabriquer des identités plausibles mais évidemment fictives.
FIRST_NAMES = [
    "Camille", "Lucas", "Inès", "Noah", "Jade", "Gabriel", "Louise", "Raphaël",
    "Emma", "Adam", "Alice", "Léo", "Chloé", "Hugo", "Manon", "Nathan",
    "Sarah", "Ethan", "Zoé", "Timéo",
]
LAST_NAMES = [
    "Martin", "Bernard", "Dubois", "Thomas", "Robert", "Richard", "Petit",
    "Durand", "Leroy", "Moreau", "Simon", "Laurent", "Lefebvre", "Michel",
    "Garcia", "David", "Bertrand", "Roux", "Vincent", "Fournier",
]
CITIES = [
    ("Paris", "75011"), ("Lyon", "69003"), ("Marseille", "13006"),
    ("Bordeaux", "33000"), ("Lille", "59000"), ("Nantes", "44000"),
    ("Toulouse", "31000"), ("Strasbourg", "67000"),
]
COMPANIES = ["Cashpad QA", "Seed Corp", "Test & Co", "Fixture SARL", ""]


def build_customer(run_id: str, index: int) -> dict:
    """Un client fictif, unique au run. `run_id` garantit qu'aucun run n'en recrée un identique."""
    first = random.choice(FIRST_NAMES)
    last = random.choice(LAST_NAMES)
    city, zip_code = random.choice(CITIES)
    tag = f"{run_id}-{index:03d}"
    return {
        "firstName": first,
        "lastName": f"{last} [SEED {tag}]",
        "company": random.choice(COMPANIES),
        "street": f"{random.randint(1, 120)} rue de la Recette",
        "zipCode": zip_code,
        "city": city,
        "country": "FR",
        "code": f"SEED{tag.replace('-', '')}",
        "email": f"seed-{tag}@example.invalid",
        "phone": f"+336{random.randint(10000000, 99999999)}",
        "externalId": f"seed-{tag}",
    }


def create_customer(client: httpx.Client, base: str, alias: str, auth: dict, payload: dict):
    """Renvoie (ok, détail). `ok` est False sur erreur HTTP comme sur succeeded=false."""
    url = f"{base}/api/customers/v1/{alias}/create_customer"
    try:
        response = client.post(url, params=auth, json=payload)
    except httpx.HTTPError as exc:
        return False, f"{type(exc).__name__}: {exc}"

    try:
        body = response.json()
    except ValueError:
        return False, f"HTTP {response.status_code} — réponse non-JSON : {response.text[:120]}"

    if response.status_code != 200 or not body.get("succeeded"):
        return False, f"HTTP {response.status_code} — {json.dumps(body, ensure_ascii=False)[:200]}"
    return True, body.get("customerId", "<pas de customerId dans la réponse>")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Crée N comptes clients de test via la Partner API Cashpad.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    add_target_arguments(parser)
    parser.add_argument("--count", type=int, default=50, help="nombre de clients à créer (défaut 50)")
    parser.add_argument("--delay", type=float, default=0.0, help="pause en secondes entre deux appels")
    parser.add_argument("--dry-run", action="store_true", help="affiche le plan, n'émet aucun appel")
    parser.add_argument("--seed", type=int, help="graine aléatoire, pour un jeu reproductible")
    args = parser.parse_args()

    if args.count < 1:
        sys.exit("--count doit être >= 1")
    if args.seed is not None:
        random.seed(args.seed)

    base = TARGETS[args.target]
    run_id = time.strftime("%Y%m%d-%H%M%S")
    email, token = load_credentials(args.partner)

    print(f"Cible      : {args.target} ({base})")
    print(f"Alias      : {args.alias}")
    print(f"Partenaire : {args.partner} ({email})")
    print(f"Run id     : {run_id}   → externalId 'seed-{run_id}-NNN'")
    print(f"À créer    : {args.count} client(s)\n")

    payloads = [build_customer(run_id, i + 1) for i in range(args.count)]

    if args.dry_run:
        print("DRY-RUN — aucun appel émis. Trois premiers payloads :\n")
        for payload in payloads[:3]:
            print("  " + json.dumps(payload, ensure_ascii=False))
        if args.count > 3:
            print(f"  … et {args.count - 3} autre(s)")
        return 0

    auth = {"apiuser_email": email, "apiuser_token": token}
    created, failed = [], []

    with httpx.Client(timeout=60.0) as client:
        for i, payload in enumerate(payloads, start=1):
            ok, detail = create_customer(client, base, args.alias, auth, payload)
            if ok:
                created.append(detail)
                print(f"  [{i:>3}/{args.count}] OK   {detail}  {payload['externalId']}")
            else:
                failed.append((payload["externalId"], detail))
                print(f"  [{i:>3}/{args.count}] ÉCHEC {payload['externalId']} — {detail}")
            if args.delay and i < args.count:
                time.sleep(args.delay)

    print(f"\n{len(created)} créé(s), {len(failed)} en échec.")
    if failed:
        print("\nÉchecs :")
        for external_id, detail in failed[:10]:
            print(f"  {external_id} — {detail}")
        if len(failed) > 10:
            print(f"  … et {len(failed) - 10} autre(s)")
        return 1

    print(f"\nRetrouver ce lot : externalId commençant par 'seed-{run_id}-'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
