"""Utilitaire commun : dépose un DataFrame dans une table de staging.

Stratégie "truncate & load" par source : simple et suffisante pour un
référentiel de taille modérée. Chaque table de staging garde une trace du lot
d'exécution (_batch_id), du fichier/table source (_source_file) et de
l'horodatage de chargement (_loaded_at).
"""
import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from etl.utils.logging_conf import get_logger

logger = get_logger(__name__)


def load_dataframe_to_staging(engine: Engine, df: pd.DataFrame, table_name: str,
                               batch_id: str, source_file: str) -> int:
    df = df.copy()
    df["_batch_id"] = batch_id
    df["_source_file"] = source_file
    # cast en texte : la staging area ne fait aucune conversion de type (rôle de la transformation)
    for col in df.columns:
        df[col] = df[col].apply(lambda v: None if pd.isna(v) else str(v))

    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE staging.{table_name}"))

    df.to_sql(table_name, engine, schema="staging", if_exists="append", index=False,
               method="multi", chunksize=1000)
    logger.info("staging.%s : %d lignes chargées (source=%s, batch=%s)",
                table_name, len(df), source_file, batch_id)
    return len(df)
