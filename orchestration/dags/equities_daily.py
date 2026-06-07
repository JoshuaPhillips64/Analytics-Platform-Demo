"""Daily equities pipeline: extract+load raw -> source freshness -> snapshot ->
dbt build (run + test) -> notify.

A failed dbt test fails `dbt build`, which fails the task; downstream tasks
(notify) are skipped — bad data never propagates (Phase 6 gate). The EL is atomic
per endpoint (archive to S3 then upsert to RDS in one step), so extract and load
are a single task here rather than two.

dbt writes to /tmp (the project is mounted read-only). On the free AV tier, a
daily-cap hit is a soft warning, so the extract step stays green.
"""

from __future__ import annotations

import pendulum
from airflow.models.dag import DAG
from airflow.operators.bash import BashOperator

PROJECT = "/opt/airflow/project"
TRANSFORM = f"{PROJECT}/transform"
# dbt target/log dirs must be writable (project mount is read-only).
DBT_FLAGS = "--profiles-dir . --target-path /tmp/dbt/target --log-path /tmp/dbt/logs"

default_args = {
    "retries": 1,
    "retry_delay": pendulum.duration(minutes=2),
}

with DAG(
    dag_id="equities_daily",
    description="Alpha Vantage -> S3 -> RDS raw -> dbt models/tests -> notify",
    schedule="0 6 * * 1-6",  # weekdays + Sat, after US market close (UTC)
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    catchup=False,
    default_args=default_args,
    tags=["equities", "dbt", "alpha_vantage"],
) as dag:
    extract_and_load = BashOperator(
        task_id="extract_and_load",
        # Daily incremental: economic indicators + active-symbol prices/news.
        bash_command=(
            f"cd {PROJECT} && python -m extract.run_extract "
            "--symbols KO,JNJ,PG --endpoints prices,news,economic"
        ),
    )

    dbt_source_freshness = BashOperator(
        task_id="dbt_source_freshness",
        # Freshness is informational here; don't fail the run on a stale warning.
        bash_command=f"cd {TRANSFORM} && dbt source freshness {DBT_FLAGS} || true",
    )

    dbt_snapshot = BashOperator(
        task_id="dbt_snapshot",
        bash_command=f"cd {TRANSFORM} && dbt snapshot {DBT_FLAGS}",
    )

    dbt_build = BashOperator(
        task_id="dbt_build",
        # Runs every model AND every test. A failing test => non-zero => task fails
        # => notify is skipped. Snapshots already ran above, so exclude them here.
        bash_command=f"cd {TRANSFORM} && dbt build {DBT_FLAGS} --exclude resource_type:snapshot",
    )

    notify = BashOperator(
        task_id="notify",
        bash_command='echo "equities_daily completed successfully"',
    )

    extract_and_load >> dbt_source_freshness >> dbt_snapshot >> dbt_build >> notify
