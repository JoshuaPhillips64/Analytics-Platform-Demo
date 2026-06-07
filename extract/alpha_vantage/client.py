"""Alpha Vantage HTTP client.

Ported from the legacy ``get_alpha_vantage_data``,
with three fixes per the porting guide:
  * network calls wrapped in ``tenacity`` retry (timeouts / connection / 5xx),
  * the rate-limit interval is config-driven (not a module global),
  * the 60s backoff on the rate-limit "Note" is preserved, but bounded.

The client returns the **raw** JSON payload untouched — no cleaning, no casting,
no fabrication (golden rules #1, #2). Validation happens in ``schemas.py``.

``sleep``/``monotonic``/``session`` are injectable so tests run without real
waiting or network.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

import requests
from tenacity import (
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

# Substrings Alpha Vantage uses in its rate-limit messages (in "Note"/"Information").
_RATE_LIMIT_HINTS = (
    "maximum number",
    "api call frequency",
    "call volume",
    "higher api call",
)


class AlphaVantageError(RuntimeError):
    """Non-retryable Alpha Vantage failure (4xx, or exhausted rate-limit retries)."""


class _RetryableServerError(Exception):
    """Internal: 5xx response, eligible for tenacity retry."""


class AlphaVantageClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://www.alphavantage.co/query",
        *,
        session: requests.Session | None = None,
        min_interval_s: float = 0.8,
        timeout_s: int = 30,
        max_retries: int = 5,
        rate_limit_backoff_s: int = 60,
        max_rate_limit_retries: int = 3,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url
        self._session = session or requests.Session()
        self._min_interval_s = min_interval_s
        self._timeout_s = timeout_s
        self._max_retries = max_retries
        self._rate_limit_backoff_s = rate_limit_backoff_s
        self._max_rate_limit_retries = max_rate_limit_retries
        self._sleep = sleep
        self._monotonic = monotonic
        self._last_call_at = 0.0

    def get(
        self,
        function: str,
        symbol: str | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Call an Alpha Vantage function and return the raw JSON payload."""
        query: dict[str, Any] = {"function": function, "apikey": self._api_key}
        if symbol:
            query["symbol"] = symbol
        if params:
            query.update(params)

        for _ in range(self._max_rate_limit_retries + 1):
            self._throttle()
            data = self._http_get(query)
            if self._is_rate_limited(data):
                logger.warning(
                    "Alpha Vantage rate-limit notice; backing off %ss",
                    self._rate_limit_backoff_s,
                )
                self._sleep(self._rate_limit_backoff_s)
                continue
            return data

        raise AlphaVantageError(
            f"Rate-limit retries exhausted for function={function} symbol={symbol}"
        )

    # -- internals -----------------------------------------------------------

    def _throttle(self) -> None:
        """Sleep just enough to honor the configured min interval between calls."""
        wait = self._min_interval_s - (self._monotonic() - self._last_call_at)
        if wait > 0:
            self._sleep(wait)
        self._last_call_at = self._monotonic()

    def _http_get(self, query: dict[str, Any]) -> dict[str, Any]:
        """GET with retry on connection errors, timeouts, and 5xx responses."""
        retryer = Retrying(
            reraise=True,
            stop=stop_after_attempt(self._max_retries),
            wait=wait_exponential(multiplier=1, max=30),
            retry=retry_if_exception_type(
                (requests.ConnectionError, requests.Timeout, _RetryableServerError)
            ),
            sleep=self._sleep,
        )
        try:
            return retryer(self._do_get, query)
        except (_RetryableServerError, requests.ConnectionError, requests.Timeout) as exc:
            raise AlphaVantageError(
                f"Request failed after {self._max_retries} attempts: {exc}"
            ) from exc

    def _do_get(self, query: dict[str, Any]) -> dict[str, Any]:
        resp = self._session.get(self._base_url, params=query, timeout=self._timeout_s)
        if resp.status_code >= 500:
            raise _RetryableServerError(f"HTTP {resp.status_code}")
        if resp.status_code >= 400:
            raise AlphaVantageError(f"HTTP {resp.status_code} for function={query.get('function')}")
        return resp.json()

    @staticmethod
    def _is_rate_limited(data: dict[str, Any]) -> bool:
        message = f"{data.get('Note', '')} {data.get('Information', '')}".lower()
        return any(hint in message for hint in _RATE_LIMIT_HINTS)
