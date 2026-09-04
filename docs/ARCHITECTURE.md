# Schéma d'architecture — SID Nimba Distribution

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
        FACTS[("Faits\nfact_ventes, fact_stock,\nfact_objectifs")]
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

## Composants et rôles

| Composant | Rôle | Technologie |
|---|---|---|
| Sources | Systèmes producteurs de données (fichiers plats, ERP) | CSV, Excel, JSON, PostgreSQL (OLTP) |
| ETL | Extraction, transformation, chargement | Python 3.11, pandas, SQLAlchemy |
| Orchestrateur | Planification, dépendances, reprise sur erreur | Apache Airflow (LocalExecutor) |
| Entrepôt de données | Stockage staging + modèle en étoile + vues de restitution | PostgreSQL 16 |
| Restitution | Tableaux de bord décisionnels | Apache Superset |
| Déploiement | Reproductibilité, isolation, orchestration des services | Docker Compose |
| Versionnement | Traçabilité du code et de la configuration | Git / GitHub |
