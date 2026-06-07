"""Shared fixtures and sample Alpha Vantage payloads (trimmed to shape)."""

from __future__ import annotations

import pytest

from extract.alpha_vantage.client import AlphaVantageClient


@pytest.fixture
def no_sleep_client_factory():
    """Build an AlphaVantageClient that never really sleeps or throttles."""

    def _make(**overrides):
        calls: list[float] = []

        def fake_sleep(seconds: float) -> None:
            calls.append(seconds)

        kwargs = {
            "api_key": "TEST_KEY",
            "min_interval_s": 0,
            "sleep": fake_sleep,
            "max_retries": 3,
            "rate_limit_backoff_s": 60,
        }
        kwargs.update(overrides)
        client = AlphaVantageClient(**kwargs)
        return client, calls

    return _make


@pytest.fixture
def prices_payload() -> dict:
    return {
        "Meta Data": {"2. Symbol": "KO"},
        "Time Series (Daily)": {
            "2022-01-04": {
                "1. open": "59.0",
                "2. high": "60.0",
                "3. low": "58.5",
                "4. close": "59.5",
                "5. adjusted close": "55.0",
                "6. volume": "1000000",
                "7. dividend amount": "0.0000",
                "8. split coefficient": "1.0",
            },
            "2022-01-03": {
                "1. open": "58.0",
                "2. high": "59.0",
                "3. low": "57.5",
                "4. close": "58.7",
                "5. adjusted close": "54.2",
                "6. volume": "900000",
                "7. dividend amount": "0.0000",
                "8. split coefficient": "1.0",
            },
        },
    }


@pytest.fixture
def rsi_payload() -> dict:
    return {
        "Meta Data": {"1: Symbol": "KO"},
        "Technical Analysis: RSI": {
            "2022-01-04": {"RSI": "55.1"},
            "2022-01-03": {"RSI": "53.0"},
        },
    }


@pytest.fixture
def overview_payload() -> dict:
    return {"Symbol": "KO", "Sector": "CONSUMER STAPLES", "MarketCapitalization": "250000000000"}


@pytest.fixture
def earnings_payload() -> dict:
    return {
        "symbol": "KO",
        "annualEarnings": [{"fiscalDateEnding": "2022-12-31", "reportedEPS": "2.19"}],
        "quarterlyEarnings": [
            {"fiscalDateEnding": "2022-12-31", "reportedEPS": "0.45", "surprise": "0.02"}
        ],
    }


@pytest.fixture
def news_payload() -> dict:
    return {
        "items": "2",
        "feed": [
            {
                "url": "https://example.com/a",
                "time_published": "20220103T120000",
                "ticker_sentiment": [{"ticker": "KO", "ticker_sentiment_score": "0.21"}],
            },
            {
                "url": "https://example.com/b",
                "time_published": "20220104T090000",
                "ticker_sentiment": [{"ticker": "KO", "ticker_sentiment_score": "-0.05"}],
            },
        ],
    }


@pytest.fixture
def economic_payload() -> dict:
    return {
        "name": "Real Gross Domestic Product",
        "interval": "quarterly",
        "data": [
            {"date": "2022-10-01", "value": "20000.0"},
            {"date": "2022-07-01", "value": "19900.0"},
        ],
    }
