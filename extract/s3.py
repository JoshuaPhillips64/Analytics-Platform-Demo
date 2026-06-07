"""S3 raw-archive helper.

Archives each raw API response to the immutable S3 raw zone before loading it to
RDS, so the pipeline is replayable. No hardcoded credentials (golden rule #10):
boto3's default chain is used (EC2 IAM instance role, or a local AWS profile).

Key layout: ``endpoint=<endpoint>/symbol=<symbol>/dt=<run_date>/response.json``
"""

from __future__ import annotations

import json
from typing import Any

import boto3


def build_s3_key(endpoint: str, symbol: str | None, run_date: str) -> str:
    return f"endpoint={endpoint}/symbol={symbol or '_none'}/dt={run_date}/response.json"


def archive_response(
    bucket: str,
    endpoint: str,
    symbol: str | None,
    run_date: str,
    payload: dict[str, Any],
    *,
    s3_client: Any | None = None,
) -> str:
    """Upload a raw payload as JSON and return its S3 key."""
    key = build_s3_key(endpoint, symbol, run_date)
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    client = s3_client or boto3.client("s3")
    client.put_object(Bucket=bucket, Key=key, Body=body, ContentType="application/json")
    return key
