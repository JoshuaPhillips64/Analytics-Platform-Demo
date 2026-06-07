-- Conformed security dimension. company_name/is_active from the watchlist seed;
-- sector/industry from the latest point-in-time fundamentals record (intermediate
-- layer, not staging — rule #5).

with watchlist as (
    select symbol, company_name, is_active
    from {{ ref('security_watchlist') }}
),

current_fundamentals as (
    select
        symbol,
        sector,
        industry,
        row_number() over (partition by symbol order by valid_from desc) as rn
    from {{ ref('int_fundamentals__point_in_time') }}
)

select
    cast(watchlist.symbol as text) as symbol,
    cast(watchlist.company_name as text) as company_name,
    cast(current_fundamentals.sector as text) as sector,
    cast(current_fundamentals.industry as text) as industry,
    cast(watchlist.is_active as boolean) as is_active
from watchlist
left join current_fundamentals
    on watchlist.symbol = current_fundamentals.symbol and current_fundamentals.rn = 1
