-- Point-in-time fundamentals from the SCD2 snapshot, exposed with valid_from /
-- valid_to for as-of joins. The fact joins these so each historical date sees the
-- fundamentals that were current AT THAT DATE — never today's values stamped
-- backwards (the legacy look-ahead bug). For dates before the first snapshot
-- capture, fundamentals are genuinely unknown and join to NULL (by design).

select
    symbol,
    company_name,
    sector,
    industry,
    market_cap,
    pe_ratio,
    peg_ratio,
    book_value,
    eps,
    dividend_per_share,
    dividend_yield,
    beta,
    profit_margin,
    week_52_high,
    week_52_low,
    dbt_valid_from as valid_from,
    coalesce(dbt_valid_to, '9999-12-31'::timestamp) as valid_to
from {{ ref('snap_company_fundamentals') }}
