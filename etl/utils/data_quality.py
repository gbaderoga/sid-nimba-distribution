"""Contrôles qualité basiques exécutés en fin de pipeline.

Chaque contrôle retourne (nom, ok: bool, détail). Le pipeline consigne les
résultats et lève une exception si un contrôle bloquant échoue.
"""
from sqlalchemy import text

from etl.utils.db import get_dwh_engine
from etl.utils.logging_conf import get_logger

logger = get_logger(__name__)

CHECKS = [
    ("volumetrie_fact_ventes", "SELECT COUNT(*) FROM dwh.fact_ventes", lambda v: v > 0),
    ("volumetrie_fact_stock", "SELECT COUNT(*) FROM dwh.fact_stock", lambda v: v > 0),
    ("volumetrie_fact_objectifs", "SELECT COUNT(*) FROM dwh.fact_objectifs", lambda v: v > 0),
    ("pas_de_montant_net_negatif",
     "SELECT COUNT(*) FROM dwh.fact_ventes WHERE montant_net < 0", lambda v: v == 0),
    ("unicite_client_courant",
     "SELECT COUNT(*) FROM (SELECT client_id FROM dwh.dim_client WHERE est_version_courante"
     " GROUP BY client_id HAVING COUNT(*) > 1) t", lambda v: v == 0),
    ("unicite_produit_courant",
     "SELECT COUNT(*) FROM (SELECT produit_id FROM dwh.dim_produit WHERE est_version_courante"
     " GROUP BY produit_id HAVING COUNT(*) > 1) t", lambda v: v == 0),
    ("part_ventes_client_inconnu_raisonnable",
     "SELECT ROUND(100.0 * SUM(CASE WHEN cl.client_id = 'INCONNU' THEN 1 ELSE 0 END) / COUNT(*), 2)"
     " FROM dwh.fact_ventes f JOIN dwh.dim_client cl ON cl.client_sk = f.client_sk",
     lambda v: v is not None and v < 5),
]


def run_data_quality_checks(fail_fast: bool = True) -> list:
    engine = get_dwh_engine()
    results = []
    with engine.connect() as conn:
        for name, sql, predicate in CHECKS:
            value = conn.execute(text(sql)).scalar()
            ok = bool(predicate(value))
            results.append({"check": name, "value": value, "ok": ok})
            level = logger.info if ok else logger.error
            level("Contrôle qualité [%s] = %s -> %s", name, value, "OK" if ok else "ECHEC")

    echecs = [r for r in results if not r["ok"]]
    if echecs and fail_fast:
        raise AssertionError(f"Contrôles qualité en échec : {[e['check'] for e in echecs]}")
    return results
