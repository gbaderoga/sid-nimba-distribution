#!/usr/bin/env bash
# ============================================================================
# Initialisation idempotente de Superset : migration de la base de
# métadonnées, création de l'utilisateur admin (si absent), rôles par défaut,
# puis démarrage du serveur.
#
# La création de la connexion à la base dwh, des datasets, des graphiques et
# du tableau de bord est déléguée au service "superset-provision"
# (voir docker-compose.yml), qui appelle dashboard/provision_dashboard.py via
# l'API REST une fois ce serveur en état "healthy". Cette séparation évite de
# devoir démarrer un serveur Flask temporaire dans ce script d'init.
# ============================================================================
set -e

superset db upgrade

superset fab create-admin \
    --username "${SUPERSET_ADMIN_USER:-admin}" \
    --firstname Admin \
    --lastname Nimba \
    --email "${SUPERSET_ADMIN_EMAIL:-admin@nimba-distribution.example}" \
    --password "${SUPERSET_ADMIN_PASSWORD:-admin}" || true

superset init

exec /usr/bin/run-server.sh
