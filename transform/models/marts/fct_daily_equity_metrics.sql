{{
    config(
        materialized='incremental',
        unique_key=['symbol', 'date'],
        incremental_strategy='delete+insert',
        on_schema_change='fail',
    )
}}

-- One row per active security per trading day, fully enriched. The star model.
-- Fundamentals are joined AS OF the trading date (valid_from/valid_to), and
-- earnings AS OF reported_date — so nothing from the future leaks backwards
-- (the legacy look-ahead bug, designed out). For dates before fundamentals were
-- first snapshotted, those columns are NULL by design — never back-stamped.

with base as (
    select returns.*
    from {{ ref('int_prices__daily_returns') }} as returns
    inner join {{ ref('dim_security') }} as sec on returns.symbol = sec.symbol and sec.is_active
    {% if is_incremental() %}
    where returns.date >= (select max(t.date) from {{ this }} as t)
    {% endif %}
),

technicals as (select * from {{ ref('int_technicals__pivoted') }}),

sentiment as (select * from {{ ref('int_sentiment__daily') }}),

economic as (select * from {{ ref('int_economic__daily') }}),

sector_perf as (select * from {{ ref('int_sector__daily_performance') }})

select
    cast(base.symbol as text) as symbol,
    cast(base.date as date) as date,
    cast(base.close as numeric) as close,
    cast(base.prev_close as numeric) as prev_close,
    cast(base.daily_return as numeric) as daily_return,
    cast(base.log_return as numeric) as log_return,
    cast(base.return_5d as numeric) as return_5d,
    cast(base.return_20d as numeric) as return_20d,
    cast(base.return_60d as numeric) as return_60d,
    cast(base.volatility_20d as numeric) as volatility_20d,
    cast(base.high_52w as numeric) as high_52w,
    cast(base.low_52w as numeric) as low_52w,
    cast(technicals.rsi as numeric) as rsi,
    cast(technicals.macd as numeric) as macd,
    cast(technicals.macd_signal as numeric) as macd_signal,
    cast(technicals.macd_hist as numeric) as macd_hist,
    cast(technicals.adx as numeric) as adx,
    cast(technicals.bb_upper as numeric) as bb_upper,
    cast(technicals.bb_middle as numeric) as bb_middle,
    cast(technicals.bb_lower as numeric) as bb_lower,
    cast(sentiment.avg_ticker_sentiment as numeric) as avg_ticker_sentiment,
    cast(sentiment.avg_overall_sentiment as numeric) as avg_overall_sentiment,
    cast(coalesce(sentiment.article_count, 0) as integer) as article_count,
    cast(economic.real_gdp as numeric) as real_gdp,
    cast(economic.inflation as numeric) as inflation,
    cast(economic.unemployment as numeric) as unemployment,
    cast(sector_perf.sector as text) as sector,
    cast(sector_perf.sector_return as numeric) as sector_return,
    cast(pit.market_cap as numeric) as market_cap,
    cast(pit.pe_ratio as numeric) as pe_ratio,
    cast(pit.dividend_yield as numeric) as dividend_yield,
    cast(pit.beta as numeric) as beta,
    cast(earnings.reported_eps as numeric) as reported_eps,
    cast(earnings.surprise as numeric) as earnings_surprise,
    cast(earnings.surprise_percentage as numeric) as earnings_surprise_pct,
    cast(earnings.reported_date as date) as earnings_reported_date
from base
left join technicals on base.symbol = technicals.symbol and base.date = technicals.date
left join sentiment on base.symbol = sentiment.symbol and base.date = sentiment.date
left join economic on base.date = economic.date
left join sector_perf on base.symbol = sector_perf.symbol and base.date = sector_perf.date
left join {{ ref('int_fundamentals__point_in_time') }} as pit
    on
        base.symbol = pit.symbol
        and base.date >= cast(pit.valid_from as date)
        and base.date < cast(pit.valid_to as date)
left join lateral (
    select
        e.reported_eps,
        e.surprise,
        e.surprise_percentage,
        e.reported_date
    from {{ ref('int_earnings__reported') }} as e
    where e.symbol = base.symbol and e.reported_date <= base.date
    order by e.reported_date desc
    limit 1
) as earnings on true
