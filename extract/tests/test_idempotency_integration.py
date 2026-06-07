"""Integration: re-loading the same data produces zero duplicate rows.

Skipped unless EXTRACT_IT_DB_URL is set (a Postgres SQLAlchemy URL). Run against
RDS or the CI Postgres service container:

    EXTRACT_IT_DB_URL='postgresql+psycopg2://dbt:pw@host:5432/equities?sslmode=require' \
        uv run pytest extract/tests/test_idempotency_integration.py -q
"""

from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import text

from extract import db, load

DB_URL = os.environ.get("EXTRACT_IT_DB_URL")
pytestmark = pytest.mark.skipif(not DB_URL, reason="EXTRACT_IT_DB_URL not set")


def _count(engine, schema, table) -> int:
    with engine.connect() as conn:
        return conn.execute(text(f"SELECT count(*) FROM {schema}.{table}")).scalar_one()


def test_reload_is_idempotent(prices_payload):
    engine = db.create_engine_from_url(DB_URL)
    table = f"_it_prices_{uuid.uuid4().hex[:8]}"
    spec = load.RawTableSpec(table, [("symbol", "text"), ("date", "text")])
    rows = load.decompose_daily_prices("KO", prices_payload)

    try:
        n1 = load.load_rows(engine, spec, rows, "s3://k/1")
        c1 = _count(engine, load.RAW_SCHEMA, table)
        # Second load of identical data must not add rows.
        n2 = load.load_rows(engine, spec, rows, "s3://k/2")
        c2 = _count(engine, load.RAW_SCHEMA, table)

        assert n1 == n2 == len(rows)
        assert c1 == c2 == len(rows)
    finally:
        with engine.begin() as conn:
            conn.execute(text(f"DROP TABLE IF EXISTS {load.RAW_SCHEMA}.{table}"))
