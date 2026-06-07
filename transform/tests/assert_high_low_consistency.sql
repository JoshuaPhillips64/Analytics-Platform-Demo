-- Fail any row where the daily OHLC is internally inconsistent.
select
    symbol,
    date,
    open,
    high,
    low,
    close
from {{ ref('stg_av__daily_prices') }}
where high < low
    or high < open
    or high < close
    or low > open
    or low > close
