"""Extraction des sources Excel : produits.xlsx et objectifs.xlsx."""
import os

import pandas as pd

from etl.extract.staging_loader import load_dataframe_to_staging
from etl.utils.db import get_dwh_engine
from etl.utils.logging_conf import get_logger
from etl.utils.paths import RAW_EXCEL

logger = get_logger(__name__)

PRODUITS_FILE = os.path.join(RAW_EXCEL, "produits.xlsx")
OBJECTIFS_FILE = os.path.join(RAW_EXCEL, "objectifs.xlsx")


def extract_produits(batch_id: str) -> int:
    logger.info("Extraction Excel : %s", PRODUITS_FILE)
    df = pd.read_excel(PRODUITS_FILE, sheet_name="Produits", dtype=str)
    engine = get_dwh_engine()
    return load_dataframe_to_staging(engine, df, "stg_produits", batch_id, os.path.basename(PRODUITS_FILE))


def extract_objectifs(batch_id: str) -> int:
    logger.info("Extraction Excel : %s", OBJECTIFS_FILE)
    df = pd.read_excel(OBJECTIFS_FILE, sheet_name="Objectifs", dtype=str)
    engine = get_dwh_engine()
    return load_dataframe_to_staging(engine, df, "stg_objectifs", batch_id, os.path.basename(OBJECTIFS_FILE))


if __name__ == "__main__":
    import datetime
    bid = datetime.datetime.now().strftime("manual_%Y%m%d%H%M%S")
    extract_produits(bid)
    extract_objectifs(bid)
