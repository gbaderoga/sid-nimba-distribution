#!/usr/bin/env python3
"""Provisionne automatiquement, via l'API REST de Superset, le tableau de
bord de restitution de Nimba Distribution : connexion à la base dwh, un
dataset par vue de mart.*, un jeu de graphiques par indicateur, puis un
tableau de bord regroupant l'ensemble.

Idempotent : peut être rejoué sans créer de doublons (recherche par nom
avant création).

Variables d'environnement :
    SUPERSET_URL            (def: http://localhost:8088)
    SUPERSET_ADMIN_USER     (def: admin)
    SUPERSET_ADMIN_PASSWORD (def: admin)
    POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST, POSTGRES_PORT,
    POSTGRES_DB_DWH          (paramètres de connexion à la base dwh, utilisés
                               pour construire l'URI SQLAlchemy enregistrée
                               dans Superset)
"""
import os
import sys
import time

import prison
import requests

SUPERSET_URL = os.getenv("SUPERSET_URL", "http://localhost:8088").rstrip("/")
ADMIN_USER = os.getenv("SUPERSET_ADMIN_USER", "admin")
ADMIN_PASSWORD = os.getenv("SUPERSET_ADMIN_PASSWORD", "admin")

PG_USER = os.getenv("POSTGRES_USER", "postgres")
PG_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
PG_HOST = os.getenv("POSTGRES_HOST", "postgres")
PG_PORT = os.getenv("POSTGRES_PORT", "5432")
PG_DB_DWH = os.getenv("POSTGRES_DB_DWH", "dwh")

DATABASE_NAME = "Nimba Distribution - DWH"
DATABASE_URI = f"postgresql+psycopg2://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{PG_DB_DWH}"

DASHBOARD_TITLE = "Nimba Distribution - Pilotage commercial"


class SupersetClient:
    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url
        self.session = requests.Session()
        self.access_token = None
        self._login(username, password)
        self._refresh_csrf()

    def _login(self, username, password):
        resp = self.session.post(
            f"{self.base_url}/api/v1/security/login",
            json={"username": username, "password": password, "provider": "db", "refresh": True},
            timeout=15,
        )
        resp.raise_for_status()
        self.access_token = resp.json()["access_token"]
        self.session.headers.update({"Authorization": f"Bearer {self.access_token}"})

    def _refresh_csrf(self):
        resp = self.session.get(f"{self.base_url}/api/v1/security/csrf_token/", timeout=15)
        resp.raise_for_status()
        csrf_token = resp.json()["result"]
        self.session.headers.update({"X-CSRFToken": csrf_token, "Referer": self.base_url})

    def get(self, path, **kw):
        r = self.session.get(f"{self.base_url}{path}", timeout=30, **kw)
        r.raise_for_status()
        return r.json()

    def post(self, path, **kw):
        r = self.session.post(f"{self.base_url}{path}", timeout=30, **kw)
        if not r.ok:
            print(f"ERREUR POST {path} -> {r.status_code}\n{r.text[:2000]}", file=sys.stderr)
        r.raise_for_status()
        return r.json()

    def put(self, path, **kw):
        r = self.session.put(f"{self.base_url}{path}", timeout=30, **kw)
        if not r.ok:
            print(f"ERREUR PUT {path} -> {r.status_code}\n{r.text[:2000]}", file=sys.stderr)
        r.raise_for_status()
        return r.json()

    def find_one(self, resource, name_field, name_value):
        q = prison.dumps({"filters": [{"col": name_field, "opr": "eq", "value": name_value}]})
        data = self.get(f"/api/v1/{resource}/?q={requests.utils.quote(q)}")
        results = data.get("result", [])
        return results[0] if results else None


def ensure_database(client: SupersetClient) -> int:
    existing = client.find_one("database", "database_name", DATABASE_NAME)
    if existing:
        print(f"[OK] Base déjà enregistrée (id={existing['id']})")
        return existing["id"]
    payload = {
        "database_name": DATABASE_NAME,
        "sqlalchemy_uri": DATABASE_URI,
        "expose_in_sqllab": True,
    }
    result = client.post("/api/v1/database/", json=payload)
    print(f"[+] Base créée (id={result['id']})")
    return result["id"]


def ensure_dataset(client: SupersetClient, database_id: int, table_name: str, schema: str = "mart") -> dict:
    existing = client.find_one("dataset", "table_name", table_name)
    if existing:
        print(f"[OK] Dataset {table_name} déjà présent (id={existing['id']})")
        full = client.get(f"/api/v1/dataset/{existing['id']}")["result"]
        return full
    payload = {"database": database_id, "schema": schema, "table_name": table_name}
    result = client.post("/api/v1/dataset/", json=payload)
    dataset_id = result["id"]
    print(f"[+] Dataset {table_name} créé (id={dataset_id})")
    full = client.get(f"/api/v1/dataset/{dataset_id}")["result"]
    return full


def col_type(dataset: dict, col_name: str) -> str:
    for c in dataset.get("columns", []):
        if c["column_name"] == col_name:
            return c.get("type", "VARCHAR")
    return "VARCHAR"


def ensure_chart(client: SupersetClient, slice_name: str, dataset: dict, viz_type: str, params: dict,
                  query_context_extra: dict = None) -> int:
    existing = client.find_one("chart", "slice_name", slice_name)
    import json as _json
    params_full = {"datasource": f"{dataset['id']}__table", "viz_type": viz_type, **params}
    payload = {
        "slice_name": slice_name,
        "viz_type": viz_type,
        "datasource_id": dataset["id"],
        "datasource_type": "table",
        "params": _json.dumps(params_full),
    }
    if existing:
        client.put(f"/api/v1/chart/{existing['id']}", json=payload)
        print(f"[OK] Graphique mis à jour : {slice_name} (id={existing['id']})")
        return existing["id"]
    result = client.post("/api/v1/chart/", json=payload)
    print(f"[+] Graphique créé : {slice_name} (id={result['id']})")
    return result["id"]


def ensure_dashboard(client: SupersetClient, title: str, chart_ids: list) -> int:
    existing = client.find_one("dashboard", "dashboard_title", title)

    # Layout en grille simple : une rangée de 2 graphiques par ligne
    import json as _json
    rows = []
    for i in range(0, len(chart_ids), 2):
        rows.append(chart_ids[i:i + 2])

    position_json = {"DASHBOARD_VERSION_KEY": "v2"}
    grid_children = []
    row_idx = 0
    for row in rows:
        row_id = f"ROW-{row_idx}"
        chart_children = []
        for chart_id in row:
            chart_uuid = f"CHART-{chart_id}"
            chart_children.append(chart_uuid)
            position_json[chart_uuid] = {
                "type": "CHART",
                "id": chart_uuid,
                "children": [],
                "meta": {"chartId": chart_id, "width": 6, "height": 50},
            }
        position_json[row_id] = {
            "type": "ROW",
            "id": row_id,
            "children": chart_children,
            "meta": {"background": "BACKGROUND_TRANSPARENT"},
        }
        grid_children.append(row_id)
        row_idx += 1

    position_json["GRID_ID"] = {"type": "GRID", "id": "GRID_ID", "children": grid_children}
    position_json["ROOT_ID"] = {"type": "ROOT", "id": "ROOT_ID", "children": ["GRID_ID"]}
    position_json["HEADER_ID"] = {"type": "HEADER", "id": "HEADER_ID", "meta": {"text": title}}

    payload = {
        "dashboard_title": title,
        "position_json": _json.dumps(position_json),
        "json_metadata": _json.dumps({"native_filter_configuration": []}),
    }

    if existing:
        dash_id = existing["id"]
        client.put(f"/api/v1/dashboard/{dash_id}", json=payload)
        print(f"[OK] Tableau de bord mis à jour (id={dash_id})")
    else:
        result = client.post("/api/v1/dashboard/", json=payload)
        dash_id = result["id"]
        print(f"[+] Tableau de bord créé (id={dash_id})")

    # rattache les graphiques au dashboard (charge côté chart.dashboards)
    for chart_id in chart_ids:
        client.put(f"/api/v1/chart/{chart_id}", json={"dashboards": [dash_id]})

    return dash_id


def main():
    print(f"Connexion à Superset ({SUPERSET_URL})...")
    client = SupersetClient(SUPERSET_URL, ADMIN_USER, ADMIN_PASSWORD)

    database_id = ensure_database(client)

    ds_ca = ensure_dataset(client, database_id, "v_ca_mensuel")
    ds_produit = ensure_dataset(client, database_id, "v_performance_produit")
    ds_zone = ensure_dataset(client, database_id, "v_performance_zone")
    ds_commercial = ensure_dataset(client, database_id, "v_performance_commerciale")
    ds_objectifs = ensure_dataset(client, database_id, "v_atteinte_objectifs")
    ds_client = ensure_dataset(client, database_id, "v_comportement_client")
    ds_stock = ensure_dataset(client, database_id, "v_situation_stock")

    chart_ids = []

    # Format numérique fixe (séparateur de milliers, 0 décimale) pour les
    # montants déjà exprimés en milliers de GNF : évite que Superset applique
    # en plus son propre arrondi adaptatif (k/M), ce qui donnerait par ex.
    # "2.1k" pour une valeur qui est déjà "2 119" (milliers de GNF).
    FMT_MILLIERS_GNF = ",.0f"

    # 1. KPI global : CA total
    chart_ids.append(ensure_chart(
        client, "KPI - Chiffre d'affaires total", ds_ca, "big_number_total",
        {
            "metric": {"expressionType": "SIMPLE", "column": {"column_name": "chiffre_affaires_k_gnf"},
                       "aggregate": "SUM", "label": "CA total (milliers GNF)"},
            "adhoc_filters": [],
            "header_font_size": 0.4, "subheader_font_size": 0.15,
            "subheader": "milliers de GNF",
            "y_axis_format": FMT_MILLIERS_GNF,
        },
    ))

    # 2. Évolution mensuelle du CA (courbe)
    chart_ids.append(ensure_chart(
        client, "Évolution mensuelle du chiffre d'affaires", ds_ca, "echarts_timeseries_line",
        {
            "x_axis": "annee_mois",
            "metrics": [{"expressionType": "SIMPLE", "column": {"column_name": "chiffre_affaires_k_gnf"},
                         "aggregate": "SUM", "label": "CA (milliers GNF)"}],
            "groupby": [], "adhoc_filters": [], "row_limit": 1000,
            "x_axis_sort_asc": True, "x_axis_time_format": "smart_date",
            "y_axis_format": FMT_MILLIERS_GNF,
        },
    ))

    # 3. Top 10 produits par CA
    chart_ids.append(ensure_chart(
        client, "Top 10 produits par chiffre d'affaires", ds_produit, "dist_bar",
        {
            "groupby": ["nom_produit"],
            "metrics": [{"expressionType": "SIMPLE", "column": {"column_name": "chiffre_affaires_k_gnf"},
                         "aggregate": "SUM", "label": "CA (milliers GNF)"}],
            "adhoc_filters": [], "row_limit": 10,
            "order_by_cols": ['["sum__chiffre_affaires_k_gnf", false]'],
            "y_axis_format": FMT_MILLIERS_GNF,
        },
    ))

    # 4. Répartition du CA par catégorie de produit
    chart_ids.append(ensure_chart(
        client, "Répartition du CA par catégorie de produit", ds_produit, "pie",
        {
            "groupby": ["categorie"],
            "metric": {"expressionType": "SIMPLE", "column": {"column_name": "chiffre_affaires_k_gnf"},
                       "aggregate": "SUM", "label": "CA (milliers GNF)"},
            "adhoc_filters": [], "row_limit": 20,
            "number_format": FMT_MILLIERS_GNF,
        },
    ))

    # 5. CA par ville (zone géographique)
    chart_ids.append(ensure_chart(
        client, "Chiffre d'affaires par ville", ds_zone, "dist_bar",
        {
            "groupby": ["ville"],
            "metrics": [{"expressionType": "SIMPLE", "column": {"column_name": "chiffre_affaires_k_gnf"},
                         "aggregate": "SUM", "label": "CA (milliers GNF)"}],
            "adhoc_filters": [], "row_limit": 20,
            "y_axis_format": FMT_MILLIERS_GNF,
        },
    ))

    # 6. Performance par magasin (table)
    chart_ids.append(ensure_chart(
        client, "Performance par magasin", ds_zone, "table",
        {
            "query_mode": "aggregate",
            "groupby": ["nom_magasin", "ville"],
            "metrics": [
                {"expressionType": "SIMPLE", "column": {"column_name": "chiffre_affaires_k_gnf"},
                 "aggregate": "SUM", "label": "CA (milliers GNF)"},
                {"expressionType": "SIMPLE", "column": {"column_name": "nb_commandes"},
                 "aggregate": "SUM", "label": "Nb commandes"},
            ],
            "adhoc_filters": [], "row_limit": 50,
            "order_by_cols": ['["sum__chiffre_affaires_k_gnf", false]'],
            "column_config": {
                "CA (milliers GNF)": {"d3NumberFormat": FMT_MILLIERS_GNF},
            },
        },
    ))

    # 7. Performance commerciale (table)
    chart_ids.append(ensure_chart(
        client, "Performance des commerciaux", ds_commercial, "table",
        {
            "query_mode": "aggregate",
            "groupby": ["nom_commercial"],
            "metrics": [
                {"expressionType": "SIMPLE", "column": {"column_name": "ca_realise_k_gnf"},
                 "aggregate": "SUM", "label": "CA réalisé (milliers GNF)"},
                {"expressionType": "SIMPLE", "column": {"column_name": "objectif_ca_k_gnf"},
                 "aggregate": "SUM", "label": "Objectif CA (milliers GNF)"},
            ],
            "adhoc_filters": [], "row_limit": 50,
            "order_by_cols": ['["sum__ca_realise_k_gnf", false]'],
            "column_config": {
                "CA réalisé (milliers GNF)": {"d3NumberFormat": FMT_MILLIERS_GNF},
                "Objectif CA (milliers GNF)": {"d3NumberFormat": FMT_MILLIERS_GNF},
            },
        },
    ))

    # 8. Atteinte des objectifs par magasin (table)
    chart_ids.append(ensure_chart(
        client, "Atteinte des objectifs par magasin", ds_objectifs, "table",
        {
            "query_mode": "aggregate",
            "groupby": ["nom_magasin"],
            "metrics": [
                {"expressionType": "SIMPLE", "column": {"column_name": "objectif_ca_k_gnf"},
                 "aggregate": "SUM", "label": "Objectif CA (milliers GNF)"},
                {"expressionType": "SIMPLE", "column": {"column_name": "ca_realise_k_gnf"},
                 "aggregate": "SUM", "label": "CA réalisé (milliers GNF)"},
            ],
            "adhoc_filters": [], "row_limit": 50,
            "order_by_cols": ['["sum__ca_realise_k_gnf", false]'],
            "column_config": {
                "Objectif CA (milliers GNF)": {"d3NumberFormat": FMT_MILLIERS_GNF},
                "CA réalisé (milliers GNF)": {"d3NumberFormat": FMT_MILLIERS_GNF},
            },
        },
    ))

    # 9. Segmentation comportementale des clients (RFM)
    chart_ids.append(ensure_chart(
        client, "Segmentation comportementale des clients (RFM)", ds_client, "pie",
        {
            "groupby": ["segment_comportemental"],
            "metric": {"expressionType": "SIMPLE", "column": {"column_name": "client_id"},
                       "aggregate": "COUNT", "label": "Nombre de clients"},
            "adhoc_filters": [], "row_limit": 20,
        },
    ))

    # 10. Ruptures de stock par magasin
    chart_ids.append(ensure_chart(
        client, "Alertes de rupture de stock par magasin", ds_stock, "dist_bar",
        {
            "groupby": ["nom_magasin"],
            "metrics": [{"expressionType": "SIMPLE", "column": {"column_name": "produit_id"},
                         "aggregate": "COUNT", "label": "Nb relevés en rupture"}],
            "adhoc_filters": [{"clause": "WHERE", "subject": "en_rupture", "operator": "==",
                                "comparator": "true", "expressionType": "SIMPLE"}],
            "row_limit": 20,
        },
    ))

    dashboard_id = ensure_dashboard(client, DASHBOARD_TITLE, chart_ids)

    print(f"\nTableau de bord prêt : {SUPERSET_URL}/superset/dashboard/{dashboard_id}/")


if __name__ == "__main__":
    main()
