# BI — Hex Community apps

Three Hex apps read `marts.*` **only** (never staging/raw) — a clean governance
boundary. Hex Community is free; it queries RDS live (Airflow refreshes the data,
so no Hex scheduling is needed).

## 1. Connect Hex to RDS (project-level connection)

1. Make RDS reachable from Hex: add Hex's egress IPs (or your IP for testing) to
   `db_allowed_cidrs` in `infra/terraform/terraform.tfvars` and `terraform apply`,
   and ensure `db_publicly_accessible = true`.
2. Create a **read-only** role for BI (least privilege — Hex never needs write):
   ```sql
   -- run as the master/dbt user
   create role hex_ro login password 'choose-a-strong-password';
   grant connect on database equities to hex_ro;
   grant usage on schema marts to hex_ro;
   grant select on all tables in schema marts to hex_ro;
   alter default privileges in schema marts grant select on tables to hex_ro;
   ```
3. In Hex: add a Postgres data connection at the **project** level — host = RDS
   endpoint, db `equities`, user `hex_ro`, **SSL required**.

## 2. Research / Analyst app (param: `symbol`)

Single-security deep dive. Add a Hex text/dropdown input named `symbol`.

```sql
-- price + RSI + returns + sentiment time series
select date, close, daily_return, return_20d, volatility_20d,
       rsi, avg_ticker_sentiment, article_count
from marts.fct_daily_equity_metrics
where symbol = {{ symbol }}
order by date;

-- latest known point-in-time fundamentals (NULL on the free tier until snapshots accrue)
select symbol, market_cap, pe_ratio, dividend_yield, beta
from marts.fct_daily_equity_metrics
where symbol = {{ symbol }} and market_cap is not null
order by date desc
limit 1;

-- recent reported earnings
select distinct earnings_reported_date, reported_eps, earnings_surprise_pct
from marts.fct_daily_equity_metrics
where symbol = {{ symbol }} and earnings_reported_date is not null
order by earnings_reported_date desc
limit 8;
```

## 3. Risk app (`mart_risk_monitor`)

```sql
-- latest risk snapshot per security
select distinct on (symbol)
       symbol, company_name, sector, date,
       volatility_20d, volatility_60d, beta,
       distance_from_52w_high, current_drawdown, max_drawdown_to_date
from marts.mart_risk_monitor
order by symbol, date desc;

-- volatility trend for a charted series
select symbol, date, volatility_20d, volatility_60d
from marts.mart_risk_monitor
order by symbol, date;
```

## 4. Leadership app (`mart_watchlist_daily`)

```sql
-- latest performance per security (Day/WTD/MTD/YTD)
select distinct on (symbol)
       symbol, company_name, sector, date,
       daily_return, wtd_return, mtd_return, ytd_return,
       rsi, avg_ticker_sentiment, article_count
from marts.mart_watchlist_daily
order by symbol, date desc;

-- top movers on the latest day
select symbol, company_name, daily_return
from marts.mart_watchlist_daily
where date = (select max(date) from marts.mart_watchlist_daily)
order by daily_return desc;
```

## 5. Capture screenshots

Add screenshots/GIFs of each app to `docs/` (or an `images/` folder) and link them
from the README's BI section.

> Free-tier note: with only KO/JNJ/PG active and ~100 days of non-adjusted prices,
> charts are shorter and some columns (beta, sector_return) are NULL until premium
> data / sector-ETF prices are loaded. The apps render regardless.
