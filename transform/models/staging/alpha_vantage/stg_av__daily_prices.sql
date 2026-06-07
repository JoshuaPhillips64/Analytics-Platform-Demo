with source as (
    select * from {{ source('alpha_vantage', 'av_daily_prices') }}
),

renamed as (
    select
        symbol,
        date::date as date,
        {{ av_numeric('record', '1. open') }} as open,
        {{ av_numeric('record', '2. high') }} as high,
        {{ av_numeric('record', '3. low') }} as low,
        {{ av_numeric('record', '4. close') }} as close,
        -- premium ADJUSTED puts volume at '6.'; free DAILY puts it at '5.'
        coalesce(
            {{ av_numeric('record', '6. volume') }},
            {{ av_numeric('record', '5. volume') }}
        ) as volume,
        -- premium-only fields; NULL on the free tier (never fabricated)
        {{ av_numeric('record', '5. adjusted close') }} as adjusted_close,
        {{ av_numeric('record', '7. dividend amount') }} as dividend_amount,
        {{ av_numeric('record', '8. split coefficient') }} as split_coefficient,
        source_s3_key,
        loaded_at
    from source
)

select * from renamed
