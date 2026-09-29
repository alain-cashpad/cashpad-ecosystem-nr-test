from __future__ import annotations

"""
Test de non-régression généré par /cp-test — ticket BOV2KABAN-2111
[BACK] Incremental pull of customer accounts from device into BO V2

Fige le comportement OBSERVÉ et VALIDÉ le 2026-07-20 sur la DB de staging BO V2
(réplica du pull device → BO V2). La surface vérifiée est la BASE DE DONNÉES
(les acceptance criteria sont tous internes : upsert, réconciliation, curseur,
scope par site) — il n'existe pas de surface HTTP publique pour ce LOT
(écrans/listing = LOT3, hors périmètre).

Tables réplica (schéma public) :
    customers            PK (site_id, id)          — id = uuid device-origine
    customer_operations  PK (site_id, id, customer)— append-only, FK customer→customers.id

Choix de conception confirmé sur staging : AUCUNE table de curseur durable
séparée ; le curseur de version est dérivé de MAX(version) du réplica commité.
=> AC1/AC4/AC5 sont garantis par construction ; ce test fige les invariants
   observables plutôt que des comptes exacts (le réplica continue de se remplir,
   un golden de volumétrie serait fragile).

Accès DB : lecture seule. La connexion force default_transaction_read_only=on ;
seules des requêtes SELECT sont émises. L'URL vient de .env (BOV2_STAGING_DB_URL),
même accès privilégié que celui utilisé pour la vérification manuelle.

Dépendance : psycopg (v3). Installer avec uv :  uv add "psycopg[binary]"
"""

import os

import pytest

try:
    import psycopg
except ImportError:  # pragma: no cover
    psycopg = None

from dotenv import load_dotenv

load_dotenv()


# ── Sites observés lors de la vérification du 2026-07-20 ──
# (6 sites ↔ 6 devices listés dans le ticket). Utilisé comme plancher de présence,
# pas comme égalité stricte : le réplica peut gagner de nouveaux sites.
OBSERVED_SITES = {4652, 4714, 4741, 4753, 4756, 4757}


def get_db_url() -> str:
    """URL de la DB staging BO V2 (réplica). Skip si absente : accès privilégié, tout le monde ne l'a pas."""
    url = os.getenv("BOV2_STAGING_DB_URL")
    if not url:
        pytest.skip("BOV2_STAGING_DB_URL absent de .env — test DB réplica ignoré")
    if psycopg is None:
        pytest.skip("psycopg non installé — `uv add \"psycopg[binary]\"`")
    return url


@pytest.fixture(scope="module")
def conn():
    """Connexion unique, READ-ONLY, partagée entre les steps."""
    url = get_db_url()
    # default_transaction_read_only=on : garde-fou dur, aucune écriture possible.
    connection = psycopg.connect(url, autocommit=True, options="-c default_transaction_read_only=on")
    try:
        yield connection
    finally:
        connection.close()


def _scalar(conn, sql: str):
    with conn.cursor() as cur:
        cur.execute(sql)
        row = cur.fetchone()
        return row[0] if row else None


def _rows(conn, sql: str):
    with conn.cursor() as cur:
        cur.execute(sql)
        return cur.fetchall()


def test_01_replicas_populated(conn):
    """Le pull a bien alimenté le réplica : customers et opérations non vides (témoin d'exécution)."""
    n_customers = _scalar(conn, "SELECT count(*) FROM customers")
    n_operations = _scalar(conn, "SELECT count(*) FROM customer_operations")
    assert n_customers > 0, "Aucun customer dans le réplica — pull non exécuté ?"
    assert n_operations > 0, "Aucune opération dans le réplica"


def test_02_reconciliation_key_is_site_id_plus_id(conn):
    """AC2 (structurel) : la PK customers est (site_id, id) — réconciliation par id device-origine garantie."""
    pk_def = _scalar(
        conn,
        """
        SELECT pg_get_constraintdef(oid)
        FROM pg_constraint
        WHERE conrelid = 'customers'::regclass AND contype = 'p'
        """,
    )
    assert pk_def == "PRIMARY KEY (site_id, id)", f"PK customers inattendue : {pk_def}"


def test_03_no_duplicate_customer_per_device_id(conn):
    """AC2 : aucun doublon par (site_id, id) — l'upsert ne peut que mettre à jour, jamais dupliquer."""
    dups = _scalar(
        conn,
        """
        SELECT count(*) FROM (
            SELECT site_id, id FROM customers GROUP BY site_id, id HAVING count(*) > 1
        ) d
        """,
    )
    assert dups == 0, f"{dups} clé(s) (site_id, id) en doublon dans customers"


def test_04_no_orphan_operations(conn):
    """Rattachement opérations→customer : chaque opération référence un customer existant (0 orpheline)."""
    orphans = _scalar(
        conn,
        """
        SELECT count(*)
        FROM customer_operations o
        LEFT JOIN customers c ON c.site_id = o.site_id AND c.id = o.customer
        WHERE c.id IS NULL
        """,
    )
    assert orphans == 0, f"{orphans} opération(s) orpheline(s) sans customer rattaché"


def test_05_operations_append_only_no_monotonic_dup(conn):
    """Append-only : pas de doublon sur la clé monotone (site_id, raw_id) des opérations."""
    dups = _scalar(
        conn,
        """
        SELECT count(*) FROM (
            SELECT site_id, raw_id FROM customer_operations
            GROUP BY site_id, raw_id HAVING count(*) > 1
        ) d
        """,
    )
    assert dups == 0, f"{dups} clé(s) monotone (site_id, raw_id) en doublon dans customer_operations"


def test_06_per_site_scope(conn):
    """Scope par site : les données sont réparties par site_id ; les sites observés sont présents."""
    sites = {r[0] for r in _rows(conn, "SELECT DISTINCT site_id FROM customers")}
    assert sites, "Aucun site_id dans customers"
    missing = OBSERVED_SITES - sites
    assert not missing, f"Sites observés disparus du réplica : {sorted(missing)}"


def test_07_soft_delete_propagated(conn):
    """Soft-delete propagé : la colonne deleted porte des suppressions (jamais de hard-delete côté BO V2)."""
    soft_deleted = _scalar(conn, "SELECT count(*) FROM customers WHERE deleted")
    assert soft_deleted > 0, "Aucun customer soft-deleted — propagation du soft-delete non observée"


def test_08_version_cursor_derived_from_replica(conn):
    """AC1/AC4 : le curseur est dérivé du réplica (MAX(version) commité), pas d'un état séparé.

    Invariant figé de l'ordonnancement customers-avant-opérations observé le 2026-07-20 :
    la plus haute version customers est >= la plus haute version opérations.
    """
    vmax_customers = _scalar(conn, "SELECT max(version) FROM customers")
    vmax_operations = _scalar(conn, "SELECT max(version) FROM customer_operations")
    assert vmax_customers is not None and vmax_customers > 0
    assert vmax_operations is not None and vmax_operations > 0
    assert vmax_customers >= vmax_operations, (
        "Ordonnancement inattendu : max(version) opérations > max(version) customers "
        f"({vmax_operations} > {vmax_customers})"
    )
