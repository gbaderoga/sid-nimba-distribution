"""Chemins standards du projet, utilisés par le générateur de données et l'ETL."""
import os

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

DATA_DIR = os.path.join(PROJECT_ROOT, "data")
RAW_DIR = os.path.join(DATA_DIR, "raw")
RAW_CSV = os.path.join(RAW_DIR, "csv")
RAW_EXCEL = os.path.join(RAW_DIR, "excel")
RAW_JSON = os.path.join(RAW_DIR, "json")

SQL_DIR = os.path.join(PROJECT_ROOT, "sql")
LOGS_DIR = os.path.join(PROJECT_ROOT, "logs")

os.makedirs(LOGS_DIR, exist_ok=True)
