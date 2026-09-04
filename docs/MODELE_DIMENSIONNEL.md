# Modèle dimensionnel — SID Nimba Distribution

Modèle en étoile (approche Kimball), implémenté dans le schéma `dwh` de la base PostgreSQL `dwh` (scripts : `sql/03_dwh/`). Les vues de restitution consommées par Superset vivent dans le schéma `mart` (`sql/04_views/`).

## Schéma en étoile

```mermaid
erDiagram
    DIM_DATE ||--o{ FACT_VENTES : "date_id"
    DIM_CLIENT ||--o{ FACT_VENTES : "client_sk"
    DIM_PRODUIT ||--o{ FACT_VENTES : "produit_sk"
    DIM_MAGASIN ||--o{ FACT_VENTES : "magasin_sk"
    DIM_COMMERCIAL ||--o{ FACT_VENTES : "commercial_sk"
    DIM_CANAL_VENTE ||--o{ FACT_VENTES : "canal_sk"

    DIM_DATE ||--o{ FACT_STOCK : "date_id"
    DIM_PRODUIT ||--o{ FACT_STOCK : "produit_sk"
    DIM_MAGASIN ||--o{ FACT_STOCK : "magasin_sk"

    DIM_DATE ||--o{ FACT_OBJECTIFS : "date_id"
    DIM_COMMERCIAL ||--o{ FACT_OBJECTIFS : "commercial_sk"
    DIM_MAGASIN ||--o{ FACT_OBJECTIFS : "magasin_sk"

    DIM_DATE ||--o{ FACT_TAUX_CHANGE : "date_id"

    FACT_VENTES {
        bigint vente_sk PK
        int date_id FK
        bigint client_sk FK
        bigint produit_sk FK
        bigint magasin_sk FK
        bigint commercial_sk FK
        smallint canal_sk FK
        text numero_commande "dimension dégénérée"
        text ligne_id "dimension dégénérée"
        int quantite
        numeric montant_net "= CA"
        numeric marge
    }

    FACT_STOCK {
        bigint stock_sk PK
        int date_id FK
        bigint produit_sk FK
        bigint magasin_sk FK
        int quantite_stock
        numeric valeur_stock
        boolean en_rupture
    }

    FACT_OBJECTIFS {
        bigint objectif_sk PK
        int date_id FK
        bigint commercial_sk FK
        bigint magasin_sk FK
        numeric objectif_ca
        int objectif_quantite
    }

    FACT_TAUX_CHANGE {
        int date_id FK
        varchar devise_source
        varchar devise_cible
        numeric taux
    }

    DIM_DATE {
        int date_id PK
        date date_complete
        smallint mois
        smallint annee
        varchar annee_mois
        boolean est_weekend
    }

    DIM_CLIENT {
        bigint client_sk PK
        text client_id "clé métier"
        varchar segment_client
        varchar ville
        varchar region
        varchar pays
        date date_debut_validite
        date date_fin_validite
        boolean est_version_courante
    }

    DIM_PRODUIT {
        bigint produit_sk PK
        text produit_id "clé métier"
        varchar categorie
        varchar sous_categorie
        numeric prix_unitaire
        numeric cout_unitaire
        boolean est_version_courante
    }

    DIM_MAGASIN {
        bigint magasin_sk PK
        text magasin_id "clé métier"
        varchar ville
        varchar region
        varchar pays
    }

    DIM_COMMERCIAL {
        bigint commercial_sk PK
        text commercial_id "clé métier = matricule"
        varchar statut
    }

    DIM_CANAL_VENTE {
        smallint canal_sk PK
        varchar code_canal
    }
```

## Granularité des tables de faits

| Table de faits | Grain (une ligne = ...) | Mesures principales |
|---|---|---|
| `fact_ventes` | Une ligne de commande (un produit, dans une commande, à une date, un magasin, un commercial) | `quantite`, `montant_brut`, `montant_remise`, `montant_net` (= CA), `cout_total`, `marge` |
| `fact_stock` | Un relevé de stock pour un produit, dans un magasin, à une date donnée | `quantite_stock`, `valeur_stock`, `en_rupture` |
| `fact_objectifs` | Un objectif mensuel pour un commercial (rattaché à un magasin) | `objectif_ca`, `objectif_quantite` |
| `fact_taux_change` | Un taux de change pour une paire de devises, à une date | `taux` |

## Stratégie SCD par dimension

| Dimension | Type SCD | Justification |
|---|---|---|
| `dim_date` | Statique (générée) | Dimension calendaire, ne varie jamais |
| `dim_client` | **SCD 2** | Le segment, la ville ou la région d'un client peuvent évoluer ; l'historique a une valeur analytique (ex. : CA généré avant/après un changement de segment) |
| `dim_produit` | **SCD 2** | Le prix ou la catégorie d'un produit évoluent ; une vente doit rester associée au prix/coût en vigueur à sa date |
| `dim_magasin` | SCD 1 | Attributs stables (adresse, géolocalisation) ; l'historisation n'apporte pas de valeur analytique pour ce périmètre |
| `dim_commercial` | SCD 1 | Idem ; seul le statut (actif/inactif) change occasionnellement |
| `dim_canal_vente` | Statique | 3 valeurs fixes (magasin / en ligne / téléphone) |

## Clés de substitution et membres "inconnu"

Chaque dimension expose une clé de substitution technique (`*_sk`, `BIGSERIAL`) distincte de sa clé métier (`*_id`), condition nécessaire à l'implémentation du SCD Type 2 (plusieurs lignes physiques peuvent partager la même clé métier). Chaque dimension possède également un **membre "INCONNU"** (voir `sql/03_dwh/03_seed_membres_inconnus.sql`) : une ligne de fait dont une clé étrangère ne peut être résolue (référentiel incomplet, incohérence source) est rattachée à ce membre plutôt que d'être rejetée, conformément aux bonnes pratiques Kimball — vérifié par le contrôle qualité `part_ventes_client_inconnu_raisonnable`.
