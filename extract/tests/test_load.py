"""Decomposition is structural and lossless; SQL builders are correct."""

from __future__ import annotations

from extract import db, load


def test_decompose_daily_prices_keeps_record_verbatim(prices_payload):
    rows = load.decompose_daily_prices("KO", prices_payload)
    assert len(rows) == 2
    by_date = {r["date"]: r for r in rows}
    assert by_date["2022-01-04"]["symbol"] == "KO"
    # record is the untouched per-day dict
    assert by_date["2022-01-04"]["record"] == prices_payload["Time Series (Daily)"]["2022-01-04"]


def test_decompose_technical(rsi_payload):
    rows = load.decompose_technical("KO", rsi_payload, "Technical Analysis: RSI")
    assert {r["date"] for r in rows} == {"2022-01-03", "2022-01-04"}
    assert rows[0]["record"]["RSI"] in {"55.1", "53.0"}


def test_decompose_overview_single_row(overview_payload):
    rows = load.decompose_overview("KO", overview_payload)
    assert rows == [{"symbol": "KO", "record": overview_payload}]


def test_decompose_earnings_splits_annual_quarterly(earnings_payload):
    rows = load.decompose_earnings("KO", earnings_payload)
    types = sorted(r["report_type"] for r in rows)
    assert types == ["annual", "quarterly"]
    for r in rows:
        assert r["symbol"] == "KO"
        assert r["fiscal_date_ending"] == "2022-12-31"


def test_decompose_news_uses_url_key(news_payload):
    rows = load.decompose_news_sentiment("KO", news_payload)
    assert {r["url"] for r in rows} == {"https://example.com/a", "https://example.com/b"}


def test_decompose_economic(economic_payload):
    rows = load.decompose_economic(economic_payload)
    assert {r["date"] for r in rows} == {"2022-10-01", "2022-07-01"}
    assert rows[0]["record"] in economic_payload["data"]


def test_dedupe_keeps_last_per_key():
    rows = [
        {"symbol": "KO", "url": "u", "record": {"v": 1}},
        {"symbol": "KO", "url": "u", "record": {"v": 2}},
        {"symbol": "KO", "url": "x", "record": {"v": 3}},
    ]
    out = load.dedupe_by_keys(rows, ["symbol", "url"])
    assert len(out) == 2
    by_url = {r["url"]: r for r in out}
    assert by_url["u"]["record"] == {"v": 2}  # last wins


def test_build_create_table_sql_has_pk_and_jsonb():
    sql = db.build_create_table_sql(
        "raw", "av_daily_prices", [("symbol", "text"), ("date", "text")]
    )
    assert "CREATE TABLE IF NOT EXISTS raw.av_daily_prices" in sql
    assert '"record" jsonb NOT NULL' in sql
    assert 'PRIMARY KEY ("symbol", "date")' in sql


def test_build_upsert_sql_is_idempotent_upsert():
    sql = db.build_upsert_sql("raw", "av_daily_prices", ["symbol", "date"])
    assert "INSERT INTO raw.av_daily_prices" in sql
    assert 'ON CONFLICT ("symbol", "date") DO UPDATE' in sql
    assert 'EXCLUDED."record"' in sql


def test_every_raw_table_has_grain_keys():
    for name, spec in load.RAW_TABLES.items():
        assert spec.name == name
        assert spec.key_columns, f"{name} must have a grain"
