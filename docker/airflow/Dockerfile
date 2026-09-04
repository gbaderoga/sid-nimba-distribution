# ============================================================================
# Image Airflow de Nimba Distribution : image officielle + dépendances du
# package etl/ (pandas, openpyxl, Faker, requests, python-dotenv) installées
# avec le fichier de contraintes officiel Airflow pour rester cohérent avec
# les versions déjà pinnées dans l'image de base (numpy, psycopg2, ...).
# ============================================================================
ARG AIRFLOW_VERSION=2.10.4
ARG PYTHON_VERSION=3.11
FROM apache/airflow:${AIRFLOW_VERSION}-python${PYTHON_VERSION}

ARG AIRFLOW_VERSION
ARG PYTHON_VERSION

COPY requirements-airflow.txt /requirements-airflow.txt

RUN pip install --no-cache-dir -r /requirements-airflow.txt \
    --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-${PYTHON_VERSION}.txt"
