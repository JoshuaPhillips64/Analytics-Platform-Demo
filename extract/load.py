"""Decompose raw payloads into grain-keyed rows and load them to ``raw.*``.

Decomposition is purely structural: it routes the **untouched** API JSON into one
row per record at the table's grain (the ``record`` column holds the verbatim
object). No casting, cleaning, joining, or fabrication happens here — that is all
dbt's job (golden rules #1, #2). Field naming and typing happen in dbt staging.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy.engine import Engine

from extract import db, s3
from extract.alpha_vantage import endpoints
from extract.alpha_vantage.client import AlphaVantageClient

RAW_SCHEMA = "raw"


@dataclass(frozen=True)
class RawTableSpec:
    name: str
    key_columns: list[tuple[str, str]]

    @property
    def key_names(self) -> list[str]:
        return [name for name, _ in self.key_columns]


_PRICE_LIKE = [("symbol", "text"), ("date", "text")]

RAW_TABLES: dict[str, RawTableSpec] = {
    "av_daily_prices": RawTableSpec("av_daily_prices", _PRICE_LIKE),
    "av_rsi": RawTableSpec("av_rsi", _PRICE_LIKE),
    "av_macd": RawTableSpec("av_macd", _PRICE_LIKE),
    "av_adx": RawTableSpec("av_adx", _PRICE_LIKE),
    "av_bbands": RawTableSpec("av_bbands", _PRICE_LIKE),
    "av_company_overview": RawTableSpec("av_company_overview", [("symbol", "text")]),
    "av_earnings": RawTableSpec(
        "av_earnings",
        [("symbol", "text"), ("fiscal_date_ending", "text"), ("report_type", "text")],
    ),
    "av_news_sentiment": RawTableSpec("av_news_sentiment", [("symbol", "text"), ("url", "text")]),
    "av_real_gdp": RawTableSpec("av_real_gdp", [("date", "text")]),
    "av_inflation": RawTableSpec("av_inflation", [("date", "text")]),
    "av_unemployment": RawTableSpec("av_unemployment", [("date", "text")]),
}


# --- decomposition (pure) ---------------------------------------------------


def decompose_daily_prices(symbol: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
    series = payload["Time Series (Daily)"]
    return [{"symbol": symbol, "date": d, "record": rec} for d, rec in series.items()]


def decompose_technical(symbol: str, payload: dict[str, Any], ta_key: str) -> list[dict[str, Any]]:
    series = payload[ta_key]
    return [{"symbol": symbol, "date": d, "record": rec} for d, rec in series.items()]


def decompose_overview(symbol: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [{"symbol": symbol, "record": payload}]


def decompose_earnings(symbol: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for report_type, key in (("annual", "annualEarnings"), ("quarterly", "quarterlyEarnings")):
        for rec in payload.get(key, []):
            rows.append(
                {
                    "symbol": symbol,
                    "fiscal_date_ending": rec["fiscalDateEnding"],
                    "report_type": report_type,
                    "record": rec,
                }
            )
    return rows


def decompose_news_sentiment(symbol: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"symbol": symbol, "url": article["url"], "record": article}
        for article in payload.get("feed", [])
    ]


def decompose_economic(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [{"date": item["date"], "record": item} for item in payload["data"]]


def dedupe_by_keys(
    rows: Sequence[dict[str, Any]], key_names: Sequence[str]
) -> list[dict[str, Any]]:
    """Keep the last row per grain key, so a single upsert batch has no dup keys
    (Postgres rejects ON CONFLICT hitting the same row twice in one statement)."""
    by_key: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in rows:
        by_key[tuple(row[k] for k in key_names)] = row
    return list(by_key.values())


# --- load orchestration -----------------------------------------------------


def load_rows(
    engine: Engine, spec: RawTableSpec, rows: Sequence[dict[str, Any]], s3_key: str | None
) -> int:
    deduped = dedupe_by_keys(rows, spec.key_names)
    db.ensure_raw_table(engine, RAW_SCHEMA, spec.name, spec.key_columns)
    return db.upsert_rows(engine, RAW_SCHEMA, spec.name, spec.key_names, deduped, s3_key)


def ingest_daily_prices(
    client: AlphaVantageClient,
    engine: Engine,
    s3_client: Any,
    bucket: str,
    symbol: str,
    run_date: str,
    *,
    prices_function: str = "TIME_SERIES_DAILY",
    prices_outputsize: str = "compact",
) -> int:
    payload = endpoints.fetch_daily_prices(
        client, symbol, function=prices_function, outputsize=prices_outputsize
    )
    key = s3.archive_response(
        bucket, "daily_prices", symbol, run_date, payload, s3_client=s3_client
    )
    return load_rows(
        engine, RAW_TABLES["av_daily_prices"], decompose_daily_prices(symbol, payload), key
    )


def ingest_technical(
    client: AlphaVantageClient,
    engine: Engine,
    s3_client: Any,
    bucket: str,
    symbol: str,
    indicator: str,
    run_date: str,
) -> int:
    spec_ind = endpoints.INDICATOR_SPECS[indicator]
    payload = endpoints.fetch_technical(client, symbol, indicator)
    key = s3.archive_response(bucket, indicator, symbol, run_date, payload, s3_client=s3_client)
    rows = decompose_technical(symbol, payload, spec_ind.ta_key)
    return load_rows(engine, RAW_TABLES[spec_ind.raw_table], rows, key)


def ingest_company_overview(
    client: AlphaVantageClient,
    engine: Engine,
    s3_client: Any,
    bucket: str,
    symbol: str,
    run_date: str,
) -> int:
    payload = endpoints.fetch_company_overview(client, symbol)
    key = s3.archive_response(bucket, "overview", symbol, run_date, payload, s3_client=s3_client)
    return load_rows(
        engine, RAW_TABLES["av_company_overview"], decompose_overview(symbol, payload), key
    )


def ingest_earnings(
    client: AlphaVantageClient,
    engine: Engine,
    s3_client: Any,
    bucket: str,
    symbol: str,
    run_date: str,
) -> int:
    payload = endpoints.fetch_earnings(client, symbol)
    key = s3.archive_response(bucket, "earnings", symbol, run_date, payload, s3_client=s3_client)
    return load_rows(engine, RAW_TABLES["av_earnings"], decompose_earnings(symbol, payload), key)


def ingest_news_sentiment(
    client: AlphaVantageClient,
    engine: Engine,
    s3_client: Any,
    bucket: str,
    symbol: str,
    run_date: str,
    *,
    time_from: str | None = None,
    time_to: str | None = None,
) -> int:
    payload = endpoints.fetch_news_sentiment(client, symbol, time_from=time_from, time_to=time_to)
    key = s3.archive_response(
        bucket, "news_sentiment", symbol, run_date, payload, s3_client=s3_client
    )
    return load_rows(
        engine, RAW_TABLES["av_news_sentiment"], decompose_news_sentiment(symbol, payload), key
    )


def ingest_economic(
    client: AlphaVantageClient,
    engine: Engine,
    s3_client: Any,
    bucket: str,
    indicator: str,
    run_date: str,
) -> int:
    spec_econ = endpoints.ECONOMIC_SPECS[indicator]
    payload = endpoints.fetch_economic(client, indicator)
    key = s3.archive_response(bucket, indicator, None, run_date, payload, s3_client=s3_client)
    return load_rows(engine, RAW_TABLES[spec_econ.raw_table], decompose_economic(payload), key)
