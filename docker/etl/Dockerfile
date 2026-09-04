# ============================================================================
# Image légère pour les commandes ETL ponctuelles (génération de données,
# exécution manuelle du pipeline, tests). Le code est monté en volume par
# docker-compose ; cette image ne fournit que l'environnement Python.
# ============================================================================
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

CMD ["python3", "-m", "etl.run_pipeline"]
