"""Raw-edge validation: valid payloads pass unchanged; drift/errors raise."""

from __future__ import annotations

import pytest

from extract.alpha_vantage import schemas
from extract.alpha_vantage.schemas import SchemaValidationError


def test_valid_prices_pass_through_unchanged(prices_payload):
    out = schemas.validate_daily_prices(prices_payload, "KO")
    assert out is prices_payload
    # values are NOT coerced — still strings
    assert out["Time Series (Daily)"]["2022-01-04"]["1. open"] == "59.0"


def test_error_message_payload_raises():
    with pytest.raises(SchemaValidationError):
        schemas.validate_daily_prices({"Error Message": "Invalid API call"}, "BAD")


def test_rate_limit_note_payload_raises():
    with pytest.raises(SchemaValidationError):
        schemas.validate_company_overview({"Note": "call frequency"}, "KO")


def test_prices_missing_time_series_raises():
    with pytest.raises(SchemaValidationError):
        schemas.validate_daily_prices({"Meta Data": {}}, "KO")


def test_technical_valid_and_missing(rsi_payload):
    assert schemas.validate_technical(rsi_payload, "KO", "Technical Analysis: RSI") is rsi_payload
    with pytest.raises(SchemaValidationError):
        schemas.validate_technical({"Meta Data": {}}, "KO", "Technical Analysis: RSI")


def test_overview_requires_market_cap(overview_payload):
    assert schemas.validate_company_overview(overview_payload, "KO") is overview_payload
    with pytest.raises(SchemaValidationError):
        schemas.validate_company_overview({"Symbol": "KO"}, "KO")


def test_earnings_requires_both_arrays(earnings_payload):
    assert schemas.validate_earnings(earnings_payload, "KO") is earnings_payload
    with pytest.raises(SchemaValidationError):
        schemas.validate_earnings({"symbol": "KO", "annualEarnings": []}, "KO")


def test_news_requires_feed(news_payload):
    assert schemas.validate_news_sentiment(news_payload, "KO") is news_payload
    with pytest.raises(SchemaValidationError):
        schemas.validate_news_sentiment({"items": "0"}, "KO")


def test_economic_requires_data(economic_payload):
    assert schemas.validate_economic(economic_payload, "real_gdp") is economic_payload
    with pytest.raises(SchemaValidationError):
        schemas.validate_economic({"name": "x"}, "real_gdp")
