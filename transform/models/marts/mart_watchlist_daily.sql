-- Leadership app: watchlist performance with period-to-date returns + a sentiment
-- snapshot. Grain: (symbol, date). Reads the fact + dim_security only.

with fct as (
    select * from {{ ref('fct_daily_equity_metrics') }}
),

buckets as (
    select
        symbol,
        date,
        close,
        daily_return,
        sector,
        rsi,
        avg_ticker_sentiment,
        article_count,
        date_trunc('week', cast(date as timestamp)) as week_bucket,
        date_trunc('month', cast(date as timestamp)) as month_bucket,
        date_trunc('year', cast(date as timestamp)) as year_bucket
    from fct
),

period_opens as (
    select
        buckets.*,
        first_value(close) over (partition by symbol, week_bucket order by date) as week_open,
        first_value(close) over (partition by symbol, month_bucket order by date) as month_open,
        first_value(close) over (partition by symbol, year_bucket order by date) as year_open
    from buckets
)

select
    period_opens.symbol,
    dim_security.company_name,
    period_opens.sector,
    period_opens.date,
    period_opens.close,
    period_opens.daily_return,
    period_opens.close / nullif(period_opens.week_open, 0) - 1 as wtd_return,
    period_opens.close / nullif(period_opens.month_open, 0) - 1 as mtd_return,
    period_opens.close / nullif(period_opens.year_open, 0) - 1 as ytd_return,
    period_opens.rsi,
    period_opens.avg_ticker_sentiment,
    period_opens.article_count
from period_opens
left join {{ ref('dim_security') }} as dim_security on period_opens.symbol = dim_security.symbol
