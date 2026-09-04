-- ============================================================================
-- NIMBA DISTRIBUTION - Système Source ERP/CRM (OLTP)
-- ============================================================================
-- Ce script simule le système opérationnel (ERP/CRM) de l'entreprise :
-- une base relationnelle distincte du Data Warehouse, représentative d'une
-- application métier de gestion des commandes, des commerciaux et des stocks.
--
-- A exécuter sur la base : erp_source
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS erp;

-- ----------------------------------------------------------------------------
-- Commerciaux (force de vente)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS erp.commerciaux (
    commercial_id      SERIAL PRIMARY KEY,
    matricule          VARCHAR(20) UNIQUE NOT NULL,
    nom                VARCHAR(100) NOT NULL,
    prenom             VARCHAR(100) NOT NULL,
    email              VARCHAR(150),
    magasin_id         VARCHAR(20) NOT NULL,      -- FK logique vers magasins.json (dim_magasin)
    date_embauche      DATE NOT NULL,
    statut             VARCHAR(20) NOT NULL DEFAULT 'actif' CHECK (statut IN ('actif', 'inactif')),
    updated_at         TIMESTAMP NOT NULL DEFAULT now()
);

-- ----------------------------------------------------------------------------
-- Commandes (en-tête)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS erp.commandes (
    commande_id        SERIAL PRIMARY KEY,
    numero_commande    VARCHAR(30) UNIQUE NOT NULL,
    client_code        VARCHAR(20) NOT NULL,      -- FK logique vers clients.csv (dim_client)
    magasin_id         VARCHAR(20) NOT NULL,      -- FK logique vers magasins.json (dim_magasin)
    commercial_id      INTEGER REFERENCES erp.commerciaux(commercial_id),
    canal_vente        VARCHAR(20) NOT NULL DEFAULT 'magasin' CHECK (canal_vente IN ('magasin', 'en_ligne', 'telephone')),
    date_commande       TIMESTAMP NOT NULL,
    statut_commande    VARCHAR(20) NOT NULL DEFAULT 'validee' CHECK (statut_commande IN ('validee', 'annulee', 'remboursee')),
    updated_at         TIMESTAMP NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_commandes_date ON erp.commandes(date_commande);
CREATE INDEX IF NOT EXISTS idx_commandes_client ON erp.commandes(client_code);
CREATE INDEX IF NOT EXISTS idx_commandes_magasin ON erp.commandes(magasin_id);

-- ----------------------------------------------------------------------------
-- Lignes de commande (détail produit)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS erp.lignes_commande (
    ligne_id           SERIAL PRIMARY KEY,
    commande_id        INTEGER NOT NULL REFERENCES erp.commandes(commande_id),
    produit_id         VARCHAR(20) NOT NULL,      -- FK logique vers produits.xlsx (dim_produit)
    quantite           INTEGER NOT NULL CHECK (quantite > 0),
    prix_unitaire_vente NUMERIC(12,2) NOT NULL CHECK (prix_unitaire_vente >= 0),
    taux_remise        NUMERIC(5,4) NOT NULL DEFAULT 0 CHECK (taux_remise BETWEEN 0 AND 1),
    updated_at         TIMESTAMP NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_lignes_commande_commande ON erp.lignes_commande(commande_id);
CREATE INDEX IF NOT EXISTS idx_lignes_commande_produit ON erp.lignes_commande(produit_id);

-- ----------------------------------------------------------------------------
-- Stocks (relevé quotidien par magasin / produit)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS erp.stocks (
    stock_id           SERIAL PRIMARY KEY,
    date_releve        DATE NOT NULL,
    magasin_id         VARCHAR(20) NOT NULL,
    produit_id         VARCHAR(20) NOT NULL,
    quantite_stock     INTEGER NOT NULL CHECK (quantite_stock >= 0),
    seuil_alerte       INTEGER NOT NULL DEFAULT 5,
    updated_at         TIMESTAMP NOT NULL DEFAULT now(),
    UNIQUE (date_releve, magasin_id, produit_id)
);

CREATE INDEX IF NOT EXISTS idx_stocks_date ON erp.stocks(date_releve);

COMMENT ON SCHEMA erp IS 'Système opérationnel (OLTP) simulant l''ERP/CRM de Nimba Distribution : source relationnelle du SID.';
