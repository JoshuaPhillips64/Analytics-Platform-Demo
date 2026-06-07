-- Calendar dimension spanning the loaded price history. is_trading_day is a
-- weekday approximation (Mon–Fri); has_prices marks dates we actually loaded.
-- Sourced from the intermediate layer (not staging) to respect layering (rule #5).

with spine as (
    {{ dbt_utils.date_spine(
        datepart="day",
        start_date="(select min(date) from " ~ ref('int_prices__daily_returns') ~ ")",
        end_date="(select max(date) + 1 from " ~ ref('int_prices__daily_returns') ~ ")"
    ) }}
),

price_dates as (
    select distinct date from {{ ref('int_prices__daily_returns') }}
)

select
    cast(spine.date_day as date) as date_day,
    cast(extract(isodow from spine.date_day) as integer) as day_of_week,
    cast(to_char(spine.date_day, 'Day') as text) as day_name,
    cast(extract(isodow from spine.date_day) < 6 as boolean) as is_trading_day,
    cast(price_dates.date is not null as boolean) as has_prices,
    cast(extract(week from spine.date_day) as integer) as week_of_year,
    cast(extract(month from spine.date_day) as integer) as month_number,
    cast(to_char(spine.date_day, 'Month') as text) as month_name,
    cast(extract(quarter from spine.date_day) as integer) as quarter,
    cast(extract(year from spine.date_day) as integer) as year_number,
    cast(
        spine.date_day = (date_trunc('month', spine.date_day) + interval '1 month - 1 day') as boolean
    ) as is_month_end
from spine
left join price_dates on price_dates.date = cast(spine.date_day as date)
