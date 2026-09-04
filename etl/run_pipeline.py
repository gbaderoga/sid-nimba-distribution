#!/usr/bin/env python3
"""Orchestrateur du pipeline ETL complet - exécutable en local ou appelé par
les tâches du DAG Airflow (chaque fonction ci-dessous correspond à une tâche).

Ordre d'exécution :
  1. Extraction (toutes sources -> staging), indépendantes entre elles
  2. Chargement des dimensions (staging -> dwh), indépendantes entre elles
  3. Chargement des faits (staging + dims -> dwh), dépendent des dimensions
  4. Contrôles qualité
"""
import argparse
import datetime
import sys

from etl.extract.extract_api_taux_change import extract_taux_change
from etl.extract.extract_csv import extract_clients
from etl.extract.extract_erp import extract_commerciaux, extract_stocks, extract_ventes
from etl.extract.extract_excel import extract_objectifs, extract_produits
from etl.extract.extract_json import extract_magasins
from etl.load.load_dimensions import load_dim_client, load_dim_commercial, load_dim_magasin, load_dim_produit
from etl.load.load_facts import load_fact_objectifs, load_fact_stock, load_fact_taux_change, load_fact_ventes
from etl.utils.data_quality import run_data_quality_checks
from etl.utils.logging_conf import get_logger

logger = get_logger(__name__)


def new_batch_id() -> str:
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


def run_extraction(batch_id: str):
    logger.info("=== Étape 1/4 : extraction ===")
    extract_clients(batch_id)
    extract_produits(batch_id)
    extract_objectifs(batch_id)
    extract_magasins(batch_id)
    extract_commerciaux(batch_id)
    extract_ventes(batch_id)
    extract_stocks(batch_id)
    extract_taux_change(batch_id)


def run_load_dimensions(effective_date=None):
    logger.info("=== Étape 2/4 : chargement des dimensions ===")
    load_dim_magasin()
    load_dim_commercial()
    load_dim_client(effective_date)
    load_dim_produit(effective_date)


def run_load_facts(batch_id: str):
    logger.info("=== Étape 3/4 : chargement des faits ===")
    load_fact_ventes(batch_id)
    load_fact_stock(batch_id)
    load_fact_objectifs(batch_id)
    load_fact_taux_change(batch_id)


def run_quality_checks():
    logger.info("=== Étape 4/4 : contrôles qualité ===")
    return run_data_quality_checks(fail_fast=True)


def run_full_pipeline():
    batch_id = new_batch_id()
    logger.info("Démarrage du pipeline ETL - batch_id=%s", batch_id)
    t0 = datetime.datetime.now()
    try:
        run_extraction(batch_id)
        run_load_dimensions()
        run_load_facts(batch_id)
        run_quality_checks()
    except Exception:
        logger.exception("Échec du pipeline ETL (batch_id=%s)", batch_id)
        raise
    duree = (datetime.datetime.now() - t0).total_seconds()
    logger.info("Pipeline ETL terminé avec succès en %.1fs (batch_id=%s)", duree, batch_id)
    return batch_id


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Exécute le pipeline ETL de Nimba Distribution.")
    parser.add_argument("--step", choices=["all", "extract", "dims", "facts", "quality"], default="all")
    args = parser.parse_args()

    if args.step == "all":
        run_full_pipeline()
    elif args.step == "extract":
        run_extraction(new_batch_id())
    elif args.step == "dims":
        run_load_dimensions()
    elif args.step == "facts":
        run_load_facts(new_batch_id())
    elif args.step == "quality":
        run_quality_checks()

    sys.exit(0)
