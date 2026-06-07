{#
  Use the model's configured +schema verbatim (raw/staging/intermediate/marts),
  instead of dbt's default of prefixing it with the target schema. The dbt role
  has CREATE on these schemas (see infra/sql/bootstrap.sql). Models without a
  custom schema fall back to the target's default schema.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
