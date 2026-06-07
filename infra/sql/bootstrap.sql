-- Bootstrap the RDS database: create the four dbt schemas and an application
-- role. DDL only — no transformation logic (golden rule #1). Run once after
-- `terraform apply`, connected as the RDS master user. Pass the dbt role's
-- password as a RAW value (no surrounding quotes); psql quotes it safely:
--
--   psql 'host=<rds_address> port=5432 dbname=equities user=postgres sslmode=require' \
--        -v dbt_password='choose-a-strong-dbt-password' \
--        -f infra/sql/bootstrap.sql
--
-- NOTE: psql variable interpolation does NOT happen inside dollar-quoted ($$)
-- blocks, so the role is created via \gexec (which interpolates correctly).

\set ON_ERROR_STOP on

-- Application role used by both the Python loader (writes raw.*) and dbt
-- (builds staging/intermediate/marts). Split into two roles later if desired.
-- CREATE ROLE has no IF NOT EXISTS, so guard with a WHERE NOT EXISTS + \gexec.
-- format(%L, :'dbt_password') -> a safely single-quoted password literal.
SELECT format('CREATE ROLE dbt LOGIN PASSWORD %L', :'dbt_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'dbt')
\gexec

-- Schemas owned by the dbt role.
CREATE SCHEMA IF NOT EXISTS raw          AUTHORIZATION dbt;
CREATE SCHEMA IF NOT EXISTS staging      AUTHORIZATION dbt;
CREATE SCHEMA IF NOT EXISTS intermediate AUTHORIZATION dbt;
CREATE SCHEMA IF NOT EXISTS marts        AUTHORIZATION dbt;

-- Let dbt connect to the database and work in each schema.
GRANT CONNECT ON DATABASE equities TO dbt;
GRANT USAGE, CREATE ON SCHEMA raw, staging, intermediate, marts TO dbt;

-- Confirm.
\echo 'Schemas present:'
\dn
