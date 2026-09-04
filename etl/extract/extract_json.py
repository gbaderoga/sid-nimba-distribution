"""Extraction de la source JSON : magasins.json -> staging.stg_magasins."""
import json
import os

import pandas as pd

from etl.extract.staging_loader import load_dataframe_to_staging
from etl.utils.db import get_dwh_engine
from etl.utils.logging_conf import get_logger
from etl.utils.paths import RAW_JSON

logger = get_logger(__name__)

MAGASINS_FILE = os.path.join(RAW_JSON, "magasins.json")


def extract_magasins(batch_id: str) -> int:
    logger.info("Extraction JSON : %s", MAGASINS_FILE)
    with open(MAGASINS_FILE, "r", encoding="utf-8") as f:
        payload = json.load(f)
    df = pd.json_normalize(payload["magasins"])
    engine = get_dwh_engine()
    return load_dataframe_to_staging(engine, df, "stg_magasins", batch_id, os.path.basename(MAGASINS_FILE))


if __name__ == "__main__":
    import datetime
    extract_magasins(datetime.datetime.now().strftime("manual_%Y%m%d%H%M%S"))
