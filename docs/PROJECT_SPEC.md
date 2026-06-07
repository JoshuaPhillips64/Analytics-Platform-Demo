# Equities Analytics Platform — Project Spec (v2, AWS + cost-capped)

**One-line:** An end-to-end analytics pipeline that ingests raw equities data from Alpha Vantage, archives it on S3, loads it into Postgres on RDS, transforms it into tested, documented, point-in-time-correct data models with dbt Core, orchestrates with self-hosted Airflow, ships on GitHub with free CI, and serves three cross-functional teams through Hex (free tier).

**Hard constraints (v2):**
- All infrastructure on **AWS**.
- **Python 3.13** (requires dbt-core ≥ 1.10 — verified below).
- Raw landing on **S3**.
- Warehouse = **Postgres on RDS** (dbt runs *inside* it; marts served from it).
- Orchestration = **Airflow**, self-hosted — **pay for infra only**, no managed/paid Airflow (no MWAA, no Astro Cloud).
- CI and BI must have **free tiers**.
- **Couple of days of work, < $50/month** total AWS+SaaS (Alpha Vantage API excluded).

**The deliverable that matters:** `fct_daily_equity_metrics` — one row per security per trading day, with prices, returns, technicals, point-in-time fundamentals, daily sentiment, macro context, and sector performance joined, typed, tested, and documented.

---

## 1. Cost model & free-tier strategy (read this first — it drives every other choice)

| Component | Service | Monthly cost (post-free-tier, conservative) | Free-tier / lever |
|---|---|---|---|
| Raw landing | **S3** | ~$0 (pennies) | 5 GB free 12 mo; data here is <1 GB regardless |
| Warehouse | **RDS Postgres `db.t4g.micro`** | ~$12–15 + ~$2–3 storage | $0 if in 12-mo free tier (750 hrs micro + 20 GB); **stop when idle** (auto-restarts after 7 days) |
| Orchestration | **EC2 `t3.small`** self-hosted Airflow | ~$15 if 24/7 | **Stop when idle → ~$1–3**; or run Airflow locally in Docker → $0 |
| Transform | **dbt Core** | $0 | Open source |
| CI | **GitHub Actions** | $0 | Free/unlimited minutes on **public** repos |
| BI | **Hex Community** | $0 | Free forever (limits in §9) |
| **Total** | | **~$30–35 worst case 24/7; <$10 if you stop instances** | Comfortably under $50 |

**Cost discipline rules:**
- Make the repo **public** → CI is free.
- **Stop RDS and EC2 whenever you're not building or demoing.** This is a 2-day project; you'll run them a handful of hours. (RDS auto-restarts after 7 days stopped — just re-stop it.)
- Set an **AWS Budget alert at $25** so a forgotten running instance can't surprise you.
- Use `db.t4g.micro` (Graviton, cheapest) — this dataset is ~100k–200k rows; micro is plenty.

**The real bottleneck is NOT AWS — it's Alpha Vantage.** The free AV tier is **25 requests/day, 5/min**. A full historical backfill of ~21 symbols across ~7 endpoints is hundreds of calls — impossible in a day on free tier. Options:
1. **Buy AV premium ($49.99/mo, 75 req/min) for the one big backfill, run it, then cancel.** Cleanest. (This is the "except Alpha Vantage" cost you already accepted.)
2. **Shrink scope to fit free tier:** fewer symbols (e.g. 5) and/or shorter history (e.g. 2 years), spread the backfill over 2–3 days.
3. After the initial backfill, daily incremental loads are tiny and fit comfortably in free-tier limits.

Decide this on day 0 — it determines your universe and history depth.

### LOCKED DECISIONS (Phase 0, 2026-06-06)

**Alpha Vantage plan:** **Free tier** (revised 2026-06-06, Phase 2). 25 requests/day, 5/min. Implications, accepted:
- **Prices use `TIME_SERIES_DAILY` (non-adjusted)** — no `adjusted_close`/`dividend`/`split_coefficient`. (`TIME_SERIES_DAILY_ADJUSTED` is premium-only.) The endpoint is config-driven (`AV_PRICES_FUNCTION`), so switching to premium-adjusted later is a one-line `.env` change.
- **Reduced *active* universe** to fit 25 calls/day (see below); the rest of the seed stays `is_active=false` and is documented but not loaded.
- **Backfill spread over days** — a day's run targets a subset via `--symbols/--endpoints`; re-runs are idempotent.
- Originally Phase 0 chose premium for one backfill; revised to free tier to avoid the spend.

**Active universe (free-tier, `is_active=true`):** equities **KO, JNJ, PG**; index proxy **SPY**; sector ETF **XLP** (Consumer Defensive). Per-equity endpoints: prices, RSI, overview, earnings, news. Indicators beyond RSI (MACD/ADX/BBANDS) are deferred under the daily cap. Daily budget ≈ prices(5) + rsi(3) + overview(3) + earnings(3) + news(3) + economic(3) = ~20 calls.

**History depth:** Free tier is limited to **`outputsize=compact` ≈ latest 100 trading days** (`outputsize=full` is premium, even for `TIME_SERIES_DAILY`). The intended **2022-01-01 → present (~3 years)** with `full` requires premium — a one-line `AV_PRICES_OUTPUTSIZE=full` switch once premium is active. Re-runs are idempotent.

**Universe — 12 equities** (sector-diversified; the watchlist that drives the apps), recorded in `transform/seeds/security_watchlist.csv`:

| Symbol | Company | Sector (per fundamentals) |
|---|---|---|
| AAPL | Apple Inc. | Technology |
| MSFT | Microsoft Corporation | Technology |
| JNJ | Johnson & Johnson | Healthcare |
| PFE | Pfizer Inc. | Healthcare |
| JPM | JPMorgan Chase & Co. | Financial Services |
| KO | The Coca-Cola Company | Consumer Defensive |
| PG | The Procter & Gamble Company | Consumer Defensive |
| XOM | Exxon Mobil Corporation | Energy |
| CVX | Chevron Corporation | Energy |
| HD | The Home Depot Inc. | Consumer Cyclical |
| CAT | Caterpillar Inc. | Industrials |
| NEE | NextEra Energy Inc. | Utilities |

> Note: `sector` is **not** stored in the watchlist seed — it is sourced point-in-time from `av_company_overview` (golden rule #3). The column above is documentation only.

**Sector ETFs** (price-extracted for `int_sector__daily_performance`; the `sector → etf` mapping becomes the Phase 4 seed `sector_etf_map.csv`):

| Sector | ETF |
|---|---|
| Technology | XLK |
| Healthcare | XLV |
| Financial Services | XLF |
| Consumer Defensive | XLP |
| Energy | XLE |
| Consumer Cyclical | XLY |
| Industrials | XLI |
| Utilities | XLU |

**Index proxies** (price-extracted; used for beta / market-return context in `mart_risk_monitor`): **SPY**, **QQQ**.

So the **extraction symbol set** = 12 equities + 8 sector ETFs + 2 index proxies = **22 symbols** for price/technical endpoints; fundamentals/earnings/overview endpoints apply to the **12 equities** only; news sentiment to the 12 equities; economic indicators are symbol-independent.

---

## 2. Why this project (mapped to the job description)

| Job requirement | Where it's demonstrated |
|---|---|
| Multi-step ETL jobs | Python extract → S3 archive → RDS raw load → dbt staging → intermediate → marts, gated end to end |
| Robust data models via dbt | Layered dbt project: sources, staging, intermediate, marts, snapshots, seeds, tests, docs, contracts |
| Airflow + workflow management | Self-hosted DAG: extract/load → freshness → `dbt build` → snapshot → (optional) BI refresh, with backfills |
| GitHub / version control | Public repo, branch protection, PR workflow, GitHub Actions CI (lint + `dbt build` on a Postgres service container) |
| SQL + Python transformation | Python owns extract/load only; **all** transformation is SQL in dbt |
| Reporting/dashboards in Hex for cross-functional teams | Three Hex apps for Research, Risk, and Leadership, reading from marts only |

**Design choices that double as interview talking points** (each fixes a real flaw in the original source job):
1. **Clean EL/ELT split.** Python only extracts/loads raw data. The original transformed in pandas then `to_sql(if_exists='replace')` — untestable, unversioned. We move 100% of transformation into dbt SQL.
2. **No fabricated values.** The original injects `random.uniform(-1,1)` when MACD-hist is zero. We land true source values; nulls stay null; a test asserts no fabrication.
3. **Point-in-time correctness.** The original stamps *today's* fundamentals onto *all historical dates* (look-ahead bias). We snapshot fundamentals (SCD2) and join as-of each date.
4. **Reference data version-controlled.** The original hardcodes a sector→ETF Python dict; we move it to a dbt seed.
5. **Idempotent, incremental loads.** Raw loads upsert on `(symbol, date)`; the fact is incremental. Re-running a day is safe.

---

## 3. Architecture (corrected for dbt-on-Postgres)

**Important:** dbt-postgres transforms data *inside Postgres*. So raw must be loaded into RDS for dbt to run SQL against it. S3 is the immutable raw **archive/landing + replay source**; RDS holds `raw` **and** the transformed schemas; the cleaned **marts** are the final analysis-ready tables served from RDS.

```
Alpha Vantage API
      │  Python 3.13: extract + validate (pydantic) + retry/backoff (tenacity)
      ▼
S3 raw zone        s3://.../endpoint=.../symbol=.../dt=.../response.json   (immutable, replayable)
      │  Python loader: read S3 → upsert into RDS raw schema (on symbol,date)
      ▼
RDS Postgres (db.t4g.micro)
   ├─ schema raw.*          (landed 1:1 with API)
   │       │  dbt Core (runs ON EC2 or laptop, executes SQL IN Postgres)
   │       ▼
   ├─ schema staging.*      stg_*  (snake_case, typed, deduped, 1:1)
   ├─ schema intermediate.* int_*  (returns, technicals pivot, PIT joins, windows)
   ├─ snapshots             snap_company_fundamentals (SCD2)
   └─ schema marts.*        dim_date, dim_security, fct_daily_equity_metrics,
                            mart_watchlist_daily, mart_risk_monitor
      │
      ▼
Hex Community  ──►  Research app  |  Risk app  |  Leadership app   (reads marts.* only)
```

Orchestration (Airflow on EC2, daily):
`extract_alpha_vantage` → `load_s3_to_rds_raw` → `dbt source freshness` → `dbt build` (run + test) → `dbt snapshot` → `notify` (optional Hex refresh is a paid feature — skip on free tier; Hex queries live data anyway)

---

## 4. Stack decision (v2)

| Layer | Choice | Notes |
|---|---|---|
| Runtime | **Python 3.13** | ✅ Supported by **dbt-core ≥ 1.10** + dbt-postgres. **Do NOT use 3.14** — dbt is not yet compatible (mashumaro/pydantic-v1 break). |
| Extract/Load | `requests`, `pydantic` (raw contract), `tenacity` (retry), `boto3` (S3), `psycopg2-binary` (RDS load) | |
| Raw archive | **S3** | Partitioned by `endpoint/symbol/dt`; lifecycle rule to Glacier/expire if you care, but volume is trivial |
| Warehouse | **RDS Postgres `db.t4g.micro`**, `dbt-postgres` adapter | Holds raw + transformed schemas; dbt runs in it |
| Transform | **dbt Core ≥ 1.10** (+ `dbt-utils`, `dbt-expectations`, `codegen`) | The core AE showcase |
| Orchestration | **Self-hosted Apache Airflow** (official Docker Compose, **LocalExecutor**) on EC2 `t3.small`; stop when idle | No MWAA (~hundreds/mo), no Astro Cloud (paid). `astronomer-cosmos` is **free OSS (Apache-2.0)** and optional — unrelated to Astro's paid product |
| CI | **GitHub Actions**, public repo | `sqlfluff` + `dbt parse` + `dbt build` against a **Postgres service container** in the runner |
| BI | **Hex Community (free)** | Reads marts; see §9 for limits. Free web-app fallback: **Evidence.dev** (SQL-as-BI, static build to S3) or Streamlit on the EC2 |

**Local dev tip:** you can iterate dbt against a local Postgres Docker container for speed, then point `profiles.yml` at RDS for the real runs. Same dbt code.

---

## 5. dbt model DAG (explicit)

### Sources (`models/staging/alpha_vantage/_sources.yml`)
Raw tables in RDS, landed 1:1 with the API (never pre-join in Python):
- `raw.av_daily_prices` (equities **and** sector ETFs)
- `raw.av_rsi`, `raw.av_macd`, `raw.av_bbands`, `raw.av_adx`
- `raw.av_company_overview`
- `raw.av_news_sentiment` (article-level)
- `raw.av_real_gdp`, `raw.av_unemployment`, `raw.av_inflation`
- `raw.av_earnings`

### Staging — `stg_av__*` (views): snake_case, cast, dedupe to grain, no business logic, no joins
- `stg_av__daily_prices` — grain `(symbol, date)`
- `stg_av__technical_indicators` — union the four indicator sources into long `(symbol, date, indicator, value)`
- `stg_av__company_overview` — grain `(symbol, loaded_at)`
- `stg_av__news_sentiment` — grain `(symbol, article_published_at)`
- `stg_av__economic_indicators` — grain `(indicator, period_date)`
- `stg_av__earnings` — grain `(symbol, fiscal_date_ending)`

### Snapshots — `snapshots/`
- `snap_company_fundamentals` — SCD2 over overview keyed on `symbol` (market cap / P/E / div yield / beta / sector / industry). **The look-ahead-bias fix.**

### Seeds — `seeds/`
- `sector_etf_map.csv` — `sector, etf_symbol` (replaces hardcoded dict)
- `security_watchlist.csv` — `symbol, company_name, is_active` (drives the universe)

### Intermediate — `int_*`
- `int_prices__daily_returns` — daily/log return, 5/20/60-day returns, 20-day rolling vol, 52-week high/low (window fns)
- `int_technicals__pivoted` — one row per `(symbol, date)` with rsi/macd/macd_signal/macd_hist/adx/upper_band/lower_band
- `int_sentiment__daily` — daily mean sentiment + article_count; **null when no articles, never 0**
- `int_economic__daily` — forward-fill quarterly/monthly macro onto the trading calendar (document the fill)
- `int_sector__daily_performance` — sector ETF daily return mapped to securities via `sector_etf_map`
- `int_fundamentals__point_in_time` — from the snapshot, with `valid_from`/`valid_to` for as-of joins

### Marts — `marts/`
- `dim_date` — calendar + `is_trading_day`, fiscal periods, week/month/quarter keys
- `dim_security` — `symbol, company_name, sector, industry, is_active` (conformed dimension)
- `fct_daily_equity_metrics` ⭐ — **incremental**, grain `(symbol, date)`, **contract-enforced**. Joins prices + returns + pivoted technicals + PIT fundamentals + daily sentiment + macro + sector perf + earnings.
- `mart_watchlist_daily` — curated columns for the Leadership app
- `mart_risk_monitor` — volatility, beta, max drawdown, distance-from-52w-high for the Risk app

---

## 6. Testing strategy (this is what gets you hired)

**Generic:** `not_null` + `unique` on every grain; `dbt_utils.unique_combination_of_columns` on `(symbol, date)`; `relationships` fact→dim_security and fact→dim_date; `accepted_values` on `sector`, `indicator`.

**Range (`dbt_expectations`):** RSI 0–100; `volume >= 0`; `dividend_yield >= 0`; `close > 0`; not-null on core price columns.

**Singular (`tests/`):**
- `assert_high_low_consistency.sql` — fail rows where `high < low | open | close`, or `low > open | close`
- `assert_no_future_dates.sql` — fail `date > current_date`
- `assert_no_fabricated_sentiment.sql` — sentiment must be null (not 0) when `article_count = 0`
- `assert_pit_fundamentals_no_overlap.sql` — no overlapping SCD2 windows per symbol

**Source freshness:** warn 36h / error 72h on `av_daily_prices` (tuned to the trading calendar).

**Contracts:** enforce column names + types on `fct_daily_equity_metrics` and the dims so a schema change can't silently break Hex.

Target: **every model documented, every model tested, zero untested grain.** Put that line in the README.

---

## 7. Repo structure

```
equities-analytics-platform/
├── README.md                      # architecture, screenshots, run guide, design decisions
├── docs/{architecture.md,data_model.md,decisions/}
├── extract/                       # Python 3.13 EL
│   ├── alpha_vantage/{client.py,endpoints.py,schemas.py}
│   ├── load.py                    # S3 -> RDS raw upsert (on symbol,date)
│   ├── run_extract.py             # CLI: --symbols --start --end --endpoints
│   └── tests/                     # pytest: retry, schema validation, load idempotency
├── transform/                     # dbt project
│   ├── dbt_project.yml
│   ├── packages.yml               # dbt_utils, dbt_expectations, codegen
│   ├── profiles/                  # postgres (rds) + postgres (local docker) examples
│   ├── models/{staging,intermediate,marts}/
│   ├── snapshots/  seeds/  tests/  macros/
├── orchestration/                 # Airflow (self-hosted)
│   ├── docker-compose.yaml        # official Airflow, trimmed to LocalExecutor
│   ├── dags/equities_daily.py
│   └── .env.example
├── infra/                         # optional, keep minimal
│   ├── README.md                  # manual setup steps (S3 bucket, RDS, EC2, security groups)
│   └── terraform/                 # OPTIONAL stretch: s3 + rds + ec2 + sg (IaC signal)
├── .github/workflows/ci.yml
├── .sqlfluff  .pre-commit-config.yaml  pyproject.toml
```

---

## 8. CI (GitHub Actions, public repo, $0)

On every PR:
1. `pip install` + `dbt deps`
2. Spin up a **Postgres service container** in the runner (free, ephemeral)
3. `sqlfluff lint` (dbt templater)
4. `dbt parse` (compile/ref errors)
5. `dbt seed && dbt build --target ci --warn-error` against the service-container Postgres with a small committed sample → runs **and tests** every model
6. (stretch) `dbt docs generate` uploaded as a build artifact

Branch protection: PR + green CI required to merge to `main`.

---

## 9. Hex (free Community tier) + fallback

**Hex Community is free forever.** Known limits to design around: up to ~5 projects, ~3 project authors, **project-level** data connection (configure the RDS Postgres connection inside the project), **7-day** version history, **no scheduled runs**, email-only support.

That's fine here: you don't need Hex scheduling — **Airflow refreshes the data; Hex queries RDS live.** Build three apps, all reading `marts.*` only (governance story):
1. **Research / Analyst** — single-security deep dive. Param `symbol`: price + Bollinger bands, RSI/MACD panels, returns table, latest PIT fundamentals, recent earnings surprises, sentiment trend.
2. **Risk** — watchlist risk monitor: rolling 20/60-day vol, beta vs. S&P, max drawdown, distance from 52-week high, sector concentration. Reads `mart_risk_monitor`.
3. **Leadership** — watchlist performance: Day/WTD/MTD/YTD returns, top movers, sector heatmap, sentiment snapshot. Reads `mart_watchlist_daily`.

Capture screenshots/GIFs for the README.

**Free web-app fallback (if Hex limits annoy you):** **Evidence.dev** — SQL-as-BI, builds a static site from queries against RDS; deploy the static build to **S3 static hosting** for pennies. Bonus AE signal (BI-as-code, version-controlled). Or a small **Streamlit** app on the EC2.

---

## 10. Build sequence (2-day timeline)

**Day 1 — data flowing, models built**
| Step | Done when |
|---|---|
| Decide AV plan + universe/history (§1) | You know your symbol list and date range |
| AWS: create S3 bucket, RDS micro, EC2 small, security groups; set $25 budget alert | `psql` connects to RDS from EC2/laptop |
| Python EL: client (retry/rate-limit), pydantic schemas, S3 archive, S3→RDS raw upsert, pytest | Re-running a date range produces no dupes; `raw.*` populated |
| dbt skeleton + sources + freshness + `stg_av__*` + schema tests | `dbt build --select staging` green; staging documented |
| Intermediate models (returns, technicals pivot, sentiment, macro, sector) | Spot-checks pass on known dates |

**Day 2 — marts, orchestration, CI, BI, polish**
| Step | Done when |
|---|---|
| Dims, `fct_daily_equity_metrics` (incremental), snapshot, singular tests, contracts | Full `dbt build` green; incremental re-run idempotent |
| Airflow on EC2: docker-compose (LocalExecutor), `equities_daily` DAG, one backfill run | DAG runs end-to-end; a failed test halts downstream |
| GitHub Actions CI (Postgres service container) + branch protection | PR shows green; a deliberately broken model fails CI |
| Hex: 3 apps on RDS marts, parameterized; screenshots | All three render live |
| README: architecture diagram, ERD, design decisions, screenshots, run guide | A stranger understands it in 5 minutes |
| **Stop RDS + EC2** | Billing stops |

---

## 11. Definition of done (interview-grade)

- `dbt build` runs every model **and** every test green from a clean clone.
- Zero models without a documented grain and ≥1 test.
- `dbt docs` lineage shows clean staging → intermediate → marts (no mart references staging/source directly).
- Look-ahead-bias fix is provable (a test enforces as-of fundamentals joins).
- README leads with: problem, architecture diagram, three dashboards (screenshots), and a "design decisions" section naming the EL/ELT split, PIT correctness, and the no-fabrication rule.
- CI is green and visibly gates merges; repo is public.
- A documented cost note proving the whole thing runs under $50/mo.

---

## 12. Stretch goals (only after DoD)

- `infra/terraform/` provisioning S3 + RDS + EC2 + security groups (IaC signal) — keep it small and clean.
- `elementary-data` for freshness/anomaly monitoring + an observability report.
- dbt `exposures` pointing at the three Hex apps (closes lineage to BI).
- RDS index tuning on `(symbol, date)` for the fact; prove query speedup.
- Full-history backfill (`outputsize=full`) with incremental-vs-full-refresh parity check.

---

## 13. Things to deliberately avoid (scope discipline)

- No ML, no prediction, no Flask app, no LLM analysis — that's what made the original a generalist project.
- **No MWAA / no Astro Cloud** — both cost real money. Self-host Airflow or run it locally.
- Don't build on the AV **options** endpoint until you verify it returns real data (it's flaky/premium).
- Don't transform in Python "because it's easier" — transformations go in dbt.
- Don't let marts reference staging/sources directly — go through intermediate/dims.
- Don't fabricate or silently impute. Forward-fill **only** macro indicators, and document it.
- Don't ship stale/broken tests (the original repo's lethal mistake). If a test can't run, fix or delete it.
- **Don't use Python 3.14** — dbt isn't compatible yet. 3.13 only.
- Don't leave RDS/EC2 running. Stop them between sessions.
