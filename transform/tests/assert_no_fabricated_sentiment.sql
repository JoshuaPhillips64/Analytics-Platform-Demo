-- Fail if sentiment is present when there were no articles. Missing sentiment
-- must stay NULL — never fabricated (golden rule #2).
select symbol, date, avg_ticker_sentiment, article_count
from {{ ref('fct_daily_equity_metrics') }}
where article_count = 0 and avg_ticker_sentiment is not null
