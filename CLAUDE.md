# CLAUDE.md

This file is auto-loaded by Claude Code. Read it fully before doing anything. Then read, in order:
1. `docs/PROJECT_SPEC.md` — the full spec (architecture, models, tests, cost model).
2. `instructions/PORTING_FROM_LEGACY.md` — exactly what to copy from the old codebase (and what NOT to).
3. `instructions/BUILD_PLAN.md` — the phased task list you will execute.

---

## What this is
A portfolio project for an **Analytics Engineer** role. It ingests equities data from Alpha Vantage, archives it on S3, loads it into Postgres on RDS, transforms it into tested/documented/point-in-time-correct data models with **dbt Core**, orchestrates with self-hosted **Airflow**, ships on GitHub with free CI, and serves three teams via **Hex** (free tier).

It is a rebuild of an existing working project (`stock_prediction_pipelines`). **The full original codebase is included in this repo at `_legacy_reference/` (read-only).** The old project mixes ML/app/infra and does transformation in pandas. We keep its **working API-extraction code** and throw away its transformation approach — `instructions/PORTING_FROM_LEGACY.md` is the exact, function-by-function map of what to copy, what to fix, and what to ignore. Read the legacy files directly when porting; do not guess.

The single most important deliverable is `marts.fct_daily_equity_metrics` — one row per security per trading day, fully enriched, typed, tested, documented.

---

## Golden rules (non-negotiable — violating these defeats the project's purpose)

1. **EL/ELT split.** Python only **extracts and loads raw data**. **All** transformation logic lives in dbt SQL. If you're tempted to clean/join/aggregate in Python, stop — it goes in dbt.
2. **Never fabricate data.** The legacy code injects `random.uniform(-1, 1)` for zero-valued MACD-hist. Do not port that or anything like it. Missing values stay `NULL`. A dbt test enforces this.
3. **Point-in-time correctness.** The legacy code stamps *today's* company fundamentals onto *every historical date* (look-ahead bias). We fix this with a dbt snapshot (SCD2) and as-of joins. Never join current-state attributes onto historical facts.
4. **Tests are mandatory, not optional.** Every model has a documented grain and at least one test. `dbt build` must run models **and** tests green. A phase is not done until its gate passes.
5. **Layering discipline.** `marts` never reference `staging` or `sources` directly — always go through `intermediate` or dims. `staging` is 1:1 with sources, no business logic.
6. **Cost discipline.** Everything must run under **$50/month** (Alpha Vantage excluded). Public repo (free CI). Stop RDS + EC2 when idle. No MWAA, no Astro Cloud, no paid SaaS tiers.
7. **Versions are pinned for a reason.** **Python 3.13** (NOT 3.14 — dbt is incompatible). **dbt-core ≥ 1.10** with `dbt-postgres` (this is the minimum that supports Python 3.13).
8. **Forward-fill only macro indicators**, and document it. Never forward-fill or impute prices/returns.
9. **Options data is out of scope.** The Alpha Vantage options endpoint is flaky/premium. Do not build on it.
10. **Secrets never touch git.** Use a gitignored `.env` locally and an EC2 IAM instance role on AWS. No hardcoded AWS keys (the legacy code hardcodes them — do not copy that pattern).

---

## How to work (workflow for Claude Code)

- Execute `instructions/BUILD_PLAN.md` **phase by phase, in order.** Do not start a phase until the previous phase's **acceptance gate** passes.
- At the start of each phase, restate the gate. At the end, run the gate's commands and show they pass before moving on.
- **Commit after each phase** with a conventional-commit message (e.g. `feat(staging): add stg_av models + tests`).
- When porting code, follow `instructions/PORTING_FROM_LEGACY.md` literally against the files in `_legacy_reference/`. Copy the named functions; rewrite credential/typing handling as noted; never copy the transformation functions.
- If a requirement in the spec conflicts with something you find while building, **stop and flag it** rather than guessing. No assumptions.
- Prefer small, reviewable changes. Keep functions short and typed. Add docstrings.
- Do not add dependencies that aren't needed. Do not scaffold ML, Flask, or anything in the "out of scope" list.

---

## Repo layout (target)
```
equities-analytics-platform/
├── CLAUDE.md                      # this file
├── README.md                      # written in the final phase (architecture, screenshots, run guide)
├── docs/PROJECT_SPEC.md           # the spec — source of truth
├── instructions/                  # build plan + porting guide
├── _legacy_reference/             # FULL original codebase, read-only reference, gitignored. Port from it per the porting guide; ignore everything not named there (ML, webserver, terraform).
├── extract/                       # Python 3.13 EL (extract + S3 archive + S3->RDS raw load)
├── transform/                     # dbt Core project (sources, staging, intermediate, marts, snapshots, seeds, tests)
├── orchestration/                 # self-hosted Airflow (docker-compose LocalExecutor + dags)
├── infra/                         # manual setup notes; OPTIONAL terraform (stretch)
└── .github/workflows/ci.yml       # GitHub Actions: sqlfluff + dbt parse + dbt build on a Postgres service container
```

## Tech + versions
- Python **3.13**; deps managed with `uv` or `pip` + `pyproject.toml`.
- Extract libs: `requests`, `pydantic` (raw-edge validation), `tenacity` (retry), `boto3` (S3), `psycopg2-binary` (RDS).
- Transform: `dbt-core>=1.10`, `dbt-postgres`, packages `dbt-utils`, `dbt-expectations`, `codegen`.
- Lint: `sqlfluff` (dbt templater, postgres dialect), `ruff` + `black` for Python, `pre-commit`.
- Orchestration: Apache Airflow via official Docker Compose, **LocalExecutor**. `astronomer-cosmos` is optional and is free OSS (Apache-2.0) — not the paid Astro product.
- Warehouse: Postgres on RDS `db.t4g.micro`. Schemas: `raw`, `staging`, `intermediate`, `marts` (+ dbt snapshots).
- BI: Hex Community (free). Fallback: Evidence.dev (static build to S3) or Streamlit.

## Common commands
```bash
# Python EL
uv run python -m extract.run_extract --symbols KO,JNJ --start 2022-01-01 --end 2022-12-31 --endpoints prices,overview
uv run pytest extract/tests -q

# dbt (from transform/)
dbt deps
dbt build                      # run + test everything
dbt build --select staging     # one layer
dbt test --select fct_daily_equity_metrics
dbt snapshot
dbt docs generate && dbt docs serve

# lint
sqlfluff lint transform/models
ruff check extract && black --check extract

# airflow (from orchestration/)
docker compose up -d
```

## dbt conventions
- `staging` materialized as `view`; `intermediate` as `view`/`ephemeral`; `marts` as `table`; `fct_daily_equity_metrics` as **incremental** on `(symbol, date)`.
- Names: `stg_av__<entity>`, `int_<entity>__<verb>`, `dim_<noun>`, `fct_<grain>`, `mart_<use_case>`.
- Every model gets a `.yml` with description, documented grain, and tests. Enforce **contracts** on marts + dims.
- Sources declared with **freshness** (warn 36h / error 72h on `av_daily_prices`).

## Out of scope (do not build)
ML/prediction models, Flask web app, LLM "analysis", options data, MWAA, Astro Cloud, intraday/real-time, anything that costs money beyond the AWS infra listed.
