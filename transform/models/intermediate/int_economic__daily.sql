-- Forward-fill macro indicators onto the trading calendar (as-of join: each date
-- gets the most recent period value <= that date). Forward-filling is applied
-- ONLY to macro indicators here, and it is documented — prices/returns are never
-- forward-filled (golden rule #8). The trading calendar is the set of dates for
-- which we have prices.

with calendar as (
    select distinct date from {{ ref('stg_av__daily_prices') }}
),

economic as (
    select indicator, period_date, value
    from {{ ref('stg_av__economic_indicators') }}
),

as_of as (
    select
        calendar.date,
        economic.indicator,
        economic.value,
        row_number() over (
            partition by calendar.date, economic.indicator
            order by economic.period_date desc
        ) as rn
    from calendar
    inner join economic on calendar.date >= economic.period_date
)

select
    date,
    max(value) filter (where indicator = 'real_gdp') as real_gdp,
    max(value) filter (where indicator = 'inflation') as inflation,
    max(value) filter (where indicator = 'unemployment') as unemployment
from as_of
where rn = 1
group by date
