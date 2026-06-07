-- Risk app: rolling volatility, beta, drawdown, and distance from the 52-week
-- high. Grain: (symbol, date). Reads the fact + dim_security only.
-- Free-tier note: beta comes from fundamentals (NULL until snapshots cover the
-- date), and sector_return-based metrics are NULL until sector ETF prices load.

with fct as (
    select * from {{ ref('fct_daily_equity_metrics') }}
),

drawdown as (
    select
        fct.symbol,
        fct.date,
        fct.close,
        fct.high_52w,
        fct.beta,
        fct.volatility_20d,
        fct.daily_return,
        max(fct.close) over (partition by fct.symbol order by fct.date) as running_peak
    from fct
)

select
    drawdown.symbol,
    dim_security.company_name,
    dim_security.sector,
    drawdown.date,
    drawdown.close,
    drawdown.volatility_20d,
    stddev_samp(drawdown.daily_return) over (
        partition by drawdown.symbol order by drawdown.date rows between 59 preceding and current row
    ) as volatility_60d,
    drawdown.beta,
    drawdown.close / nullif(drawdown.high_52w, 0) - 1 as distance_from_52w_high,
    drawdown.close / nullif(drawdown.running_peak, 0) - 1 as current_drawdown,
    min(drawdown.close / nullif(drawdown.running_peak, 0) - 1) over (
        partition by drawdown.symbol order by drawdown.date
    ) as max_drawdown_to_date
from drawdown
left join {{ ref('dim_security') }} as dim_security on drawdown.symbol = dim_security.symbol
