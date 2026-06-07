-- Daily mean sentiment + article count per security. Averages over NULL ticker
-- scores yield NULL, never 0 — and days with no articles simply produce no row
-- here (they become NULL when left-joined onto the trading calendar in the fact).
-- No fabrication (golden rule #2); enforced by assert_no_fabricated_sentiment.

select
    symbol,
    (article_published_at at time zone 'UTC')::date as date,
    avg(ticker_sentiment_score) as avg_ticker_sentiment,
    avg(overall_sentiment_score) as avg_overall_sentiment,
    count(*) as article_count
from {{ ref('stg_av__news_sentiment') }}
where article_published_at is not null
group by symbol, (article_published_at at time zone 'UTC')::date
