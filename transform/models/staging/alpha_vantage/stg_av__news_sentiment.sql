with source as (
    select * from {{ source('alpha_vantage', 'av_news_sentiment') }}
),

parsed as (
    select
        source.symbol,
        source.url,
        to_timestamp(source.record ->> 'time_published', 'YYYYMMDD"T"HH24MISS') as article_published_at,
        source.record ->> 'title' as title,
        source.record ->> 'source' as news_source,
        {{ av_numeric('source.record', 'overall_sentiment_score') }} as overall_sentiment_score,
        source.record ->> 'overall_sentiment_label' as overall_sentiment_label,
        -- the sentiment score Alpha Vantage assigned to THIS ticker for the article
        ticker.value as ticker_sentiment_score,
        source.loaded_at,
        source.source_s3_key
    from source
    left join lateral (
        select nullif(elem ->> 'ticker_sentiment_score', '')::numeric as value
        from jsonb_array_elements(source.record -> 'ticker_sentiment') as elem
        where elem ->> 'ticker' = source.symbol
        order by nullif(elem ->> 'relevance_score', '')::numeric desc nulls last
        limit 1
    ) as ticker on true
)

select * from parsed
