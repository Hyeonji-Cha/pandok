# 로컬 Airflow에 PANDOK 코드와 Snowflake 연결 기능을 포함한다.
FROM apache/airflow:3.3.1-python3.12

COPY --chown=airflow:root airflow/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY --chown=airflow:root pyproject.toml README.md /opt/pandok/
COPY --chown=airflow:root src /opt/pandok/src
COPY --chown=airflow:root contracts /opt/pandok/contracts
RUN pip install --no-cache-dir /opt/pandok

COPY --chown=airflow:root sql /opt/pandok/sql

# 소스 레이아웃을 우선 사용해 validator가 바로 옆 contracts Schema를 찾게 한다.
ENV PYTHONPATH=/opt/pandok/src
