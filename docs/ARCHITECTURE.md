# Schéma d'architecture — SID Nimba Distribution

## Vue simplifiée

Pour comprendre le principe en un coup d'œil : les données brutes (fichiers et bases sources) sont collectées et mises en forme par un pipeline ETL, stockées dans un Data Warehouse organisé en schéma en étoile, puis restituées sous forme de tableau de bord. L'ensemble est rejoué automatiquement chaque jour par Airflow.

```mermaid
flowchart LR
    SRC["Sources de données
    CSV · Excel · JSON
    Base ERP · API taux de change"]
    ETL["Pipeline ETL
    Python / pandas
    (extraction -> transformation -> chargement)"]
    DWH[("Data Warehouse
    PostgreSQL
    schéma en étoile")]
    BI["Tableau de bord
    Apache Superset
    Pilotage commercial"]
    AIRFLOW["Orchestration
    Apache Airflow
    (DAG quotidien, 03h00)"]

    SRC --> ETL --> DWH --> BI
    AIRFLOW -. orchestre chaque étape .-> ETL

    classDef store fill:#e8f0fe,stroke:#4285f4,stroke-width:1px;
    classDef step fill:#fff8e1,stroke:#f9a825,stroke-width:1px;
    classDef orch fill:#f3e5f5,stroke:#8e24aa,stroke-width:1px,stroke-dasharray: 3 3;
    class SRC,DWH,BI store;
    class ETL step;
    class AIRFLOW orch;
```

## Vue détaillée

La vue ci-dessous détaille chaque étape technique du flux (staging, chargement des dimensions/faits, contrôles qualité, vues de restitution) :

```mermaid
flowchart LR
    subgraph SOURCES["Sources de données"]
        direction TB
        CSV["clients.csv\n(CSV)"]
        XLS1["produits.xlsx\n(Excel)"]
        XLS2["objectifs.xlsx\n(Excel)"]
        JSON["magasins.json\n(JSON)"]
        ERP[("erp_source\nPostgreSQL (OLTP)\ncommerciaux / commandes /\nlignes_commande / stocks")]
        API["API externe\ntaux de change\n(optionnel)"]
    end

    subgraph ETL["Pipeline ETL — Python / pandas"]
        direction TB
        EXTRACT["Extraction\n(etl/extract/*)"]
        STAGING[("staging.*\nPostgreSQL (dwh)")]
        LOADDIM["Chargement dimensions\nSCD1 / SCD2\n(etl/load/load_dimensions.py)"]
        LOADFACT["Chargement faits\n(etl/load/load_facts.py)"]
        DQ["Contrôles qualité\n(etl/utils/data_quality.py)"]
    end

    subgraph AIRFLOW["Orchestration — Apache Airflow"]
        DAG["DAG quotidien\nsid_nimba_distribution_daily"]
    end

    subgraph DWH["Data Warehouse — schéma en étoile"]
        direction TB
        DIMS[("Dimensions\ndim_date, dim_client*, dim_produit*,\ndim_magasin, dim_commercial, dim_canal_vente")]
        FACTS[("Faits\nfact_ventes, fact_stock,\nfact_objectifs, fact_taux_change")]
        MART[("Vues mart.*\n(1 vue par indicateur)")]
    end

    subgraph BI["Restitution — Apache Superset"]
        DASH["Tableau de bord\nPilotage commercial\n(10 graphiques)"]
    end

    CSV --> EXTRACT
    XLS1 --> EXTRACT
    XLS2 --> EXTRACT
    JSON --> EXTRACT
    ERP --> EXTRACT
    API --> EXTRACT

    EXTRACT --> STAGING
    STAGING --> LOADDIM --> DIMS
    STAGING --> LOADFACT
    DIMS --> LOADFACT --> FACTS
    FACTS --> DQ
    DIMS --> MART
    FACTS --> MART
    MART --> DASH

    DAG -. orchestre .-> EXTRACT
    DAG -. orchestre .-> LOADDIM
    DAG -. orchestre .-> LOADFACT
    DAG -. orchestre .-> DQ

    classDef store fill:#e8f0fe,stroke:#4285f4;
    class STAGING,DIMS,FACTS,MART,ERP store;
```

*(dim_client et dim_produit sont gérées en SCD Type 2 ; dim_magasin, dim_commercial et dim_canal_vente en SCD Type 1 — voir `docs/MODELE_DIMENSIONNEL.md`.)*

## Déploiement (Docker Compose)

```mermaid
flowchart TB
    subgraph HOST["Machine hôte (docker compose up)"]
        subgraph NET["Réseau Docker sid-nimba-distribution"]
            PG["postgres:16\n(port 5432)\nerp_source / dwh / airflow / superset"]
            AWI["airflow-init\n(migration + admin, one-shot)"]
            AWW["airflow-webserver\n(port 8080)"]
            AWS["airflow-scheduler"]
            SS["superset\n(port 8088)"]
            SP["superset-provision\n(one-shot : datasets + charts + dashboard)"]
            ET["etl-tools\n(profil 'tools' : génération de données,\nexécution manuelle du pipeline)"]
        end
        VOL1[("volume pgdata")]
        VOL2[("volume airflow_logs")]
        VOL3[("volume superset_home")]
    end

    PG --> VOL1
    AWS --> VOL2
    SS --> VOL3
    AWI --> PG
    AWW --> PG
    AWS --> PG
    SS --> PG
    SP -->|API REST| SS
    ET --> PG

    UTIL["Utilisateur"] -->|:8080 - pilotage ETL| AWW
    UTIL -->|:8088 - tableaux de bord| SS
```

## Composants et rôles

| Composant | Rôle | Technologie |
|---|---|---|
| Sources | Systèmes producteurs de données (fichiers plats, ERP, API) | CSV, Excel, JSON, PostgreSQL (OLTP), API REST |
| ETL | Extraction, transformation, chargement | Python 3.11, pandas, SQLAlchemy |
| Orchestrateur | Planification, dépendances, reprise sur erreur | Apache Airflow (LocalExecutor) |
| Entrepôt de données | Stockage staging + modèle en étoile + vues de restitution | PostgreSQL 16 |
| Restitution | Tableaux de bord décisionnels | Apache Superset |
| Déploiement | Reproductibilité, isolation, orchestration des services | Docker Compose |
| Versionnement | Traçabilité du code et de la configuration | Git / GitHub |
