{#
  SCD2 snapshot of company fundamentals — THE look-ahead-bias fix.

  Each EL run lands current fundamentals in stg_av__company_overview. This
  snapshot records when each field combination was first seen and until when it
  was valid, so downstream models can join fundamentals *as of* a given date
  instead of stamping today's values onto all history (the legacy bug).
#}
{% snapshot snap_company_fundamentals %}
    {{
        config(
            target_schema='snapshots',
            unique_key='symbol',
            strategy='check',
            check_cols=[
                'sector', 'industry', 'market_cap', 'pe_ratio', 'peg_ratio',
                'book_value', 'eps', 'dividend_per_share', 'dividend_yield',
                'beta', 'profit_margin', 'week_52_high', 'week_52_low',
            ],
        )
    }}

    with latest as (
        select
            *,
            row_number() over (partition by symbol order by loaded_at desc) as rn
        from {{ ref('stg_av__company_overview') }}
    )

    select
        symbol, company_name, sector, industry, exchange, currency, country,
        market_cap, pe_ratio, peg_ratio, book_value, eps, dividend_per_share,
        dividend_yield, beta, profit_margin, week_52_high, week_52_low
    from latest
    where rn = 1

{% endsnapshot %}
