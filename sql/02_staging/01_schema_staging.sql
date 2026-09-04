-- ============================================================================
-- NIMBA DISTRIBUTION - Zone de Staging (Data Warehouse)
-- ============================================================================
-- La zone de staging reçoit les données brutes de chaque source, sans
-- transformation métier, avec des colonnes techniques de traçabilité.
-- Elle est purgée/rechargée à chaque exécution du pipeline ETL (stratégie
-- "truncate & load" adaptée à un référentiel de taille modérée).
--
-- A exécuter sur la base : dwh
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS staging;

-- ----------------------------------------------------------------------------
-- Colonnes techniques communes ajoutées par l'ETL à chaque table de staging :
--   _batch_id     : identifiant du lot d'exécution Airflow (run_id)
--   _source_file  : nom du fichier / table source
--   _loaded_at    : horodatage de chargement
-- ----------------------------------------------------------------------------

-- Source CSV : clients
CREATE TABLE IF NOT EXISTS staging.stg_clients (
    client_code         TEXT,
    nom                  TEXT,
    prenom               TEXT,
    email                TEXT,
    telephone            TEXT,
    date_inscription     TEXT,
    segment              TEXT,
    ville                TEXT,
    region               TEXT,
    pays                 TEXT,
    _batch_id            TEXT,
    _source_file         TEXT,
    _loaded_at           TIMESTAMP DEFAULT now()
);

-- Source Excel : produits
CREATE TABLE IF NOT EXISTS staging.stg_produits (
    produit_id           TEXT,
    nom_produit          TEXT,
    categorie            TEXT,
    sous_categorie       TEXT,
    marque               TEXT,
    prix_unitaire        TEXT,
    cout_unitaire        TEXT,
    date_maj             TEXT,
    _batch_id            TEXT,
    _source_file         TEXT,
    _loaded_at           TIMESTAMP DEFAULT now()
);

-- Source Excel : objectifs commerciaux
CREATE TABLE IF NOT EXISTS staging.stg_objectifs (
    annee_mois           TEXT,
    matricule_commercial TEXT,
    magasin_id           TEXT,
    objectif_ca          TEXT,
    objectif_quantite    TEXT,
    _batch_id            TEXT,
    _source_file         TEXT,
    _loaded_at           TIMESTAMP DEFAULT now()
);

-- Source JSON : magasins / agences
CREATE TABLE IF NOT EXISTS staging.stg_magasins (
    magasin_id           TEXT,
    nom_magasin          TEXT,
    type_magasin         TEXT,
    adresse              TEXT,
    ville                TEXT,
    region               TEXT,
    pays                 TEXT,
    latitude             TEXT,
    longitude            TEXT,
    date_ouverture       TEXT,
    _batch_id            TEXT,
    _source_file         TEXT,
    _loaded_at           TIMESTAMP DEFAULT now()
);

-- Source relationnelle (ERP) : commerciaux
CREATE TABLE IF NOT EXISTS staging.stg_commerciaux (
    commercial_id        TEXT,
    matricule            TEXT,
    nom                   TEXT,
    prenom                TEXT,
    email                 TEXT,
    magasin_id            TEXT,
    date_embauche         TEXT,
    statut                TEXT,
    _batch_id             TEXT,
    _source_file          TEXT,
    _loaded_at            TIMESTAMP DEFAULT now()
);

-- Source relationnelle (ERP) : commandes + lignes (dénormalisées au niveau ligne)
CREATE TABLE IF NOT EXISTS staging.stg_ventes (
    commande_id           TEXT,
    numero_commande       TEXT,
    ligne_id              TEXT,
    client_code           TEXT,
    magasin_id            TEXT,
    commercial_id         TEXT,
    canal_vente           TEXT,
    date_commande         TEXT,
    statut_commande       TEXT,
    produit_id            TEXT,
    quantite              TEXT,
    prix_unitaire_vente   TEXT,
    taux_remise           TEXT,
    _batch_id             TEXT,
    _source_file          TEXT,
    _loaded_at            TIMESTAMP DEFAULT now()
);

-- Source relationnelle (ERP) : stocks
CREATE TABLE IF NOT EXISTS staging.stg_stocks (
    date_releve           TEXT,
    magasin_id            TEXT,
    produit_id             TEXT,
    quantite_stock         TEXT,
    seuil_alerte           TEXT,
    _batch_id              TEXT,
    _source_file            TEXT,
    _loaded_at              TIMESTAMP DEFAULT now()
);

-- Source API externe (optionnelle) : taux de change
CREATE TABLE IF NOT EXISTS staging.stg_taux_change (
    date_taux              TEXT,
    devise_source          TEXT,
    devise_cible            TEXT,
    taux                    TEXT,
    _batch_id                TEXT,
    _source_file              TEXT,
    _loaded_at                TIMESTAMP DEFAULT now()
);

COMMENT ON SCHEMA staging IS 'Zone de staging du Data Warehouse : dépôt brut des données sources avant transformation.';
