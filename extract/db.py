"""RDS load helpers: engine factory + idempotent raw upsert.

Ported intent from the legacy ``create_engine_from_url`` / ``upsert_df`` /
``psql_insert_copy``, rebuilt as a clean, idempotent ``INSERT ... ON CONFLICT``
keyed on the table's grain. Re-running the same data updates rows in place — it
never creates duplicates (Phase 2 gate). DDL here only creates the ``raw.*``
landing tables; all typing/transformation happens later in dbt.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

import psycopg2.extras
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

# Fixed (non-key) columns every raw table carries.
_RECORD_COL = "record"
_S3_COL = "source_s3_key"
_LOADED_COL = "loaded_at"


def create_engine_from_url(db_url: str) -> Engine:
    """Create a SQLAlchemy engine from a database URL."""
    if not isinstance(db_url, str):
        raise TypeError("db_url must be a string")
    return create_engine(db_url, pool_pre_ping=True)


def build_create_table_sql(schema: str, table: str, key_columns: Sequence[tuple[str, str]]) -> str:
    """DDL for a raw landing table: grain key columns + record jsonb + lineage."""
    key_defs = ",\n    ".join(f'"{name}" {sqltype} NOT NULL' for name, sqltype in key_columns)
    pk_cols = ", ".join(f'"{name}"' for name, _ in key_columns)
    return (
        f"CREATE TABLE IF NOT EXISTS {schema}.{table} (\n"
        f"    {key_defs},\n"
        f'    "{_RECORD_COL}" jsonb NOT NULL,\n'
        f'    "{_S3_COL}" text,\n'
        f'    "{_LOADED_COL}" timestamptz NOT NULL DEFAULT now(),\n'
        f"    CONSTRAINT {table}_pk PRIMARY KEY ({pk_cols})\n"
        f");"
    )


def build_upsert_sql(schema: str, table: str, key_columns: Sequence[str]) -> str:
    """INSERT ... ON CONFLICT (grain) DO UPDATE — the idempotent raw load."""
    insert_cols = [*key_columns, _RECORD_COL, _S3_COL]
    cols_sql = ", ".join(f'"{c}"' for c in insert_cols)
    conflict_sql = ", ".join(f'"{c}"' for c in key_columns)
    return (
        f"INSERT INTO {schema}.{table} ({cols_sql}) VALUES %s\n"
        f"ON CONFLICT ({conflict_sql}) DO UPDATE SET\n"
        f'    "{_RECORD_COL}" = EXCLUDED."{_RECORD_COL}",\n'
        f'    "{_S3_COL}" = EXCLUDED."{_S3_COL}",\n'
        f'    "{_LOADED_COL}" = now();'
    )


def ensure_raw_table(
    engine: Engine, schema: str, table: str, key_columns: Sequence[tuple[str, str]]
) -> None:
    conn = engine.raw_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(build_create_table_sql(schema, table, key_columns))
        conn.commit()
    finally:
        conn.close()


def upsert_rows(
    engine: Engine,
    schema: str,
    table: str,
    key_columns: Sequence[str],
    rows: Sequence[dict[str, Any]],
    source_s3_key: str | None,
) -> int:
    """Upsert raw rows. Each row has its key columns plus a ``record`` dict.

    Returns the number of rows sent. Idempotent: a second call with the same
    keys updates in place (zero duplicates).
    """
    if not rows:
        return 0

    sql = build_upsert_sql(schema, table, key_columns)
    values = [
        tuple(
            [row[col] for col in key_columns]
            + [psycopg2.extras.Json(row[_RECORD_COL]), source_s3_key]
        )
        for row in rows
    ]

    conn = engine.raw_connection()
    try:
        with conn.cursor() as cur:
            psycopg2.extras.execute_values(cur, sql, values, page_size=500)
        conn.commit()
    finally:
        conn.close()

    logger.info("upserted %d rows into %s.%s", len(values), schema, table)
    return len(values)
