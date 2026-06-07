"""Bootstrap the RDS database without psql: create the four dbt schemas and the
dbt application role. Cross-platform equivalent of infra/sql/bootstrap.sql for
environments that don't have the psql client installed.

DDL/admin only -- no transformation logic (golden rule #1). Idempotent: safe to
re-run. Connection + passwords are read from environment variables; nothing is
written to disk or git.

Usage (from repo root, with the project venv active):

    PGHOST=<rds_address> PGPASSWORD=<master_pw> DBT_PASSWORD=<dbt_pw> \
        python infra/scripts/bootstrap_db.py

Env vars:
    PGHOST       RDS hostname            (required)
    PGPORT       default 5432
    PGDATABASE   default "equities"
    PGUSER       master user, default "postgres"
    PGPASSWORD   master password         (required)
    PGSSLMODE    default "require"
    DBT_PASSWORD password for the dbt role (required)
"""

from __future__ import annotations

import os
import sys

import psycopg2
from psycopg2 import sql

SCHEMAS = ("raw", "staging", "intermediate", "marts")


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        sys.exit(f"ERROR: environment variable {name} is required")
    return value


def main() -> None:
    host = _require("PGHOST")
    master_password = _require("PGPASSWORD")
    dbt_password = _require("DBT_PASSWORD")
    port = os.environ.get("PGPORT", "5432")
    dbname = os.environ.get("PGDATABASE", "equities")
    user = os.environ.get("PGUSER", "postgres")
    sslmode = os.environ.get("PGSSLMODE", "require")

    conn = psycopg2.connect(
        host=host,
        port=port,
        dbname=dbname,
        user=user,
        password=master_password,
        sslmode=sslmode,
        connect_timeout=15,
    )
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            # 1. dbt application role (CREATE ROLE has no IF NOT EXISTS).
            cur.execute("SELECT 1 FROM pg_roles WHERE rolname = 'dbt'")
            if cur.fetchone():
                cur.execute("ALTER ROLE dbt WITH LOGIN PASSWORD %s", (dbt_password,))
                print("role 'dbt' already existed -> password ensured")
            else:
                cur.execute("CREATE ROLE dbt LOGIN PASSWORD %s", (dbt_password,))
                print("role 'dbt' created")

            # On RDS the master user is rds_superuser (not a true superuser), so
            # it must be a member of dbt to create objects owned by dbt.
            cur.execute("GRANT dbt TO CURRENT_USER")

            # 2. Schemas owned by dbt.
            for schema in SCHEMAS:
                cur.execute(
                    sql.SQL("CREATE SCHEMA IF NOT EXISTS {} AUTHORIZATION dbt").format(
                        sql.Identifier(schema)
                    )
                )
            print(f"schemas ensured: {', '.join(SCHEMAS)}")

            # 3. Privileges.
            cur.execute(
                sql.SQL("GRANT CONNECT ON DATABASE {} TO dbt").format(sql.Identifier(dbname))
            )
            cur.execute(
                sql.SQL("GRANT USAGE, CREATE ON SCHEMA {} TO dbt").format(
                    sql.SQL(", ").join(sql.Identifier(s) for s in SCHEMAS)
                )
            )

            # 4. Confirm (psql \dn equivalent).
            cur.execute(
                "SELECT nspname, pg_get_userbyid(nspowner) AS owner "
                "FROM pg_namespace WHERE nspname = ANY(%s) ORDER BY nspname",
                (list(SCHEMAS),),
            )
            print("\nSchemas present:")
            print(f"  {'name':<14} owner")
            for name, owner in cur.fetchall():
                print(f"  {name:<14} {owner}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
