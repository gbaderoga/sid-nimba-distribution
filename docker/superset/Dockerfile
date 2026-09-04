# ============================================================================
# Image Superset de Nimba Distribution : image officielle + configuration
# applicative (superset_config.py) + script d'initialisation idempotent.
# ============================================================================
ARG SUPERSET_VERSION=4.1.1
FROM apache/superset:${SUPERSET_VERSION}

USER root

# psycopg2-binary n'est pas inclus dans l'image officielle Superset, alors que
# superset_config.py construit un SQLALCHEMY_DATABASE_URI en
# postgresql+psycopg2://... (connexion à la base dwh) : sans ce paquet,
# Superset plante au démarrage avec ModuleNotFoundError: No module named 'psycopg2'.
RUN pip install --no-cache-dir psycopg2-binary

COPY superset_config.py /app/pythonpath/superset_config.py
COPY docker-init.sh /app/docker-init.sh
RUN chmod +x /app/docker-init.sh
USER superset

ENV SUPERSET_CONFIG_PATH=/app/pythonpath/superset_config.py
