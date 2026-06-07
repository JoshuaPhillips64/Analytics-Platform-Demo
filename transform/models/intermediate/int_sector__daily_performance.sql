-- Sector-relative performance: each active security's sector ETF daily return,
-- per trading date. Sector membership is slowly-changing reference data, so we
-- map on the security's latest known sector (distinct from the point-in-time
-- *financial* fundamentals, which are as-of joined in the fact).
--
-- Free-tier note: only the XLP ETF is loaded, so securities whose sector maps to
-- an unloaded ETF (e.g. HEALTHCARE -> XLV) get NULL sector_return until those
-- ETF prices are backfilled.

with active_securities as (
    select symbol
    from {{ ref('security_watchlist') }}
    where is_active
),

security_sector as (
    select
        symbol,
        sector,
        row_number() over (partition by symbol order by loaded_at desc) as rn
    from {{ ref('stg_av__company_overview') }}
),

etf_returns as (
    select
        symbol as etf_symbol,
        date,
        close / nullif(lag(close) over (partition by symbol order by date), 0) - 1 as etf_daily_return
    from {{ ref('stg_av__daily_prices') }}
    where symbol in (select sem.etf_symbol from {{ ref('sector_etf_map') }} as sem)
),

security_days as (
    select prices.symbol, prices.date
    from {{ ref('stg_av__daily_prices') }} as prices
    inner join active_securities using (symbol)
)

select
    sd.symbol,
    sd.date,
    ss.sector,
    m.etf_symbol,
    er.etf_daily_return as sector_return
from security_days as sd
left join security_sector as ss on sd.symbol = ss.symbol and ss.rn = 1
left join {{ ref('sector_etf_map') }} as m on ss.sector = m.sector
left join etf_returns as er on m.etf_symbol = er.etf_symbol and sd.date = er.date
