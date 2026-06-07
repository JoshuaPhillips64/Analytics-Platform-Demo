"""Raw-edge validation of Alpha Vantage payloads.

These models assert the *structure* of each response so we fail fast on contract
drift or error payloads (e.g. an invalid symbol returns ``{"Error Message": ...}``).
They deliberately do **not** coerce or clean values — every measure stays a raw
string, to be cast in dbt staging (golden rules #1, #2). ``extra="allow"`` keeps
any extra fields the API adds.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class SchemaValidationError(RuntimeError):
    """Raised when a payload does not match the expected raw shape."""


def _guard_error_payload(payload: dict[str, Any], context: str) -> None:
    """Surface Alpha Vantage error/notice payloads as clear failures."""
    for key in ("Error Message", "Information", "Note"):
        if key in payload:
            raise SchemaValidationError(f"{context}: API returned {key!r}: {payload[key]!r}")


class _Raw(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)


class DailyPricesResponse(_Raw):
    meta_data: dict[str, str] = Field(alias="Meta Data")
    time_series: dict[str, dict[str, str]] = Field(alias="Time Series (Daily)")


class CompanyOverviewResponse(_Raw):
    symbol: str = Field(alias="Symbol")
    market_capitalization: str = Field(alias="MarketCapitalization")


class EarningsResponse(_Raw):
    symbol: str
    annual_earnings: list[dict[str, str]] = Field(alias="annualEarnings")
    quarterly_earnings: list[dict[str, str]] = Field(alias="quarterlyEarnings")


class NewsSentimentResponse(_Raw):
    items: str
    feed: list[dict[str, Any]]


class _EconomicRow(_Raw):
    date: str
    value: str


class EconomicResponse(_Raw):
    data: list[_EconomicRow]


def _validate(model: type[BaseModel], payload: dict[str, Any], context: str) -> dict[str, Any]:
    _guard_error_payload(payload, context)
    try:
        model.model_validate(payload)
    except ValidationError as exc:
        raise SchemaValidationError(f"{context}: {exc}") from exc
    return payload


def validate_daily_prices(payload: dict[str, Any], symbol: str) -> dict[str, Any]:
    return _validate(DailyPricesResponse, payload, f"daily_prices[{symbol}]")


def validate_technical(payload: dict[str, Any], symbol: str, ta_key: str) -> dict[str, Any]:
    """Technical responses key their series under a dynamic 'Technical Analysis: X'."""
    _guard_error_payload(payload, f"technical[{symbol}:{ta_key}]")
    series = payload.get(ta_key)
    if not isinstance(series, dict) or not series:
        raise SchemaValidationError(f"technical[{symbol}:{ta_key}]: missing/empty {ta_key!r}")
    return payload


def validate_company_overview(payload: dict[str, Any], symbol: str) -> dict[str, Any]:
    return _validate(CompanyOverviewResponse, payload, f"overview[{symbol}]")


def validate_earnings(payload: dict[str, Any], symbol: str) -> dict[str, Any]:
    return _validate(EarningsResponse, payload, f"earnings[{symbol}]")


def validate_news_sentiment(payload: dict[str, Any], symbol: str) -> dict[str, Any]:
    return _validate(NewsSentimentResponse, payload, f"news[{symbol}]")


def validate_economic(payload: dict[str, Any], indicator: str) -> dict[str, Any]:
    return _validate(EconomicResponse, payload, f"economic[{indicator}]")
