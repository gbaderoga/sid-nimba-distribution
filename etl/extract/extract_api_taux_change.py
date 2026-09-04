"""Extraction de la source externe (optionnelle - "aller plus loin") :
taux de change EUR -> USD / GNF, via une API publique.

Cette source illustre l'intégration d'une API externe dans le SID. Par
construction, le pipeline reste robuste sans accès réseau externe : en cas
d'échec (timeout, erreur HTTP, environnement sans sortie Internet), le module
retombe automatiquement sur l'instantané statique fourni dans
data/raw/json/taux_change_fallback.json, journalise l'incident et poursuit
sans faire échouer le DAG.
"""
import datetime
import json
import os

import pandas as pd
import requests

from etl.extract.staging_loader import load_dataframe_to_staging
from etl.utils.db import get_dwh_engine
from etl.utils.logging_conf import get_logger
from etl.utils.paths import RAW_JSON

logger = get_logger(__name__)

API_URL = os.getenv("EXCHANGE_RATE_API_URL", "https://open.er-api.com/v6/latest/EUR")
FALLBACK_FILE = os.path.join(RAW_JSON, "taux_change_fallback.json")
DEVISES_SUIVIES = ["USD", "GNF"]


def _fetch_from_api() -> dict:
    resp = requests.get(API_URL, timeout=8)
    resp.raise_for_status()
    payload = resp.json()
    return {
        "base": payload.get("base_code", payload.get("base", "EUR")),
        "date": datetime.date.today().isoformat(),
        "rates": payload.get("rates", {}),
    }


def _fetch_from_fallback() -> dict:
    with open(FALLBACK_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_taux_change(batch_id: str) -> int:
    try:
        data = _fetch_from_api()
        logger.info("Taux de change récupérés depuis l'API externe (%s)", API_URL)
    except Exception as exc:  # noqa: BLE001 - on veut dégrader proprement quelle que soit la cause
        logger.warning("API de taux de change injoignable (%s) - repli sur le fichier statique %s",
                        exc, FALLBACK_FILE)
        data = _fetch_from_fallback()

    rows = [
        {"date_taux": data["date"], "devise_source": data["base"], "devise_cible": devise, "taux": taux}
        for devise, taux in data.get("rates", {}).items()
        if devise in DEVISES_SUIVIES
    ]
    df = pd.DataFrame(rows)
    return load_dataframe_to_staging(get_dwh_engine(), df, "stg_taux_change", batch_id, "api_taux_change")


if __name__ == "__main__":
    extract_taux_change(datetime.datetime.now().strftime("manual_%Y%m%d%H%M%S"))
