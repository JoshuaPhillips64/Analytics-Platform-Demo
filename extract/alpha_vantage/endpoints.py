"""Endpoint fetchers — ported ``fetch_*`` functions.

Each returns the **raw** Alpha Vantage payload (structurally validated, never
coerced). The legacy split-adjustment math in ``fetch_time_series_data`` is
deliberately NOT ported — that is transformation and now lives in dbt
(golden rule #1). Indicators land to their own raw tables (no merging in Python).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from extract.alpha_vantage import schemas
from extract.alpha_vantage.client import AlphaVantageClient


@dataclass(frozen=True)
class IndicatorSpec:
    code: str
    function: str
    params: dict[str, Any]
    ta_key: str
    raw_table: str


@dataclass(frozen=True)
class EconomicSpec:
    code: str
    function: str
    raw_table: str
    params: dict[str, Any] = field(default_factory=dict)


# RSI / MACD / ADX / BBANDS — each to its own raw table.
INDICATOR_SPECS: dict[str, IndicatorSpec] = {
    "rsi": IndicatorSpec(
        "rsi",
        "RSI",
        {"interval": "daily", "time_period": 14, "series_type": "close"},
        "Technical Analysis: RSI",
        "av_rsi",
    ),
    "macd": IndicatorSpec(
        "macd",
        "MACD",
        {"interval": "daily", "series_type": "close"},
        "Technical Analysis: MACD",
        "av_macd",
    ),
    "adx": IndicatorSpec(
        "adx",
        "ADX",
        {"interval": "daily", "time_period": 14},
        "Technical Analysis: ADX",
        "av_adx",
    ),
    "bbands": IndicatorSpec(
        "bbands",
        "BBANDS",
        {"interval": "daily", "time_period": 20, "series_type": "close"},
        "Technical Analysis: BBANDS",
        "av_bbands",
    ),
}

ECONOMIC_SPECS: dict[str, EconomicSpec] = {
    "real_gdp": EconomicSpec("real_gdp", "REAL_GDP", "av_real_gdp", {"interval": "quarterly"}),
    "inflation": EconomicSpec("inflation", "INFLATION", "av_inflation", {"interval": "annual"}),
    "unemployment": EconomicSpec("unemployment", "UNEMPLOYMENT", "av_unemployment"),
}


def fetch_daily_prices(client: AlphaVantageClient, symbol: str) -> dict[str, Any]:
    """Full daily adjusted OHLCV. Used for equities, sector ETFs, and index proxies."""
    data = client.get("TIME_SERIES_DAILY_ADJUSTED", symbol, {"outputsize": "full"})
    return schemas.validate_daily_prices(data, symbol)


def fetch_technical(client: AlphaVantageClient, symbol: str, indicator: str) -> dict[str, Any]:
    spec = INDICATOR_SPECS[indicator]
    data = client.get(spec.function, symbol, spec.params)
    return schemas.validate_technical(data, symbol, spec.ta_key)


def fetch_company_overview(client: AlphaVantageClient, symbol: str) -> dict[str, Any]:
    data = client.get("OVERVIEW", symbol)
    return schemas.validate_company_overview(data, symbol)


def fetch_earnings(client: AlphaVantageClient, symbol: str) -> dict[str, Any]:
    data = client.get("EARNINGS", symbol)
    return schemas.validate_earnings(data, symbol)


def fetch_news_sentiment(
    client: AlphaVantageClient,
    symbol: str,
    *,
    time_from: str | None = None,
    time_to: str | None = None,
    limit: int = 1000,
) -> dict[str, Any]:
    """Article-level news sentiment. ``time_from``/``time_to`` are ``YYYYMMDDTHHMM``."""
    params: dict[str, Any] = {"tickers": symbol, "sort": "LATEST", "limit": limit}
    if time_from:
        params["time_from"] = time_from
    if time_to:
        params["time_to"] = time_to
    data = client.get("NEWS_SENTIMENT", None, params)
    return schemas.validate_news_sentiment(data, symbol)


def fetch_economic(client: AlphaVantageClient, indicator: str) -> dict[str, Any]:
    spec = ECONOMIC_SPECS[indicator]
    data = client.get(spec.function, None, spec.params or None)
    return schemas.validate_economic(data, indicator)
