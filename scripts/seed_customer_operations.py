#!/usr/bin/env python3
"""
Seed d'opérations de crédit sur des comptes clients, via la Partner API Cashpad.

Crédite de l'argent ou des points de fidélité sur les clients d'une installation,
pour disposer d'un historique d'opérations à interroger. Pendant naturel de
`seed_customers.py` : ce dernier crée les comptes, celui-ci les alimente.

    GET <host>/api/customers/v1/<alias>/add_credit_operation
        ?apiuser_email=…&apiuser_token=…
        &id=<uuid> | &external_id=<ref>
        &type=money|points&amount=<×1000>&transaction_id=<ref>

⚠️⚠️ CET ENDPOINT EST UN « GET » QUI ÉCRIT — il crédite de la valeur réelle sur
un compte client. Filtrer sur le verbe HTTP ne protège de RIEN. D'où :

  * `--target` obligatoire, sans défaut ; les cibles de PRODUCTION sont absentes
    de la table (cf. `_partner_api.TARGETS`) et donc inatteignables ;
  * par défaut, seuls les clients issus d'un seed (`externalId` commençant par
    `seed-`) sont crédités — viser tout le site demande `--all`, explicitement ;
  * `--dry-run` affiche le plan sans émettre un seul appel.

⚠️ `transaction_id` N'EST PAS IDEMPOTENT (vérifié sur BOV1 preprod le
2026-09-03) : rejouer le même identifiant crée une SECONDE opération et
recrédite le compte. Il n'existe donc aucun filet contre un double envoi — ne
relancez pas « pour voir » un run interrompu sans contrôler les soldes.

Échelles (doc « Customers management », vérifiées en réel) :
  * `amount` est transmis ×1000 : 5000 = 5 € ou 5 points. Ce script prend les
    montants en unités LISIBLES (euros / points) et fait la conversion.
  * en relecture, `balance` et `account` restent en ×1000, alors que
    `loyaltyPoints` est ramené en unités. Deux échelles dans le même objet.

Exemples
--------
    # plan, aucun appel réseau
    uv run --with httpx scripts/seed_customer_operations.py \
        --target bov1-preprod --alias cashpad-8007 --dry-run

    # 3 opérations sur chaque client issu d'un seed
    uv run --with httpx scripts/seed_customer_operations.py \
        --target bov1-preprod --alias cashpad-8007

    # que de la fidélité, 5 à 50 points, sur un client précis
    uv run --with httpx scripts/seed_customer_operations.py \
        --target bov1-preprod --alias cashpad-8007 \
        --customer-id ad03dc84-a794-11f1-9005-0242ac110003 \
        --type points --amount-min 5 --amount-max 50
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time

import httpx

from _partner_api import TARGETS, add_target_arguments, fetch_customers, load_credentials

# Facteur de transmission des montants (doc + vérification réelle).
AMOUNT_SCALE = 1000


def select_customers(customers: list[dict], args) -> list[dict]:
    """Cibles de l'opération, selon les filtres. Par défaut : les clients issus d'un seed."""
    if args.customer_id:
        wanted = set(args.customer_id)
        selected = [c for c in customers if c["id"] in wanted]
        missing = wanted - {c["id"] for c in selected}
        if missing:
            sys.exit(f"Client(s) introuvable(s) sur ce site : {sorted(missing)}")
        return selected

    if args.all:
        return [c for c in customers if not c["deleted"]]

    prefix = args.external_id_prefix
    return [
        c for c in customers
        if not c["deleted"] and (c.get("externalId") or "").startswith(prefix)
    ]


def build_operations(selected: list[dict], run_id: str, args) -> list[dict]:
    """Une opération = un client, un type, un montant en unités lisibles, un transaction_id unique."""
    operations = []
    counter = 0
    for customer in selected:
        for _ in range(args.per_customer):
            counter += 1
            op_type = args.type if args.type != "mixed" else random.choice(("money", "points"))
            if op_type == "points":
                amount = random.randint(int(args.amount_min), max(int(args.amount_min), int(args.amount_max)))
            else:
                amount = round(random.uniform(args.amount_min, args.amount_max), 2)
            operations.append({
                "customer": customer,
                "type": op_type,
                "amount": amount,                                  # unités lisibles (€ ou points)
                "raw_amount": int(round(amount * AMOUNT_SCALE)),    # ce qui part sur le fil
                "transaction_id": f"seedop-{run_id}-{counter:04d}",
            })
    return operations


def send_operation(client: httpx.Client, base: str, alias: str, auth: dict, op: dict):
    """Renvoie (ok, détail). `ok` est False sur erreur HTTP comme sur succeeded=false."""
    url = f"{base}/api/customers/v1/{alias}/add_credit_operation"
    params = {
        **auth,
        "id": op["customer"]["id"],
        "type": op["type"],
        "amount": op["raw_amount"],
        "transaction_id": op["transaction_id"],
    }
    try:
        response = client.get(url, params=params)
    except httpx.HTTPError as exc:
        return False, f"{type(exc).__name__}: {exc}"

    try:
        body = response.json()
    except ValueError:
        return False, f"HTTP {response.status_code} — réponse non-JSON : {response.text[:120]}"

    if response.status_code != 200 or not body.get("succeeded"):
        return False, f"HTTP {response.status_code} — {json.dumps(body, ensure_ascii=False)[:200]}"
    return True, body


def unit(op_type: str) -> str:
    return "pts" if op_type == "points" else "EUR"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Crédite des opérations de test sur des comptes clients (Partner API).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    add_target_arguments(parser)
    parser.add_argument("--per-customer", type=int, default=3,
                        help="opérations par client (défaut 3)")
    parser.add_argument("--type", choices=("money", "points", "mixed"), default="mixed",
                        help="type d'opération (défaut mixed)")
    parser.add_argument("--amount-min", type=float, default=1.0,
                        help="montant minimum, en euros ou en points (défaut 1)")
    parser.add_argument("--amount-max", type=float, default=20.0,
                        help="montant maximum, en euros ou en points (défaut 20)")
    parser.add_argument("--external-id-prefix", default="seed-",
                        help="ne créditer que les clients dont l'externalId commence par ce préfixe "
                             "(défaut 'seed-', soit les clients produits par seed_customers.py)")
    parser.add_argument("--customer-id", action="append", metavar="UUID",
                        help="cibler un client précis par son id (répétable) ; ignore le préfixe")
    parser.add_argument("--all", action="store_true",
                        help="créditer TOUS les clients non supprimés du site, seed ou non")
    parser.add_argument("--delay", type=float, default=0.0,
                        help="pause en secondes entre deux appels")
    parser.add_argument("--dry-run", action="store_true",
                        help="affiche le plan, n'émet aucun appel")
    parser.add_argument("--seed", type=int, help="graine aléatoire, pour un jeu reproductible")
    args = parser.parse_args()

    if args.per_customer < 1:
        sys.exit("--per-customer doit être >= 1")
    if args.amount_min <= 0 or args.amount_max < args.amount_min:
        sys.exit("Montants invalides : attendu 0 < --amount-min <= --amount-max")
    if args.seed is not None:
        random.seed(args.seed)

    base = TARGETS[args.target]
    run_id = time.strftime("%Y%m%d-%H%M%S")
    email, token = load_credentials(args.partner)
    auth = {"apiuser_email": email, "apiuser_token": token}

    print(f"Cible      : {args.target} ({base})")
    print(f"Alias      : {args.alias}")
    print(f"Partenaire : {args.partner} ({email})")
    print(f"Run id     : {run_id}   → transaction_id 'seedop-{run_id}-NNNN'")

    with httpx.Client(timeout=60.0) as client:
        customers = fetch_customers(client, base, args.alias, auth)
        selected = select_customers(customers, args)

        scope = (
            "clients désignés" if args.customer_id
            else "TOUS les clients non supprimés" if args.all
            else f"clients dont l'externalId commence par {args.external_id_prefix!r}"
        )
        print(f"Périmètre  : {scope} → {len(selected)} client(s) sur {len(customers)}")

        if not selected:
            print("\nAucun client ne correspond. Lancer seed_customers.py d'abord, "
                  "ou élargir avec --external-id-prefix / --customer-id / --all.")
            return 1

        operations = build_operations(selected, run_id, args)
        print(f"À créer    : {len(operations)} opération(s) "
              f"({args.per_customer} par client, type {args.type})\n")

        if args.dry_run:
            print("DRY-RUN — aucun appel émis. Cinq premières opérations :\n")
            for op in operations[:5]:
                print(f"  {op['customer']['id']}  {op['type']:<6} "
                      f"{op['amount']:>8} {unit(op['type']):<3} → amount={op['raw_amount']:<8} "
                      f"tx={op['transaction_id']}")
            if len(operations) > 5:
                print(f"  … et {len(operations) - 5} autre(s)")
            return 0

        done, failed = [], []
        for i, op in enumerate(operations, start=1):
            ok, detail = send_operation(client, base, args.alias, auth, op)
            if ok:
                done.append(op)
                print(f"  [{i:>4}/{len(operations)}] OK    {op['type']:<6} "
                      f"{op['amount']:>8} {unit(op['type']):<3}  "
                      f"balance={detail.get('balance')}  {op['customer']['id']}")
            else:
                failed.append((op, detail))
                print(f"  [{i:>4}/{len(operations)}] ÉCHEC {op['type']:<6} "
                      f"{op['customer']['id']} — {detail}")
            if args.delay and i < len(operations):
                time.sleep(args.delay)

    total_money = sum(op["amount"] for op in done if op["type"] == "money")
    total_points = sum(op["amount"] for op in done if op["type"] == "points")
    print(f"\n{len(done)} opération(s) créée(s), {len(failed)} en échec.")
    print(f"Crédité : {total_money:.2f} EUR et {total_points} point(s) "
          f"sur {len({op['customer']['id'] for op in done})} client(s).")

    if failed:
        print("\nÉchecs :")
        for op, detail in failed[:10]:
            print(f"  {op['transaction_id']} — {detail}")
        if len(failed) > 10:
            print(f"  … et {len(failed) - 10} autre(s)")
        return 1

    print(f"\nRetrouver ce lot : transaction_id commençant par 'seedop-{run_id}-'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
