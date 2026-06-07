-- Union the four indicator sources into a long shape: one row per
-- (symbol, date, indicator). MACD and Bollinger Bands fan out into multiple
-- indicator rows. No business logic here — just typing + reshaping.

with rsi as (
    select
        symbol,
        date::date as date,
        'rsi' as indicator,
        {{ av_numeric('record', 'RSI') }} as value
    from {{ source('alpha_vantage', 'av_rsi') }}
),

macd as (
    select symbol, date::date as date, 'macd' as indicator, {{ av_numeric('record', 'MACD') }} as value
    from {{ source('alpha_vantage', 'av_macd') }}
    union all
    select symbol, date::date as date, 'macd_signal' as indicator, {{ av_numeric('record', 'MACD_Signal') }} as value
    from {{ source('alpha_vantage', 'av_macd') }}
    union all
    select symbol, date::date as date, 'macd_hist' as indicator, {{ av_numeric('record', 'MACD_Hist') }} as value
    from {{ source('alpha_vantage', 'av_macd') }}
),

adx as (
    select
        symbol,
        date::date as date,
        'adx' as indicator,
        {{ av_numeric('record', 'ADX') }} as value
    from {{ source('alpha_vantage', 'av_adx') }}
),

bbands as (
    select symbol, date::date as date, 'bb_upper' as indicator, {{ av_numeric('record', 'Real Upper Band') }} as value
    from {{ source('alpha_vantage', 'av_bbands') }}
    union all
    select symbol, date::date as date, 'bb_middle' as indicator, {{ av_numeric('record', 'Real Middle Band') }} as value
    from {{ source('alpha_vantage', 'av_bbands') }}
    union all
    select symbol, date::date as date, 'bb_lower' as indicator, {{ av_numeric('record', 'Real Lower Band') }} as value
    from {{ source('alpha_vantage', 'av_bbands') }}
)

select * from rsi
union all
select * from macd
union all
select * from adx
union all
select * from bbands
