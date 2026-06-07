"""Endpoint fetchers send the right function and validate the response."""

from __future__ import annotations

import responses

from extract.alpha_vantage import endpoints

URL = "https://www.alphavantage.co/query"


@responses.activate
def test_fetch_daily_prices_defaults_to_free_endpoint(no_sleep_client_factory, prices_payload):
    client, _ = no_sleep_client_factory()
    responses.add(responses.GET, URL, json=prices_payload, status=200)

    out = endpoints.fetch_daily_prices(client, "KO")

    assert out == prices_payload
    assert "function=TIME_SERIES_DAILY" in responses.calls[0].request.url
    assert "TIME_SERIES_DAILY_ADJUSTED" not in responses.calls[0].request.url


@responses.activate
def test_fetch_daily_prices_premium_function(no_sleep_client_factory, prices_payload):
    client, _ = no_sleep_client_factory()
    responses.add(responses.GET, URL, json=prices_payload, status=200)

    endpoints.fetch_daily_prices(client, "KO", function="TIME_SERIES_DAILY_ADJUSTED")

    assert "function=TIME_SERIES_DAILY_ADJUSTED" in responses.calls[0].request.url


@responses.activate
def test_fetch_technical_sends_indicator_function(no_sleep_client_factory, rsi_payload):
    client, _ = no_sleep_client_factory()
    responses.add(responses.GET, URL, json=rsi_payload, status=200)

    endpoints.fetch_technical(client, "KO", "rsi")

    url = responses.calls[0].request.url
    assert "function=RSI" in url
    assert "time_period=14" in url
