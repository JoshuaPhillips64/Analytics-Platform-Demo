"""Client behaviour: retry on 5xx, backoff on rate-limit notice, fail on 4xx."""

from __future__ import annotations

import pytest
import responses

from extract.alpha_vantage.client import AlphaVantageError

URL = "https://www.alphavantage.co/query"


@responses.activate
def test_retries_on_5xx_then_succeeds(no_sleep_client_factory):
    client, _ = no_sleep_client_factory(max_retries=3)
    responses.add(responses.GET, URL, status=500)
    responses.add(responses.GET, URL, json={"ok": "1"}, status=200)

    data = client.get("OVERVIEW", "KO")

    assert data == {"ok": "1"}
    assert len(responses.calls) == 2  # one failure, one success


@responses.activate
def test_gives_up_after_max_retries(no_sleep_client_factory):
    client, _ = no_sleep_client_factory(max_retries=3)
    responses.add(responses.GET, URL, status=503)
    responses.add(responses.GET, URL, status=503)
    responses.add(responses.GET, URL, status=503)

    with pytest.raises(AlphaVantageError):
        client.get("OVERVIEW", "KO")
    assert len(responses.calls) == 3


@responses.activate
def test_backs_off_on_rate_limit_notice_then_succeeds(no_sleep_client_factory):
    client, sleeps = no_sleep_client_factory()
    responses.add(
        responses.GET,
        URL,
        json={"Note": "Thank you... our standard API call frequency is 75 calls per minute"},
        status=200,
    )
    responses.add(responses.GET, URL, json={"Symbol": "KO"}, status=200)

    data = client.get("OVERVIEW", "KO")

    assert data == {"Symbol": "KO"}
    assert 60 in sleeps  # the 60s rate-limit backoff fired


@responses.activate
def test_rate_limit_retries_exhausted_raises(no_sleep_client_factory):
    client, _ = no_sleep_client_factory(max_rate_limit_retries=1)
    note = {"Information": "higher API call volume; please subscribe"}
    responses.add(responses.GET, URL, json=note, status=200)
    responses.add(responses.GET, URL, json=note, status=200)

    with pytest.raises(AlphaVantageError):
        client.get("OVERVIEW", "KO")


@responses.activate
def test_4xx_raises_without_retry(no_sleep_client_factory):
    client, _ = no_sleep_client_factory()
    responses.add(responses.GET, URL, status=404)

    with pytest.raises(AlphaVantageError):
        client.get("OVERVIEW", "KO")
    assert len(responses.calls) == 1


@responses.activate
def test_sends_function_apikey_and_symbol(no_sleep_client_factory):
    client, _ = no_sleep_client_factory()
    responses.add(responses.GET, URL, json={"ok": "1"}, status=200)

    client.get("RSI", "KO", {"interval": "daily"})

    qs = responses.calls[0].request.url
    assert "function=RSI" in qs
    assert "symbol=KO" in qs
    assert "apikey=TEST_KEY" in qs
    assert "interval=daily" in qs
