-- Quarterly earnings as point-in-time events: a report is only "known" on/after
-- its reported_date. The fact as-of joins the latest report with
-- reported_date <= the trading date, so earnings never appear before they were
-- public (no look-ahead). Grain: (symbol, fiscal_date_ending).

select
    symbol,
    fiscal_date_ending,
    reported_date,
    reported_eps,
    estimated_eps,
    surprise,
    surprise_percentage
from {{ ref('stg_av__earnings') }}
where
    report_type = 'quarterly'
    and reported_date is not null
