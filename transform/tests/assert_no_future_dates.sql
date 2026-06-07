-- Fail if the fact contains any date in the future.
select symbol, date
from {{ ref('fct_daily_equity_metrics') }}
where date > current_date
