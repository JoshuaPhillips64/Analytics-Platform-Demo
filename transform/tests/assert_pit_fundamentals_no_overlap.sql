-- Fail if any symbol has overlapping SCD2 fundamentals windows. Proves the
-- point-in-time join can never match two fundamentals versions for one date.
select
    a.symbol,
    a.valid_from,
    a.valid_to
from {{ ref('int_fundamentals__point_in_time') }} as a
inner join {{ ref('int_fundamentals__point_in_time') }} as b
    on a.symbol = b.symbol
    and a.valid_from <> b.valid_from
    and a.valid_from < b.valid_to
    and b.valid_from < a.valid_to
