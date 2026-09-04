"""Utilitaire générique de chargement (upsert) des tables de faits."""
from sqlalchemy import text
from sqlalchemy.engine import Engine
import pandas as pd

from etl.utils.logging_conf import get_logger

logger = get_logger(__name__)


def upsert_fact(engine: Engine, table: str, sk_col: str, conflict_cols: list,
                 df: pd.DataFrame, batch_id: str) -> int:
    """Charge un DataFrame dans une table de faits via INSERT ... ON CONFLICT DO UPDATE.

    `df` doit contenir exactement les colonnes métier de la table de faits
    (hors clé de substitution `sk_col`, gérée automatiquement). Si la table
    n'a pas de clé de substitution technique (PK composite naturelle),
    passer `sk_col=None`.
    """
    if len(df) == 0:
        logger.warning("dwh.%s : aucune ligne à charger (DataFrame vide)", table)
        return 0

    df = df.copy()
    df["_batch_id"] = batch_id

    cols = list(df.columns)
    update_cols = [c for c in cols if c not in conflict_cols]
    tmp_name = f"tmp_{table}"

    with engine.begin() as conn:
        conn.execute(text(f"CREATE TEMP TABLE {tmp_name} (LIKE dwh.{table} INCLUDING DEFAULTS) ON COMMIT DROP"))
        if sk_col:
            conn.execute(text(f"ALTER TABLE {tmp_name} DROP COLUMN {sk_col}"))
        df.to_sql(tmp_name, conn, if_exists="append", index=False, method="multi", chunksize=2000)

        set_clause = ", ".join(f"{c} = EXCLUDED.{c}" for c in update_cols)
        col_list = ", ".join(cols)
        conflict_list = ", ".join(conflict_cols)
        result = conn.execute(text(f"""
            INSERT INTO dwh.{table} ({col_list})
            SELECT {col_list} FROM {tmp_name}
            ON CONFLICT ({conflict_list}) DO UPDATE SET {set_clause}
        """))

    logger.info("dwh.%s : %d lignes upsertées (batch=%s)", table, len(df), batch_id)
    return len(df)
