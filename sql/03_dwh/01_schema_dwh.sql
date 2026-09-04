-- ============================================================================
-- NIMBA DISTRIBUTION - Data Warehouse (schéma en étoile)
-- ============================================================================
-- Modèle dimensionnel (Kimball) : granularité = la ligne de commande pour les
-- ventes, le relevé quotidien pour les stocks, le mois pour les objectifs.
--
-- Gestion des dimensions à évolution lente (SCD) :
--   - dim_client, dim_produit : SCD Type 2 (historisation complète)
--   - dim_magasin, dim_commercial, dim_canal_vente : SCD Type 1 (écrasement)
--
-- A exécuter sur la base : dwh
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS dwh;

-- ============================================================================
-- DIMENSIONS
-- ============================================================================

-- ----------------------------------------------------------------------------
-- dim_date : dimension calendaire, générée (voir 02_seed_dim_date.sql)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dwh.dim_date (
    date_id            INTEGER PRIMARY KEY,        -- format AAAAMMJJ
    date_complete       DATE NOT NULL UNIQUE,
    jour                SMALLINT NOT NULL,
    jour_semaine        SMALLINT NOT NULL,          -- 1=lundi ... 7=dimanche
    nom_jour             VARCHAR(15) NOT NULL,
    semaine_annee        SMALLINT NOT NULL,
    mois                 SMALLINT NOT NULL,
    nom_mois             VARCHAR(15) NOT NULL,
    trimestre            SMALLINT NOT NULL,
    annee                SMALLINT NOT NULL,
    annee_mois           VARCHAR(7) NOT NULL,        -- AAAA-MM, pratique pour les regroupements
    est_weekend          BOOLEAN NOT NULL,
    est_jour_ferie       BOOLEAN NOT NULL DEFAULT FALSE
);

-- ----------------------------------------------------------------------------
-- dim_client : SCD2 - historise les changements d'adresse / segment
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dwh.dim_client (
    client_sk           BIGSERIAL PRIMARY KEY,       -- clé de substitution
    client_id            TEXT NOT NULL,               -- clé naturelle (client_code source)
    nom                   VARCHAR(100),
    prenom                VARCHAR(100),
    email                 VARCHAR(150),
    telephone             VARCHAR(30),
    segment_client        VARCHAR(30),                -- ex: Particulier / Professionnel / VIP
    ville                 VARCHAR(100),
    region                VARCHAR(100),
    pays                  VARCHAR(100),
    date_inscription      DATE,
    date_debut_validite   DATE NOT NULL,
    date_fin_validite     DATE,
    est_version_courante  BOOLEAN NOT NULL DEFAULT TRUE,
    hash_attributs        VARCHAR(64) NOT NULL         -- empreinte des attributs suivis pour détecter les changements
);

CREATE INDEX IF NOT EXISTS idx_dim_client_id ON dwh.dim_client(client_id);
CREATE INDEX IF NOT EXISTS idx_dim_client_courant ON dwh.dim_client(client_id) WHERE est_version_courante;

-- ----------------------------------------------------------------------------
-- dim_produit : SCD2 - historise les changements de prix / catégorie
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dwh.dim_produit (
    produit_sk           BIGSERIAL PRIMARY KEY,
    produit_id            TEXT NOT NULL,
    nom_produit            VARCHAR(200),
    categorie              VARCHAR(100),
    sous_categorie         VARCHAR(100),
    marque                 VARCHAR(100),
    prix_unitaire          NUMERIC(12,2),
    cout_unitaire          NUMERIC(12,2),
    date_debut_validite    DATE NOT NULL,
    date_fin_validite      DATE,
    est_version_courante   BOOLEAN NOT NULL DEFAULT TRUE,
    hash_attributs         VARCHAR(64) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_dim_produit_id ON dwh.dim_produit(produit_id);
CREATE INDEX IF NOT EXISTS idx_dim_produit_courant ON dwh.dim_produit(produit_id) WHERE est_version_courante;

-- ----------------------------------------------------------------------------
-- dim_magasin : SCD1 - agences / magasins (zone géographique)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dwh.dim_magasin (
    magasin_sk           BIGSERIAL PRIMARY KEY,
    magasin_id            TEXT NOT NULL UNIQUE,
    nom_magasin            VARCHAR(150),
    type_magasin           VARCHAR(30),
    adresse                 VARCHAR(255),
    ville                   VARCHAR(100),
    region                  VARCHAR(100),
    pays                    VARCHAR(100),
    latitude                NUMERIC(9,6),
    longitude               NUMERIC(9,6),
    date_ouverture          DATE
);

-- ----------------------------------------------------------------------------
-- dim_commercial : SCD1 - force de vente
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dwh.dim_commercial (
    commercial_sk         BIGSERIAL PRIMARY KEY,
    commercial_id          TEXT NOT NULL UNIQUE,
    matricule               VARCHAR(20),
    nom                      VARCHAR(100),
    prenom                   VARCHAR(100),
    email                    VARCHAR(150),
    magasin_id               TEXT,                     -- magasin de rattachement (NK)
    date_embauche             DATE,
    statut                    VARCHAR(20)
);

-- ----------------------------------------------------------------------------
-- dim_canal_vente : petite dimension statique
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dwh.dim_canal_vente (
    canal_sk              SMALLSERIAL PRIMARY KEY,
    code_canal              VARCHAR(20) NOT NULL UNIQUE,
    libelle_canal           VARCHAR(50) NOT NULL
);

INSERT INTO dwh.dim_canal_vente (code_canal, libelle_canal) VALUES
    ('magasin', 'Vente en magasin'),
    ('en_ligne', 'Vente en ligne'),
    ('telephone', 'Vente par téléphone')
ON CONFLICT (code_canal) DO NOTHING;

-- ============================================================================
-- TABLES DE FAITS
-- ============================================================================

-- ----------------------------------------------------------------------------
-- fact_ventes : grain = une ligne de commande
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dwh.fact_ventes (
    vente_sk              BIGSERIAL PRIMARY KEY,
    date_id                 INTEGER NOT NULL REFERENCES dwh.dim_date(date_id),
    client_sk                BIGINT NOT NULL REFERENCES dwh.dim_client(client_sk),
    produit_sk                BIGINT NOT NULL REFERENCES dwh.dim_produit(produit_sk),
    magasin_sk                 BIGINT NOT NULL REFERENCES dwh.dim_magasin(magasin_sk),
    commercial_sk                BIGINT REFERENCES dwh.dim_commercial(commercial_sk),
    canal_sk                      SMALLINT NOT NULL REFERENCES dwh.dim_canal_vente(canal_sk),
    -- dimensions dégénérées (identifiants métier conservés dans le fait)
    numero_commande                 TEXT NOT NULL,
    ligne_id                          TEXT NOT NULL,
    statut_commande                    VARCHAR(20) NOT NULL,
    -- mesures
    quantite                            INTEGER NOT NULL,
    prix_unitaire_vente                  NUMERIC(12,2) NOT NULL,
    taux_remise                           NUMERIC(5,4) NOT NULL DEFAULT 0,
    montant_brut                           NUMERIC(14,2) NOT NULL,   -- quantite * prix_unitaire_vente
    montant_remise                          NUMERIC(14,2) NOT NULL,  -- montant_brut * taux_remise
    montant_net                              NUMERIC(14,2) NOT NULL, -- montant_brut - montant_remise (= CA)
    cout_total                                NUMERIC(14,2) NOT NULL,-- quantite * cout_unitaire (dim_produit à la date de vente)
    marge                                      NUMERIC(14,2) NOT NULL,-- montant_net - cout_total
    _batch_id                                    TEXT,
    _loaded_at                                    TIMESTAMP DEFAULT now(),
    UNIQUE (numero_commande, ligne_id)
);

CREATE INDEX IF NOT EXISTS idx_fact_ventes_date ON dwh.fact_ventes(date_id);
CREATE INDEX IF NOT EXISTS idx_fact_ventes_client ON dwh.fact_ventes(client_sk);
CREATE INDEX IF NOT EXISTS idx_fact_ventes_produit ON dwh.fact_ventes(produit_sk);
CREATE INDEX IF NOT EXISTS idx_fact_ventes_magasin ON dwh.fact_ventes(magasin_sk);
CREATE INDEX IF NOT EXISTS idx_fact_ventes_commercial ON dwh.fact_ventes(commercial_sk);

-- ----------------------------------------------------------------------------
-- fact_stock : grain = relevé quotidien par magasin / produit
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dwh.fact_stock (
    stock_sk               BIGSERIAL PRIMARY KEY,
    date_id                  INTEGER NOT NULL REFERENCES dwh.dim_date(date_id),
    produit_sk                 BIGINT NOT NULL REFERENCES dwh.dim_produit(produit_sk),
    magasin_sk                   BIGINT NOT NULL REFERENCES dwh.dim_magasin(magasin_sk),
    quantite_stock                 INTEGER NOT NULL,
    seuil_alerte                    INTEGER NOT NULL,
    valeur_stock                     NUMERIC(14,2) NOT NULL,   -- quantite_stock * cout_unitaire
    en_rupture                        BOOLEAN NOT NULL DEFAULT FALSE,
    _batch_id                          TEXT,
    _loaded_at                          TIMESTAMP DEFAULT now(),
    UNIQUE (date_id, produit_sk, magasin_sk)
);

CREATE INDEX IF NOT EXISTS idx_fact_stock_date ON dwh.fact_stock(date_id);
CREATE INDEX IF NOT EXISTS idx_fact_stock_produit ON dwh.fact_stock(produit_sk);
CREATE INDEX IF NOT EXISTS idx_fact_stock_magasin ON dwh.fact_stock(magasin_sk);

-- ----------------------------------------------------------------------------
-- fact_objectifs : grain = objectif mensuel par commercial
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dwh.fact_objectifs (
    objectif_sk             BIGSERIAL PRIMARY KEY,
    date_id                   INTEGER NOT NULL REFERENCES dwh.dim_date(date_id), -- 1er jour du mois
    commercial_sk               BIGINT NOT NULL REFERENCES dwh.dim_commercial(commercial_sk),
    magasin_sk                    BIGINT NOT NULL REFERENCES dwh.dim_magasin(magasin_sk),
    objectif_ca                     NUMERIC(14,2) NOT NULL,
    objectif_quantite                 INTEGER NOT NULL,
    _batch_id                          TEXT,
    _loaded_at                          TIMESTAMP DEFAULT now(),
    UNIQUE (date_id, commercial_sk)
);

CREATE INDEX IF NOT EXISTS idx_fact_objectifs_date ON dwh.fact_objectifs(date_id);
CREATE INDEX IF NOT EXISTS idx_fact_objectifs_commercial ON dwh.fact_objectifs(commercial_sk);

-- ----------------------------------------------------------------------------
-- dim_taux_change : dimension/fait de référence pour le module optionnel
-- (conversion GNF / EUR / USD), alimentée par API externe
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dwh.fact_taux_change (
    date_id                  INTEGER NOT NULL REFERENCES dwh.dim_date(date_id),
    devise_source              VARCHAR(3) NOT NULL,
    devise_cible                 VARCHAR(3) NOT NULL,
    taux                          NUMERIC(18,6) NOT NULL,
    _batch_id                      TEXT,
    _loaded_at                      TIMESTAMP DEFAULT now(),
    PRIMARY KEY (date_id, devise_source, devise_cible)
);

COMMENT ON SCHEMA dwh IS 'Modèle dimensionnel (schéma en étoile) de Nimba Distribution.';
COMMENT ON TABLE dwh.fact_ventes IS 'Table de faits principale. Grain : une ligne de commande.';
COMMENT ON TABLE dwh.fact_stock IS 'Table de faits de stock. Grain : relevé quotidien par magasin et par produit.';
COMMENT ON TABLE dwh.fact_objectifs IS 'Table de faits des objectifs commerciaux. Grain : objectif mensuel par commercial.';
