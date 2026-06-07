"""CLI entrypoint for the EL layer.

Examples
--------
    uv run python -m extract.run_extract \
        --symbols KO,JNJ --endpoints prices,technicals,overview,earnings,news \
        --start 2022-01-01 --end 2025-01-01
    uv run python -m extract.run_extract --symbols XLK,SPY --endpoints prices,technicals
    uv run python -m extract.run_extract --endpoints economic

Each requested endpoint is applied to each symbol (``economic`` is symbol-
independent and runs once). Per-symbol failures are logged and skipped so one bad
symbol/endpoint does not abort the whole backfill.
"""

from __future__ import annotations

import argparse
import logging
from datetime import date, datetime

import boto3

from extract import load
from extract.alpha_vantage.client import AlphaVantageClient
from extract.alpha_vantage.endpoints import ECONOMIC_SPECS, INDICATOR_SPECS
from extract.config import Settings, get_settings
from extract.db import create_engine_from_url

logger = logging.getLogger("extract")

INDICATORS = list(INDICATOR_SPECS)  # rsi, macd, adx, bbands
SYMBOL_ENDPOINTS = ["prices", *INDICATORS, "overview", "earnings", "news"]
ALL_ENDPOINTS = [*SYMBOL_ENDPOINTS, "economic"]
DEFAULT_ENDPOINTS = ["prices", "technicals", "overview", "earnings", "news", "economic"]


def _expand_endpoints(requested: list[str]) -> list[str]:
    """Expand the 'technicals' alias into the four indicator endpoints."""
    expanded: list[str] = []
    for ep in requested:
        if ep == "technicals":
            expanded.extend(INDICATORS)
        else:
            expanded.append(ep)
    # de-dup, preserve order
    seen: set[str] = set()
    return [e for e in expanded if not (e in seen or seen.add(e))]


def _av_timestamp(value: str | None, *, end: bool) -> str | None:
    """Convert a YYYY-MM-DD date to Alpha Vantage's YYYYMMDDTHHMM form."""
    if not value:
        return None
    d = datetime.strptime(value, "%Y-%m-%d")
    return d.strftime("%Y%m%dT2359") if end else d.strftime("%Y%m%dT0000")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Alpha Vantage -> S3 -> RDS raw EL")
    p.add_argument("--symbols", default="", help="Comma-separated symbols")
    p.add_argument(
        "--endpoints",
        default=",".join(DEFAULT_ENDPOINTS),
        help=f"Comma-separated; any of: {', '.join(['technicals', *ALL_ENDPOINTS])}",
    )
    p.add_argument("--start", help="History/news start date YYYY-MM-DD (news time_from)")
    p.add_argument("--end", help="News time_to date YYYY-MM-DD")
    p.add_argument("--run-date", help="S3 partition date YYYY-MM-DD (default: today)")
    return p.parse_args(argv)


def build_client(settings: Settings) -> AlphaVantageClient:
    return AlphaVantageClient(
        api_key=settings.alpha_vantage_api_key,
        base_url=settings.av_base_url,
        min_interval_s=settings.min_interval_s,
        timeout_s=settings.av_request_timeout_s,
        max_retries=settings.av_max_retries,
        rate_limit_backoff_s=settings.av_rate_limit_backoff_s,
    )


def run(args: argparse.Namespace, settings: Settings) -> int:
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    endpoints = _expand_endpoints([e.strip() for e in args.endpoints.split(",") if e.strip()])
    run_date = args.run_date or date.today().isoformat()
    time_from = _av_timestamp(args.start, end=False)
    time_to = _av_timestamp(args.end, end=True)

    client = build_client(settings)
    engine = create_engine_from_url(settings.sqlalchemy_url)
    s3_client = boto3.client("s3", region_name=settings.aws_region)
    bucket = settings.s3_bucket

    total = 0
    failures = 0

    # Symbol-independent economic indicators (run once).
    if "economic" in endpoints:
        for indicator in ECONOMIC_SPECS:
            try:
                n = load.ingest_economic(client, engine, s3_client, bucket, indicator, run_date)
                logger.info("economic[%s]: %d rows", indicator, n)
                total += n
            except Exception:
                failures += 1
                logger.exception("economic[%s] failed", indicator)

    symbol_endpoints = [e for e in endpoints if e in SYMBOL_ENDPOINTS]
    for symbol in symbols:
        for ep in symbol_endpoints:
            try:
                n = _ingest_symbol_endpoint(
                    ep,
                    client,
                    engine,
                    s3_client,
                    bucket,
                    symbol,
                    run_date,
                    time_from=time_from,
                    time_to=time_to,
                )
                logger.info("%s[%s]: %d rows", ep, symbol, n)
                total += n
            except Exception:
                failures += 1
                logger.exception("%s[%s] failed", ep, symbol)

    logger.info("DONE: %d rows upserted, %d failures", total, failures)
    return failures


def _ingest_symbol_endpoint(
    ep: str,
    client: AlphaVantageClient,
    engine,
    s3_client,
    bucket: str,
    symbol: str,
    run_date: str,
    *,
    time_from: str | None,
    time_to: str | None,
) -> int:
    if ep == "prices":
        return load.ingest_daily_prices(client, engine, s3_client, bucket, symbol, run_date)
    if ep in INDICATORS:
        return load.ingest_technical(client, engine, s3_client, bucket, symbol, ep, run_date)
    if ep == "overview":
        return load.ingest_company_overview(client, engine, s3_client, bucket, symbol, run_date)
    if ep == "earnings":
        return load.ingest_earnings(client, engine, s3_client, bucket, symbol, run_date)
    if ep == "news":
        return load.ingest_news_sentiment(
            client,
            engine,
            s3_client,
            bucket,
            symbol,
            run_date,
            time_from=time_from,
            time_to=time_to,
        )
    raise ValueError(f"unknown endpoint: {ep}")


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    args = parse_args(argv)
    settings = get_settings()
    return run(args, settings)


if __name__ == "__main__":
    raise SystemExit(main())
