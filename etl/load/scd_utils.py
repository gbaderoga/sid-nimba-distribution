"""Utilitaires génériques de gestion des dimensions à évolution lente (SCD)."""
import hashlib
import datetime

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from etl.utils.logging_conf import get_logger

logger = get_logger(__name__)


def _row_hash(row: pd.Series, tracked_cols: list) -> str:
    raw = "|".join(str(row[c]) for c in tracked_cols)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def scd2_upsert(engine: Engine, table: str, business_key_col: str, tracked_cols: list,
                 df: pd.DataFrame, effective_date: datetime.date = None) -> dict:
    """Applique une logique SCD Type 2 générique sur une dimension.

    `df` doit contenir la colonne `business_key_col` ainsi que toutes les
    colonnes cibles de la dimension (y compris les colonnes non suivies pour
    l'historisation, par ex. la date d'inscription).

    Retourne un dict {"inserted": n, "expired": n, "unchanged": n}.
    """
    if effective_date is None:
        effective_date = datetime.date.today()

    df = df.drop_duplicates(subset=[business_key_col], keep="last").copy()
    df["hash_attributs"] = df.apply(lambda r: _row_hash(r, tracked_cols), axis=1)

    with engine.begin() as conn:
        current = pd.read_sql(
            text(f"SELECT {business_key_col}, hash_attributs FROM dwh.{table} WHERE est_version_courante = TRUE"),
            conn,
        )

    merged = df.merge(current, on=business_key_col, how="left", suffixes=("", "_actuel"))

    nouveaux = merged[merged["hash_attributs_actuel"].isna()]
    changes = merged[
        merged["hash_attributs_actuel"].notna()
        & (merged["hash_attributs"] != merged["hash_attributs_actuel"])
    ]
    inchanges = merged[
        merged["hash_attributs_actuel"].notna()
        & (merged["hash_attributs"] == merged["hash_attributs_actuel"])
    ]

    a_inserer = pd.concat([nouveaux, changes], ignore_index=True).drop(columns=["hash_attributs_actuel"])
    a_inserer["date_debut_validite"] = effective_date
    a_inserer["date_fin_validite"] = None
    a_inserer["est_version_courante"] = True

    with engine.begin() as conn:
        if len(changes) > 0:
            cles_a_expirer = changes[business_key_col].tolist()
            conn.execute(
                text(f"""
                    UPDATE dwh.{table}
                       SET date_fin_validite = :fin, est_version_courante = FALSE
                     WHERE {business_key_col} = ANY(:cles)
                       AND est_version_courante = TRUE
                """),
                {"fin": effective_date - datetime.timedelta(days=1), "cles": cles_a_expirer},
            )

    if len(a_inserer) > 0:
        a_inserer.to_sql(table, engine, schema="dwh", if_exists="append", index=False,
                          method="multi", chunksize=500)

    logger.info("SCD2 dwh.%s : %d nouveaux, %d modifiés (nouvelle version), %d inchangés",
                table, len(nouveaux), len(changes), len(inchanges))
    return {"inserted": len(nouveaux), "expired": len(changes), "unchanged": len(inchanges)}


def scd1_upsert(engine: Engine, table: str, business_key_col: str, df: pd.DataFrame) -> int:
    """Upsert simple (écrasement) pour une dimension SCD Type 1."""
    df = df.drop_duplicates(subset=[business_key_col], keep="last").copy()
    cols = list(df.columns)
    update_cols = [c for c in cols if c != business_key_col]

    with engine.begin() as conn:
        conn.execute(text(f"CREATE TEMP TABLE tmp_{table} (LIKE dwh.{table} INCLUDING DEFAULTS) ON COMMIT DROP"))
        conn.execute(text(f"ALTER TABLE tmp_{table} DROP COLUMN {table.split('_')[-1]}_sk"))
        df.to_sql(f"tmp_{table}", conn, if_exists="append", index=False, method="multi", chunksize=500)

        set_clause = ", ".join(f"{c} = EXCLUDED.{c}" for c in update_cols)
        col_list = ", ".join(cols)
        conn.execute(text(f"""
            INSERT INTO dwh.{table} ({col_list})
            SELECT {col_list} FROM tmp_{table}
            ON CONFLICT ({business_key_col}) DO UPDATE SET {set_clause}
        """))

    logger.info("SCD1 dwh.%s : %d lignes upsertées", table, len(df))
    return len(df)
