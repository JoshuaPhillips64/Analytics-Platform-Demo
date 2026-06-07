# BUILD_PLAN.md

Execute these phases **in order**. Do not start a phase until the previous phase's **GATE** passes. Restate the gate at the start of each phase; prove it passes (show command output) before advancing. Commit after each phase.

Detail for every model/test lives in `docs/PROJECT_SPEC.md` — this file is the task list, not a duplicate of the spec.

---

## Phase 0 — Decisions & scaffold
**Tasks**
- The legacy codebase is already in `_legacy_reference/` (read-only). Skim `instructions/PORTING_FROM_LEGACY.md` so you know what's reusable before writing extract code.
- Confirm the **Alpha Vantage plan** (free 25/day vs. premium for one backfill) and lock the **universe** (symbols + ETFs) and **history depth**. Record them in `docs/PROJECT_SPEC.md` §1 and in the watchlist seed.
- Initialize repo: `pyproject.toml` (Python 3.13), `.pre-commit-config.yaml` (ruff/black/sqlfluff), confirm `.gitignore` already excludes `.env`, `_legacy_reference/`, dbt `target/`, `logs/`; create the empty package dirs from the target layout.
- Confirm `python --version` is 3.13.x (NOT 3.14).

**GATE:** repo initialized, pre-commit installed, `_legacy_reference/` readable, universe/history written down.

---

## Phase 1 — AWS infrastructure (manual, documented)
**Tasks**
- Create: S3 bucket (raw archive), RDS Postgres `db.t4g.micro` (publicly reachable only if needed for Hex; otherwise via SG), EC2 `t3.small` (Airflow host) with an **IAM instance role** granting S3 + (optional) SNS.
- Create the RDS schemas: `raw`, `staging`, `intermediate`, `marts`, plus a dbt user/role.
- Security groups: least-privilege. Document every step in `infra/README.md`.
- Set an **AWS Budget alert at $25**.

**GATE:** `psql` connects to RDS and `\dn` shows the four schemas; EC2 can `aws s3 ls` via its instance role (no static keys); budget alert active. **Then stop RDS + EC2 if not moving straight into Phase 2.**

---

## Phase 2 — Python EL: extract + S3 archive + S3→RDS raw load
**Port from legacy per `instructions/PORTING_FROM_LEGACY.md` §1–§3.**
**Tasks**
- `extract/alpha_vantage/client.py`: port `get_alpha_vantage_data`; add `tenacity` retry; config-driven rate limit.
- `extract/alpha_vantage/endpoints.py`: port the `fetch_*` functions (prices, technicals split per-indicator, overview, earnings, news sentiment, economic). Each returns the **raw** payload.
- `extract/alpha_vantage/schemas.py`: `pydantic` models validating the raw shape at the edge (fail fast on contract drift). Do **not** coerce/clean beyond structural validation.
- `extract/load.py`: archive each raw response to S3 (`s3_upload_file`), then upsert into the matching `raw.*` table (`create_engine_from_url` + `upsert_df`/`psql_insert_copy`) keyed on `(symbol, date)` where applicable.
- `extract/run_extract.py`: CLI (`--symbols --start --end --endpoints`).
- `extract/tests/`: pytest for retry behavior, schema validation, and **load idempotency** (re-run = no dupes). Mock the API; no live calls in tests.
- Run a real (small) backfill to populate `raw.*`.

**GATE:** `pytest extract/tests -q` green; re-running the same date range produces zero duplicate rows; `raw.*` tables populated; raw JSON present in S3. No fabricated values anywhere; nulls preserved.

---

## Phase 3 — dbt project + sources + staging
**Tasks**
- `transform/` dbt project: `dbt_project.yml`, `packages.yml` (dbt-utils, dbt-expectations, codegen), `profiles/` for RDS + local-docker Postgres. `dbt deps`.
- `_sources.yml`: declare all `raw.*` sources; add **freshness** (warn 36h / error 72h on `av_daily_prices`).
- `stg_av__*` models (views): snake_case, cast types, dedupe to grain, no joins, no business logic. One per source; union the four technicals into a long shape.
- `.yml` per staging model: description, documented grain, tests (`not_null`, `unique`/`unique_combination_of_columns` on grain).

**GATE:** `dbt build --select staging` green (models + tests + source freshness); every staging model documented; `sqlfluff lint transform/models/staging` clean.

---

## Phase 4 — dbt intermediate + snapshot + seeds
**Tasks**
- Seeds: `sector_etf_map.csv`, `security_watchlist.csv`. `dbt seed`.
- Snapshot: `snap_company_fundamentals` (SCD2 on `symbol`) — **the look-ahead-bias fix**.
- Intermediate models (per spec §5): `int_prices__daily_returns`, `int_technicals__pivoted`, `int_sentiment__daily` (null when no articles), `int_economic__daily` (forward-fill macro only, documented), `int_sector__daily_performance`, `int_fundamentals__point_in_time` (valid_from/valid_to).

**GATE:** `dbt build --select intermediate+ snapshots` green; spot-check returns/technicals against known dates; confirm sentiment is NULL (not 0) where no articles.

---

## Phase 5 — dbt marts + tests + contracts
**Tasks**
- `dim_date`, `dim_security` (conformed).
- `fct_daily_equity_metrics`: **incremental** on `(symbol, date)`, **contract-enforced**, joins prices + returns + pivoted technicals + PIT fundamentals + daily sentiment + macro + sector perf + earnings.
- `mart_watchlist_daily`, `mart_risk_monitor`.
- Tests: relationships fact→dims; `dbt_expectations` ranges (RSI 0–100, volume≥0, etc.); singular tests `assert_high_low_consistency`, `assert_no_future_dates`, `assert_no_fabricated_sentiment`, `assert_pit_fundamentals_no_overlap`.
- `dbt docs generate` — verify clean lineage (no mart references staging/source directly).

**GATE:** full `dbt build` green from clean state; incremental re-run is idempotent; contracts enforced; **zero models without a documented grain and ≥1 test**; lineage clean.

---

## Phase 6 — Airflow (self-hosted)
**Tasks**
- `orchestration/docker-compose.yaml`: official Airflow trimmed to **LocalExecutor** (no Celery/Redis). `.env.example` for connections (RDS, AWS).
- `orchestration/dags/equities_daily.py`: `extract_alpha_vantage` → `load_s3_to_rds_raw` → `dbt source freshness` → `dbt build` → `dbt snapshot` → `notify`. A failed test must halt downstream. (Optional: `astronomer-cosmos` for per-model tasks — free OSS.)
- Run one end-to-end execution (a backfill day) on the EC2 host.

**GATE:** DAG runs green end-to-end; deliberately break a model and confirm the run halts at the failed test, not after loading bad data downstream. **Stop EC2 when done.**

---

## Phase 7 — CI (GitHub Actions, public repo)
**Tasks**
- `.github/workflows/ci.yml`: on PR — `dbt deps`; start a **Postgres service container**; `sqlfluff lint`; `dbt parse`; `dbt seed && dbt build --target ci --warn-error` against a small committed sample; (stretch) upload `dbt docs` artifact.
- Make the repo **public**. Enable branch protection: PR + green CI required to merge to `main`.

**GATE:** a PR shows green checks; a deliberately broken model fails CI and blocks merge.

---

## Phase 8 — BI (Hex Community) + README
**Tasks**
- Hex Community: connect to RDS at project level; build three apps reading `marts.*` only — Research (param: symbol), Risk (`mart_risk_monitor`), Leadership (`mart_watchlist_daily`). Capture screenshots/GIFs.
- (If Hex limits annoy: Evidence.dev static build to S3, or Streamlit on EC2.)
- `README.md`: problem statement, architecture diagram, the three dashboards (screenshots), a "Design decisions" section naming the **EL/ELT split, point-in-time correctness, no-fabrication rule**, run instructions, and a short **cost note** proving <$50/mo.

**GATE (Definition of Done):** clean clone → `dbt build` runs all models + tests green; lineage clean; PIT fix provable via test; three dashboards render live; CI green and gating; repo public; README complete. **Stop RDS + EC2.**

---

## Stretch (only after DoD)
`infra/terraform/` for S3+RDS+EC2+SG; `elementary-data` observability; dbt `exposures` → Hex apps; fact index tuning on `(symbol, date)`; full-history backfill parity check.
