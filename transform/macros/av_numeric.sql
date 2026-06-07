{#
  Cast a jsonb field to numeric, mapping Alpha Vantage's missing-value sentinels
  ('None', '-', '.', '') to NULL. Missing stays NULL — never fabricated (rule #2).
  Usage: {{ av_numeric('record', 'PERatio') }}
#}
{% macro av_numeric(json_col, key) -%}
    nullif(nullif(nullif(nullif({{ json_col }} ->> '{{ key }}', 'None'), '-'), '.'), '')::numeric
{%- endmacro %}
