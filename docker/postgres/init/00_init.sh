#!/usr/bin/env bash
# ============================================================================
# Initialisation du conteneur PostgreSQL au premier démarrage :
#   1. Création des 4 bases (erp_source, dwh, airflow, superset)
#   2. Application du schéma source ERP sur erp_source
#   3. Application des schémas staging / dwh / mart + seeds + vues sur dwh
#
# Ce script n'est exécuté qu'une seule fois, à l'initialisation du volume de
# données (comportement standard de l'image officielle postgres, qui exécute
# tout script de /docker-entrypoint-initdb.d/ au premier démarrage).
# ============================================================================
set -euo pipefail

SQL_DIR=/docker-entrypoint-initdb.d/sql

echo ">> Création des bases applicatives..."
for db in erp_source dwh airflow superset; do
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres -c "CREATE DATABASE ${db};" || true
done

echo ">> Application du schéma source ERP (base erp_source)..."
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname erp_source -f "${SQL_DIR}/01_source_erp/01_schema_erp.sql"

echo ">> Application du schéma Data Warehouse (base dwh)..."
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname dwh -f "${SQL_DIR}/02_staging/01_schema_staging.sql"
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname dwh -f "${SQL_DIR}/03_dwh/01_schema_dwh.sql"
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname dwh -f "${SQL_DIR}/03_dwh/02_seed_dim_date.sql"
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname dwh -f "${SQL_DIR}/03_dwh/03_seed_membres_inconnus.sql"
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname dwh -f "${SQL_DIR}/04_views/01_vues_restitution.sql"

echo ">> Initialisation PostgreSQL terminée."
