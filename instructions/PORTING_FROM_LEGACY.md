# PORTING_FROM_LEGACY.md

What to copy from the old `stock_prediction_pipelines` repo, what to fix on the way in, and what to leave behind. This is based on a function-by-function read of the legacy code. **Follow it literally.**

## The legacy code is already in this repo
The full original codebase is at **`_legacy_reference/`** (read-only). You do not need to clone anything — open the files directly. The line numbers below match the files as they sit in `_legacy_reference/src/pipelines/`.

Treat `_legacy_reference/` as **read-only**. Never import from it at runtime; copy the named functions into `extract/` and adapt them. It is gitignored by default (keeps the public portfolio clean); everything outside the files named below — ML training, `webserver/`, `terraform/` — is out of scope and must be ignored.

## The one rule that decides everything
**Port the API-call functions. Do not port the transformation functions.**
- KEEP: `get_alpha_vantage_data` and every `fetch_*` function — these are the working extraction layer.
- DROP: every `generate_*`, `apply_*`, `process_*`, `get_*_performance`, `get_*_score`, `get_*_cached` function — this is Python-side transformation that now lives in dbt SQL, and it contains the two bugs we're fixing.

---

## 1. `_legacy_reference/src/pipelines/alpha_vantage_functions.py`

### KEEP (copy into `extract/alpha_vantage/`)
| Function | Why | Adapt |
|---|---|---|
| `get_alpha_vantage_data` (L29) | Core API caller with rate-limit handling + the "Note" retry loop. The genuinely working piece. | Wrap network call in `tenacity` retry (timeouts/5xx). Make the rate interval config-driven. Keep the 60s backoff on the rate-limit "Note". |
| `fetch_time_series_data` (L70) | `TIME_SERIES_DAILY_ADJUSTED` — raw daily OHLCV. Reuse for **equities AND sector ETFs AND index proxies (SPY/QQQ)**. | Return the raw payload; do **not** coerce types here — land raw, cast in dbt. |
| `fetch_technical_indicators` (L108) | RSI / MACD / ADX / BBANDS calls. | Split so each indicator lands to its **own** raw table (`raw.av_rsi`, `raw.av_macd`, `raw.av_bbands`, `raw.av_adx`). Do not merge indicators in Python. |
| `fetch_company_overview` (L142) | Fundamentals snapshot source. | Land 1:1 to `raw.av_company_overview` with a `loaded_at`. The SCD2 snapshot happens in dbt. |
| `fetch_earnings_data` (L158) | EPS / surprise. | Land to `raw.av_earnings`. |
| `fetch_earnings_calendar` (L174) | Optional next-earnings dates. | Optional. Land raw if used. |

### MINE FOR THE FETCH, DROP THE LOGIC
These contain a useful underlying API call wrapped in Python transformation. Reuse only the call; rebuild the logic in dbt.
| Function | Reuse | Rebuild in dbt as |
|---|---|---|
| `get_market_index_performance` (L323) | the `fetch_time_series_data` call on index proxies | `int_prices__daily_returns` (compute returns in SQL) |
| `get_sentiment_score` (L363) | the `NEWS_SENTIMENT` API call (land **article-level** raw) | `int_sentiment__daily` (daily mean + count; null when no articles) |
| `get_economic_indicators_cached` (L404) | the `REAL_GDP` / `UNEMPLOYMENT` / inflation calls (land raw) | `int_economic__daily` (forward-fill onto trading calendar) |
| `get_sector_performance` (L537) | the ETF `fetch_time_series_data` calls | `int_sector__daily_performance`; move the `sector_etf_mapping` dict → seed `sector_etf_map.csv` |

### DO NOT PORT (transformation + bugs)
- `generate_enriched_stock_data` (L597) — the big assembler. **Contains both bugs**: look-ahead bias (current overview stamped on every date) and `random.uniform(-1,1)` MACD fabrication (around L117 of the file). Replaced entirely by the dbt DAG.
- `generate_basic_stock_data` (L765) — same assembly pattern.
- `apply_earnings_data` (L203), `process_earnings_data` (L288) — earnings joins → SQL.
- `get_options_data` (L452) — **out of scope** (flaky endpoint).
- `safe_float` (L521) — do not use at extract; land raw strings/values, cast in dbt staging.

---

## 2. `_legacy_reference/src/pipelines/aws_functions.py`
| Function | Verdict | Adapt |
|---|---|---|
| `open_s3_resource_connection` (L8) | KEEP idea | **Drop the hardcoded `AWS_ACCESS_KEY/SECRET`**. Use boto3's default credential chain (EC2 IAM instance role / local AWS profile). |
| `s3_upload_file` (L27) | KEEP | Use for archiving raw API responses to `s3://.../endpoint=.../symbol=.../dt=.../response.json`. |
| `pull_from_s3` (L15) | KEEP | Use in the S3→RDS loader to read archived JSON. |
| `pull_from_s3_bucket_using_last_updated` (L46), `pull_from_s3_bucket_using_text` (L83), `loop_through_s3_folder` (L109) | SKIP | Not needed for this pipeline. |
| `send_sns_email` (L141) | OPTIONAL | Could wire to an Airflow `on_failure_callback`. Keep credential-free if used. |

---

## 3. `_legacy_reference/src/pipelines/database_functions.py`
| Function | Verdict | Notes |
|---|---|---|
| `create_engine_from_url` (L16) | KEEP | Engine factory for RDS. |
| `psql_insert_copy` (L44) | KEEP | Fast COPY-based insert for loading raw to RDS. |
| `upsert_df` (L148) | KEEP | The idempotent raw-load mechanism (legacy ingests upsert on `'symbol, date'`). Verify it, reuse it for S3→`raw` loads. |
| `fetch_dataframe` (L28), `create_df_from_query` (L61) | KEEP (optional) | Handy for sanity checks/tests. |
| `execute_query` (L22) | KEEP (optional) | Small helper. |
| `get_table_data_types` (L76) | **DROP** | SQL-injection f-string + a real bug (`table_schema = {schema}` missing quotes). Not needed — dbt owns typing. |
| `match_db_data_types_to_pandas` (L91) | **DROP** | Depends on the buggy fn + `datatype_mapping.csv`. dbt handles types. |
| `overwrite_table_from_df` (L106) | **DROP** | Uses `to_sql(replace)` + a `deps_save_and_drop_dependencies` function that isn't even in the repo (non-reproducible). dbt owns transformed tables. |
| `truncate_and_load_table_from_df` (L129), `append_data_from_df` (L139) | SKIP | `upsert_df` covers our needs. |

---

## 4. `_legacy_reference/src/pipelines/config.py`
- KEEP the env-loading pattern; prefer upgrading to `pydantic-settings`.
- `STOCK_SYMBOLS` list → move to seed `security_watchlist.csv` (don't hardcode the universe in Python).
- The `sector_etf_mapping` dict (in `alpha_vantage_functions.py`) → seed `sector_etf_map.csv`.

## 5. Other legacy assets
- `_legacy_reference/src/pipelines/datatype_mapping.csv` — **DROP** (tied to the abandoned typing approach).
- `_legacy_reference/.github/workflows/ci-cd.yml` — reference only; we write fresh CI for dbt. Do not copy wholesale (it builds Lambdas/ML).
- `_legacy_reference/src/airflow/dags/*` — reference for Airflow wiring patterns only. They call `generate_*` (dropped), so do not port them; write fresh DAGs per the spec.
- `_legacy_reference/src/tests/unit/test_lambda_functions.py` — **DROP** (it imports paths that don't exist; it's broken). Write real pytest in `extract/tests/`.

---

## Net result of porting
You keep ~7 working `fetch_*`/client functions + 4 small DB/S3 helpers. You rebuild **all** enrichment, joins, returns, sentiment aggregation, macro fill, sector performance, earnings application, and typing in dbt SQL — tested and documented. The two data-integrity bugs are designed out by construction.
