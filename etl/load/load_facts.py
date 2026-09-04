"""Transformation + chargement des tables de faits depuis la zone de staging.

Chaque fonction : (1) lit le staging, (2) résout les clés de substitution via
les dimensions courantes, (3) calcule les mesures, (4) upsert dans dwh.*.
Les clés non résolues sont rattachées au membre "INCONNU" de la dimension
concernée plutôt que d'être rejetées.
"""
import datetime

import pandas as pd

from etl.load.fact_utils import upsert_fact
from etl.utils.db import get_dwh_engine
from etl.utils.logging_conf import get_logger

logger = get_logger(__name__)


def _dim_date_lookup(engine):
    return pd.read_sql("SELECT date_id, date_complete FROM dwh.dim_date", engine)


def load_fact_ventes(batch_id: str) -> int:
    engine = get_dwh_engine()

    ventes = pd.read_sql("SELECT * FROM staging.stg_ventes", engine)
    commerciaux = pd.read_sql("SELECT commercial_id AS erp_commercial_id, matricule FROM staging.stg_commerciaux", engine)

    dim_client = pd.read_sql("SELECT client_sk, client_id FROM dwh.dim_client WHERE est_version_courante", engine)
    dim_produit = pd.read_sql(
        "SELECT produit_sk, produit_id, cout_unitaire FROM dwh.dim_produit WHERE est_version_courante", engine)
    dim_magasin = pd.read_sql("SELECT magasin_sk, magasin_id FROM dwh.dim_magasin", engine)
    dim_commercial = pd.read_sql("SELECT commercial_sk, commercial_id FROM dwh.dim_commercial", engine)
    dim_canal = pd.read_sql("SELECT canal_sk, code_canal FROM dwh.dim_canal_vente", engine)
    dim_date = _dim_date_lookup(engine)

    df = ventes.copy()
    df["date_only"] = pd.to_datetime(df["date_commande"], errors="coerce").dt.date
    df["quantite"] = pd.to_numeric(df["quantite"], errors="coerce").fillna(0).astype(int)
    df["prix_unitaire_vente"] = pd.to_numeric(df["prix_unitaire_vente"], errors="coerce").fillna(0)
    df["taux_remise"] = pd.to_numeric(df["taux_remise"], errors="coerce").fillna(0)

    # résolution du matricule commercial à partir de l'id technique ERP
    df = df.merge(commerciaux, left_on="commercial_id", right_on="erp_commercial_id", how="left")

    df = df.merge(dim_date, left_on="date_only", right_on="date_complete", how="left")
    df = df.merge(dim_client, left_on="client_code", right_on="client_id", how="left")
    df = df.merge(dim_produit, left_on="produit_id", right_on="produit_id", how="left")
    df = df.merge(dim_magasin, left_on="magasin_id", right_on="magasin_id", how="left")
    df = df.merge(dim_commercial, left_on="matricule", right_on="commercial_id", how="left",
                   suffixes=("", "_dimcom"))
    df = df.merge(dim_canal, left_on="canal_vente", right_on="code_canal", how="left")

    # rattachement des clés non résolues au membre "INCONNU"
    sk_inconnu = pd.read_sql(
        "SELECT (SELECT client_sk FROM dwh.dim_client WHERE client_id='INCONNU') AS client_sk_inconnu,"
        " (SELECT produit_sk FROM dwh.dim_produit WHERE produit_id='INCONNU') AS produit_sk_inconnu,"
        " (SELECT magasin_sk FROM dwh.dim_magasin WHERE magasin_id='INCONNU') AS magasin_sk_inconnu,"
        " (SELECT commercial_sk FROM dwh.dim_commercial WHERE commercial_id='INCONNU') AS commercial_sk_inconnu",
        engine,
    ).iloc[0]

    df["client_sk"] = df["client_sk"].fillna(sk_inconnu["client_sk_inconnu"])
    df["produit_sk"] = df["produit_sk"].fillna(sk_inconnu["produit_sk_inconnu"])
    df["magasin_sk"] = df["magasin_sk"].fillna(sk_inconnu["magasin_sk_inconnu"])
    df["commercial_sk"] = df["commercial_sk"].fillna(sk_inconnu["commercial_sk_inconnu"])

    avant = len(df)
    df = df.dropna(subset=["date_id", "canal_sk"])
    if len(df) < avant:
        logger.warning("fact_ventes : %d ligne(s) écartée(s) faute de date ou canal résolus", avant - len(df))

    df["montant_brut"] = (df["quantite"] * df["prix_unitaire_vente"]).round(2)
    df["montant_remise"] = (df["montant_brut"] * df["taux_remise"]).round(2)
    df["montant_net"] = (df["montant_brut"] - df["montant_remise"]).round(2)
    df["cout_total"] = (df["quantite"] * df["cout_unitaire"].fillna(0)).round(2)
    df["marge"] = (df["montant_net"] - df["cout_total"]).round(2)

    out = df[[
        "date_id", "client_sk", "produit_sk", "magasin_sk", "commercial_sk", "canal_sk",
        "numero_commande", "ligne_id", "statut_commande", "quantite", "prix_unitaire_vente",
        "taux_remise", "montant_brut", "montant_remise", "montant_net", "cout_total", "marge",
    ]].copy()
    out["date_id"] = out["date_id"].astype(int)
    out["commercial_sk"] = out["commercial_sk"].astype("Int64")

    return upsert_fact(engine, "fact_ventes", "vente_sk", ["numero_commande", "ligne_id"], out, batch_id)


def load_fact_stock(batch_id: str) -> int:
    engine = get_dwh_engine()

    stocks = pd.read_sql("SELECT * FROM staging.stg_stocks", engine)
    dim_produit = pd.read_sql(
        "SELECT produit_sk, produit_id, cout_unitaire FROM dwh.dim_produit WHERE est_version_courante", engine)
    dim_magasin = pd.read_sql("SELECT magasin_sk, magasin_id FROM dwh.dim_magasin", engine)
    dim_date = _dim_date_lookup(engine)

    df = stocks.copy()
    df["date_only"] = pd.to_datetime(df["date_releve"], errors="coerce").dt.date
    df["quantite_stock"] = pd.to_numeric(df["quantite_stock"], errors="coerce").fillna(0).astype(int)
    df["seuil_alerte"] = pd.to_numeric(df["seuil_alerte"], errors="coerce").fillna(0).astype(int)

    df = df.merge(dim_date, left_on="date_only", right_on="date_complete", how="inner")
    df = df.merge(dim_produit, on="produit_id", how="inner")
    df = df.merge(dim_magasin, on="magasin_id", how="inner")

    df["valeur_stock"] = (df["quantite_stock"] * df["cout_unitaire"].fillna(0)).round(2)
    df["en_rupture"] = df["quantite_stock"] <= df["seuil_alerte"]

    out = df[["date_id", "produit_sk", "magasin_sk", "quantite_stock", "seuil_alerte",
              "valeur_stock", "en_rupture"]].copy()
    out["date_id"] = out["date_id"].astype(int)

    return upsert_fact(engine, "fact_stock", "stock_sk", ["date_id", "produit_sk", "magasin_sk"], out, batch_id)


def load_fact_objectifs(batch_id: str) -> int:
    engine = get_dwh_engine()

    objectifs = pd.read_sql("SELECT * FROM staging.stg_objectifs", engine)
    dim_commercial = pd.read_sql("SELECT commercial_sk, commercial_id FROM dwh.dim_commercial", engine)
    dim_magasin = pd.read_sql("SELECT magasin_sk, magasin_id FROM dwh.dim_magasin", engine)
    dim_date = _dim_date_lookup(engine)

    df = objectifs.copy()
    df["date_only"] = pd.to_datetime(df["annee_mois"] + "-01", errors="coerce").dt.date
    df["objectif_ca"] = pd.to_numeric(df["objectif_ca"], errors="coerce").fillna(0)
    df["objectif_quantite"] = pd.to_numeric(df["objectif_quantite"], errors="coerce").fillna(0).astype(int)

    df = df.merge(dim_date, left_on="date_only", right_on="date_complete", how="inner")
    df = df.merge(dim_commercial, left_on="matricule_commercial", right_on="commercial_id", how="inner")
    df = df.merge(dim_magasin, on="magasin_id", how="inner")

    out = df[["date_id", "commercial_sk", "magasin_sk", "objectif_ca", "objectif_quantite"]].copy()
    out["date_id"] = out["date_id"].astype(int)

    return upsert_fact(engine, "fact_objectifs", "objectif_sk", ["date_id", "commercial_sk"], out, batch_id)


if __name__ == "__main__":
    bid = datetime.datetime.now().strftime("manual_%Y%m%d%H%M%S")
    print("fact_ventes:", load_fact_ventes(bid))
    print("fact_stock:", load_fact_stock(bid))
    print("fact_objectifs:", load_fact_objectifs(bid))
