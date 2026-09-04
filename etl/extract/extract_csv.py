"""Extraction de la source CSV : clients.csv -> staging.stg_clients."""
import os

import pandas as pd

from etl.extract.staging_loader import load_dataframe_to_staging
from etl.utils.db import get_dwh_engine
from etl.utils.logging_conf import get_logger
from etl.utils.paths import RAW_CSV

logger = get_logger(__name__)

CLIENTS_FILE = os.path.join(RAW_CSV, "clients.csv")


def extract_clients(batch_id: str) -> int:
    logger.info("Extraction CSV : %s", CLIENTS_FILE)
    df = pd.read_csv(CLIENTS_FILE, dtype=str)
    engine = get_dwh_engine()
    return load_dataframe_to_staging(engine, df, "stg_clients", batch_id, os.path.basename(CLIENTS_FILE))


if __name__ == "__main__":
    import datetime
    extract_clients(datetime.datetime.now().strftime("manual_%Y%m%d%H%M%S"))
