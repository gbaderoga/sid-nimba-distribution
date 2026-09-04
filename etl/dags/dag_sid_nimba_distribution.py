"""
DAG Airflow - Système d'Information Décisionnel Nimba Distribution
====================================================================
Orchestre le pipeline ETL quotidien :

    extraction (8 sources, en parallèle)
        -> chargement des dimensions (SCD1 / SCD2, en parallèle)
            -> chargement des faits (en parallèle)
                -> contrôles qualité

Chaque tâche appelle directement les fonctions du package `etl` (le même
code que celui utilisé en exécution locale via `python -m etl.run_pipeline`),
Airflow n'ajoutant que l'orchestration, la planification et la reprise sur
erreur (retries).

Le module `etl` doit être disponible sur le PYTHONPATH du conteneur Airflow
(voir docker-compose.yml : le dossier du projet est monté et PYTHONPATH est
positionné en conséquence).
"""
from __future__ import annotations

import datetime

from airflow.decorators import dag, task
from airflow.models.baseoperator import cross_downstream
from airflow.operators.python import get_current_context

default_args = {
    "owner": "sid-nimba-distribution",
    "retries": 2,
    "retry_delay": datetime.timedelta(minutes=3),
    "email_on_failure": False,
}


def _batch_id() -> str:
    ctx = get_current_context()
    return ctx["run_id"].replace(":", "_").replace("+", "_")


@dag(
    dag_id="sid_nimba_distribution_daily",
    description="Pipeline ETL quotidien du SID Nimba Distribution (sources -> staging -> DWH)",
    schedule="0 3 * * *",           # tous les jours à 03h00
    start_date=datetime.datetime(2026, 1, 1),
    catchup=False,
    default_args=default_args,
    tags=["sid", "nimba-distribution", "etl"],
    max_active_runs=1,
)
def sid_nimba_distribution_daily():

    # ------------------------------------------------------------------
    # 1. Extraction (sources -> staging)
    # ------------------------------------------------------------------
    @task
    def extract_clients():
        from etl.extract.extract_csv import extract_clients as fn
        return fn(_batch_id())

    @task
    def extract_produits():
        from etl.extract.extract_excel import extract_produits as fn
        return fn(_batch_id())

    @task
    def extract_objectifs():
        from etl.extract.extract_excel import extract_objectifs as fn
        return fn(_batch_id())

    @task
    def extract_magasins():
        from etl.extract.extract_json import extract_magasins as fn
        return fn(_batch_id())

    @task
    def extract_commerciaux():
        from etl.extract.extract_erp import extract_commerciaux as fn
        return fn(_batch_id())

    @task
    def extract_ventes():
        from etl.extract.extract_erp import extract_ventes as fn
        return fn(_batch_id())

    @task
    def extract_stocks():
        from etl.extract.extract_erp import extract_stocks as fn
        return fn(_batch_id())

    @task
    def extract_taux_change():
        from etl.extract.extract_api_taux_change import extract_taux_change as fn
        return fn(_batch_id())

    # ------------------------------------------------------------------
    # 2. Chargement des dimensions (staging -> dwh)
    # ------------------------------------------------------------------
    @task
    def load_dim_magasin():
        from etl.load.load_dimensions import load_dim_magasin as fn
        return fn()

    @task
    def load_dim_commercial():
        from etl.load.load_dimensions import load_dim_commercial as fn
        return fn()

    @task
    def load_dim_client():
        from etl.load.load_dimensions import load_dim_client as fn
        return fn()

    @task
    def load_dim_produit():
        from etl.load.load_dimensions import load_dim_produit as fn
        return fn()

    # ------------------------------------------------------------------
    # 3. Chargement des faits (staging + dims -> dwh)
    # ------------------------------------------------------------------
    @task
    def load_fact_ventes():
        from etl.load.load_facts import load_fact_ventes as fn
        return fn(_batch_id())

    @task
    def load_fact_stock():
        from etl.load.load_facts import load_fact_stock as fn
        return fn(_batch_id())

    @task
    def load_fact_objectifs():
        from etl.load.load_facts import load_fact_objectifs as fn
        return fn(_batch_id())

    @task
    def load_fact_taux_change():
        from etl.load.load_facts import load_fact_taux_change as fn
        return fn(_batch_id())

    # ------------------------------------------------------------------
    # 4. Contrôles qualité
    # ------------------------------------------------------------------
    @task
    def quality_checks():
        from etl.utils.data_quality import run_data_quality_checks
        return run_data_quality_checks(fail_fast=True)

    extraction = [
        extract_clients(), extract_produits(), extract_objectifs(), extract_magasins(),
        extract_commerciaux(), extract_ventes(), extract_stocks(), extract_taux_change(),
    ]

    dims = [load_dim_magasin(), load_dim_commercial(), load_dim_client(), load_dim_produit()]

    facts = [load_fact_ventes(), load_fact_stock(), load_fact_objectifs(), load_fact_taux_change()]

    quality = quality_checks()

    cross_downstream(extraction, dims)
    cross_downstream(dims, facts)
    cross_downstream(facts, [quality])


sid_nimba_distribution_daily()
