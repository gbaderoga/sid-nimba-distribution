"""Extraction de la source base relationnelle (ERP/CRM opérationnel).

Trois flux distincts :
  - commerciaux              -> staging.stg_commerciaux
  - commandes + lignes (dénormalisées au grain ligne) -> staging.stg_ventes
  - stocks                   -> staging.stg_stocks
"""
import pandas as pd

from etl.extract.staging_loader import load_dataframe_to_staging
from etl.utils.db import get_dwh_engine, get_erp_engine
from etl.utils.logging_conf import get_logger

logger = get_logger(__name__)

SQL_COMMERCIAUX = "SELECT commercial_id, matricule, nom, prenom, email, magasin_id, date_embauche, statut FROM erp.commerciaux"

SQL_VENTES = """
    SELECT
        c.commande_id,
        c.numero_commande,
        l.ligne_id,
        c.client_code,
        c.magasin_id,
        c.commercial_id,
        c.canal_vente,
        c.date_commande,
        c.statut_commande,
        l.produit_id,
        l.quantite,
        l.prix_unitaire_vente,
        l.taux_remise
    FROM erp.commandes c
    JOIN erp.lignes_commande l ON l.commande_id = c.commande_id
"""

SQL_STOCKS = "SELECT date_releve, magasin_id, produit_id, quantite_stock, seuil_alerte FROM erp.stocks"


def extract_commerciaux(batch_id: str) -> int:
    logger.info("Extraction ERP (relationnelle) : erp.commerciaux")
    df = pd.read_sql(SQL_COMMERCIAUX, get_erp_engine())
    return load_dataframe_to_staging(get_dwh_engine(), df, "stg_commerciaux", batch_id, "erp.commerciaux")


def extract_ventes(batch_id: str) -> int:
    logger.info("Extraction ERP (relationnelle) : erp.commandes + erp.lignes_commande")
    df = pd.read_sql(SQL_VENTES, get_erp_engine())
    return load_dataframe_to_staging(get_dwh_engine(), df, "stg_ventes", batch_id, "erp.commandes+lignes_commande")


def extract_stocks(batch_id: str) -> int:
    logger.info("Extraction ERP (relationnelle) : erp.stocks")
    df = pd.read_sql(SQL_STOCKS, get_erp_engine())
    return load_dataframe_to_staging(get_dwh_engine(), df, "stg_stocks", batch_id, "erp.stocks")


if __name__ == "__main__":
    import datetime
    bid = datetime.datetime.now().strftime("manual_%Y%m%d%H%M%S")
    extract_commerciaux(bid)
    extract_ventes(bid)
    extract_stocks(bid)
