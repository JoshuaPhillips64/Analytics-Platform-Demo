# Airflow image with the dbt stack + extract EL deps layered on. The project
# code (extract/, transform/ incl. dbt_packages) is mounted at runtime, so this
# image stays generic and needs no network at build beyond pip.
FROM apache/airflow:2.10.5-python3.12

COPY requirements-airflow.txt /tmp/requirements-airflow.txt
RUN pip install --no-cache-dir -r /tmp/requirements-airflow.txt
