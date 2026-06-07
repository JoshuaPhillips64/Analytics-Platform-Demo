-- Returns, rolling volatility, and 52-week high/low via window functions.
-- Free-tier note: only ~100 trading days are loaded, so the 252-row "52-week"
-- window and 60-day returns use whatever history is available (partial early on).
-- Returns use the (non-adjusted) close on the free tier.

with prices as (
    select symbol, date, close
    from {{ ref('stg_av__daily_prices') }}
),

returns as (
    select
        symbol,
        date,
        close,
        lag(close) over w as prev_close,
        close / nullif(lag(close) over w, 0) - 1 as daily_return,
        ln(close / nullif(lag(close) over w, 0)) as log_return,
        close / nullif(lag(close, 5) over w, 0) - 1 as return_5d,
        close / nullif(lag(close, 20) over w, 0) - 1 as return_20d,
        close / nullif(lag(close, 60) over w, 0) - 1 as return_60d,
        max(close) over w_52w as high_52w,
        min(close) over w_52w as low_52w
    from prices
    window
        w as (partition by symbol order by date),
        w_52w as (partition by symbol order by date rows between 251 preceding and current row)
)

select
    symbol,
    date,
    close,
    prev_close,
    daily_return,
    log_return,
    return_5d,
    return_20d,
    return_60d,
    high_52w,
    low_52w,
    stddev_samp(daily_return) over (
        partition by symbol order by date rows between 19 preceding and current row
    ) as volatility_20d
from returns
