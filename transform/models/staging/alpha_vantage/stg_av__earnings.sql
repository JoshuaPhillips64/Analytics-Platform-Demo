with source as (
    select * from {{ source('alpha_vantage', 'av_earnings') }}
),

renamed as (
    select
        symbol,
        fiscal_date_ending::date as fiscal_date_ending,
        report_type,
        {{ av_numeric('record', 'reportedEPS') }} as reported_eps,
        {{ av_numeric('record', 'estimatedEPS') }} as estimated_eps,
        {{ av_numeric('record', 'surprise') }} as surprise,
        {{ av_numeric('record', 'surprisePercentage') }} as surprise_percentage,
        nullif(record ->> 'reportedDate', '')::date as reported_date,
        loaded_at,
        source_s3_key
    from source
)

select * from renamed
