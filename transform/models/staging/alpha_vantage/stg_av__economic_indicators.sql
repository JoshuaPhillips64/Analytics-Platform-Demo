-- Union the three macro indicator sources into one long shape:
-- (indicator, period_date, value).

with real_gdp as (
    select 'real_gdp' as indicator, date::date as period_date, {{ av_numeric('record', 'value') }} as value
    from {{ source('alpha_vantage', 'av_real_gdp') }}
),

inflation as (
    select 'inflation' as indicator, date::date as period_date, {{ av_numeric('record', 'value') }} as value
    from {{ source('alpha_vantage', 'av_inflation') }}
),

unemployment as (
    select 'unemployment' as indicator, date::date as period_date, {{ av_numeric('record', 'value') }} as value
    from {{ source('alpha_vantage', 'av_unemployment') }}
)

select * from real_gdp
union all
select * from inflation
union all
select * from unemployment
