with source as (
    select * from {{ source('alpha_vantage', 'av_company_overview') }}
),

renamed as (
    select
        symbol,
        record ->> 'Name' as company_name,
        record ->> 'Sector' as sector,
        record ->> 'Industry' as industry,
        record ->> 'Exchange' as exchange,
        record ->> 'Currency' as currency,
        record ->> 'Country' as country,
        {{ av_numeric('record', 'MarketCapitalization') }} as market_cap,
        {{ av_numeric('record', 'PERatio') }} as pe_ratio,
        {{ av_numeric('record', 'PEGRatio') }} as peg_ratio,
        {{ av_numeric('record', 'BookValue') }} as book_value,
        {{ av_numeric('record', 'EPS') }} as eps,
        {{ av_numeric('record', 'DividendPerShare') }} as dividend_per_share,
        {{ av_numeric('record', 'DividendYield') }} as dividend_yield,
        {{ av_numeric('record', 'Beta') }} as beta,
        {{ av_numeric('record', 'ProfitMargin') }} as profit_margin,
        {{ av_numeric('record', '52WeekHigh') }} as week_52_high,
        {{ av_numeric('record', '52WeekLow') }} as week_52_low,
        loaded_at,
        source_s3_key
    from source
)

select * from renamed
