FROM apache/airflow:2.9.2-python3.11

USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

USER airflow

RUN pip install --no-cache-dir \
    'dbt-core==1.7.4' \
    'dbt-duckdb==1.7.4' \
    'pandas==2.2.2' \
    'scikit-learn==1.4.1.post1' \
    'duckdb==0.10.2' \
    'google-generativeai==0.5.0' \
    'joblib==1.3.2'
