-- Pivot the long technical-indicator staging model to one row per (symbol, date)
-- with a column per indicator. Free tier: only RSI is loaded, so macd/adx/bbands
-- columns are NULL until those endpoints are backfilled (no model change needed).

select
    symbol,
    date,
    max(value) filter (where indicator = 'rsi') as rsi,
    max(value) filter (where indicator = 'macd') as macd,
    max(value) filter (where indicator = 'macd_signal') as macd_signal,
    max(value) filter (where indicator = 'macd_hist') as macd_hist,
    max(value) filter (where indicator = 'adx') as adx,
    max(value) filter (where indicator = 'bb_upper') as bb_upper,
    max(value) filter (where indicator = 'bb_middle') as bb_middle,
    max(value) filter (where indicator = 'bb_lower') as bb_lower
from {{ ref('stg_av__technical_indicators') }}
group by symbol, date
