"""CLI helper units (no network, no DB)."""

from __future__ import annotations

from extract import run_extract


def test_expand_technicals_alias():
    out = run_extract._expand_endpoints(["prices", "technicals", "economic"])
    assert out == ["prices", "rsi", "macd", "adx", "bbands", "economic"]


def test_expand_dedupes_preserving_order():
    out = run_extract._expand_endpoints(["rsi", "technicals", "rsi"])
    assert out == ["rsi", "macd", "adx", "bbands"]


def test_av_timestamp_start_and_end():
    assert run_extract._av_timestamp("2022-01-01", end=False) == "20220101T0000"
    assert run_extract._av_timestamp("2022-12-31", end=True) == "20221231T2359"
    assert run_extract._av_timestamp(None, end=False) is None


def test_parse_args_defaults():
    args = run_extract.parse_args(["--symbols", "KO,JNJ"])
    assert args.symbols == "KO,JNJ"
    assert "economic" in args.endpoints
