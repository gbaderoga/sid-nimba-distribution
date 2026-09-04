"""Fabriques de connexions SQLAlchemy vers les bases erp_source et dwh.

Les paramètres sont lus depuis les variables d'environnement (voir .env.example) :
POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST, POSTGRES_PORT,
POSTGRES_DB_ERP, POSTGRES_DB_DWH.
"""
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from etl.utils.paths import PROJECT_ROOT

load_dotenv(os.path.join(PROJECT_ROOT, ".env"))


def _build_url(db_name_env: str, default_db: str) -> str:
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "postgres")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    db = os.getenv(db_name_env, default_db)
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"


def get_erp_engine() -> Engine:
    """Connexion vers la base opérationnelle (ERP/CRM source)."""
    return create_engine(_build_url("POSTGRES_DB_ERP", "erp_source"), pool_pre_ping=True)


def get_dwh_engine() -> Engine:
    """Connexion vers le Data Warehouse (schémas staging / dwh / mart)."""
    return create_engine(_build_url("POSTGRES_DB_DWH", "dwh"), pool_pre_ping=True)
