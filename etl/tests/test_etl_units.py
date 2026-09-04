"""Tests unitaires légers (sans dépendance à une base de données) pour les
fonctions pures du pipeline ETL. Complète les tests d'intégration décrits
dans docs/RAPPORT_SYNTHESE.md (exécutés manuellement contre une base réelle).

Lancer avec : pytest etl/tests/ -v
"""
import datetime
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from etl.load.scd_utils import _row_hash  # noqa: E402


def test_row_hash_is_deterministic():
    row = pd.Series({"nom": "Diallo", "ville": "Conakry"})
    h1 = _row_hash(row, ["nom", "ville"])
    h2 = _row_hash(row, ["nom", "ville"])
    assert h1 == h2
    assert len(h1) == 64  # sha256 hex digest


def test_row_hash_changes_when_attribute_changes():
    row_a = pd.Series({"nom": "Diallo", "ville": "Conakry"})
    row_b = pd.Series({"nom": "Diallo", "ville": "Kankan"})
    assert _row_hash(row_a, ["nom", "ville"]) != _row_hash(row_b, ["nom", "ville"])


def test_row_hash_ignores_untracked_columns():
    row_a = pd.Series({"nom": "Diallo", "ville": "Conakry", "email": "a@example.com"})
    row_b = pd.Series({"nom": "Diallo", "ville": "Conakry", "email": "b@example.com"})
    assert _row_hash(row_a, ["nom", "ville"]) == _row_hash(row_b, ["nom", "ville"])


def test_staging_dataframe_preserves_none_for_missing_values():
    # Reproduit la logique de conversion de types de load_dataframe_to_staging
    # (sans appel DB ici). NB : sous pandas >= 3.0, une colonne convertie en
    # dtype "str" représente les valeurs manquantes par son propre sentinel NA
    # (pd.isna(...) == True) plutôt que par l'objet Python `None` au sens
    # strict (`is None`) - la vérification robuste est donc pd.isna(), et
    # c'est bien ce sentinel qu'écrit correctement SQLAlchemy/psycopg2 en NULL
    # SQL (vérifié par un test d'intégration direct contre PostgreSQL, voir
    # docs/RAPPORT_SYNTHESE.md).
    df = pd.DataFrame({"a": [1, None, "x"], "b": [None, 2.5, "y"]})
    for col in df.columns:
        df[col] = df[col].apply(lambda v: None if pd.isna(v) else str(v))
    assert pd.isna(df.loc[1, "a"])
    assert df.loc[0, "a"] == "1"
    assert df.loc[1, "b"] == "2.5"


def test_new_batch_id_format():
    from etl.run_pipeline import new_batch_id
    batch_id = new_batch_id()
    # format attendu : AAAAMMJJ_HHMMSS
    datetime.datetime.strptime(batch_id, "%Y%m%d_%H%M%S")
