"""Transformation + chargement des dimensions depuis la zone de staging.

dim_client, dim_produit : SCD Type 2 (historisation)
dim_magasin, dim_commercial : SCD Type 1 (écrasement)
"""
import datetime

import pandas as pd
from sqlalchemy import text

from etl.load.scd_utils import scd1_upsert, scd2_upsert
from etl.utils.db import get_dwh_engine
from etl.utils.logging_conf import get_logger

logger = get_logger(__name__)


def load_dim_client(effective_date: datetime.date = None) -> dict:
    engine = get_dwh_engine()
    stg = pd.read_sql("SELECT * FROM staging.stg_clients", engine)

    df = pd.DataFrame({
        "client_id": stg["client_code"].str.strip(),
        "nom": stg["nom"].str.strip(),
        "prenom": stg["prenom"].str.strip(),
        "email": stg["email"].str.strip().str.lower(),
        "telephone": stg["telephone"],
        "segment_client": stg["segment"],
        "ville": stg["ville"],
        "region": stg["region"],
        "pays": stg["pays"],
        "date_inscription": pd.to_datetime(stg["date_inscription"], errors="coerce").dt.date,
    }).dropna(subset=["client_id"])

    tracked = ["nom", "prenom", "email", "telephone", "segment_client", "ville", "region", "pays"]
    return scd2_upsert(engine, "dim_client", "client_id", tracked, df, effective_date)


def load_dim_produit(effective_date: datetime.date = None) -> dict:
    engine = get_dwh_engine()
    stg = pd.read_sql("SELECT * FROM staging.stg_produits", engine)

    df = pd.DataFrame({
        "produit_id": stg["produit_id"].str.strip(),
        "nom_produit": stg["nom_produit"],
        "categorie": stg["categorie"],
        "sous_categorie": stg["sous_categorie"],
        "marque": stg["marque"],
        "prix_unitaire": pd.to_numeric(stg["prix_unitaire"], errors="coerce").fillna(0).round(2),
        "cout_unitaire": pd.to_numeric(stg["cout_unitaire"], errors="coerce").fillna(0).round(2),
    }).dropna(subset=["produit_id"])

    tracked = ["nom_produit", "categorie", "sous_categorie", "marque", "prix_unitaire", "cout_unitaire"]
    return scd2_upsert(engine, "dim_produit", "produit_id", tracked, df, effective_date)


def load_dim_magasin() -> int:
    engine = get_dwh_engine()
    stg = pd.read_sql("SELECT * FROM staging.stg_magasins", engine)

    df = pd.DataFrame({
        "magasin_id": stg["magasin_id"].str.strip(),
        "nom_magasin": stg["nom_magasin"],
        "type_magasin": stg["type_magasin"],
        "adresse": stg["adresse"],
        "ville": stg["ville"],
        "region": stg["region"],
        "pays": stg["pays"],
        "latitude": pd.to_numeric(stg["latitude"], errors="coerce"),
        "longitude": pd.to_numeric(stg["longitude"], errors="coerce"),
        "date_ouverture": pd.to_datetime(stg["date_ouverture"], errors="coerce").dt.date,
    }).dropna(subset=["magasin_id"])

    return scd1_upsert(engine, "dim_magasin", "magasin_id", df)


def load_dim_commercial() -> int:
    engine = get_dwh_engine()
    stg = pd.read_sql("SELECT * FROM staging.stg_commerciaux", engine)

    df = pd.DataFrame({
        "commercial_id": stg["matricule"].str.strip(),   # clé métier stable = matricule
        "matricule": stg["matricule"].str.strip(),
        "nom": stg["nom"],
        "prenom": stg["prenom"],
        "email": stg["email"],
        "magasin_id": stg["magasin_id"],
        "date_embauche": pd.to_datetime(stg["date_embauche"], errors="coerce").dt.date,
        "statut": stg["statut"],
    }).dropna(subset=["commercial_id"])

    return scd1_upsert(engine, "dim_commercial", "commercial_id", df)


if __name__ == "__main__":
    print(load_dim_client())
    print(load_dim_produit())
    print("dim_magasin:", load_dim_magasin())
    print("dim_commercial:", load_dim_commercial())
