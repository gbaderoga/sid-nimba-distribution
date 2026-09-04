-- ============================================================================
-- NIMBA DISTRIBUTION - Vues de restitution (schéma mart)
-- ============================================================================
-- Ces vues encapsulent la logique métier des indicateurs demandés et servent
-- de datasets directement exploitables par Apache Superset. Elles s'appuient
-- exclusivement sur le schéma dwh (facts + dimensions courantes).
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS mart;

-- ----------------------------------------------------------------------------
-- v_ventes_detail : vue à plat (grain = ligne de vente), base de la plupart
-- des analyses. Ne garde que les commandes validées.
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW mart.v_ventes_detail AS
SELECT
    f.vente_sk,
    d.date_complete,
    d.annee,
    d.trimestre,
    d.mois,
    d.nom_mois,
    d.annee_mois,
    d.semaine_annee,
    d.est_weekend,
    cl.client_sk,
    cl.client_id,
    cl.nom || ' ' || cl.prenom            AS nom_client,
    cl.segment_client,
    cl.ville                                AS client_ville,
    cl.region                               AS client_region,
    cl.pays                                 AS client_pays,
    p.produit_sk,
    p.produit_id,
    p.nom_produit,
    p.categorie,
    p.sous_categorie,
    p.marque,
    m.magasin_sk,
    m.magasin_id,
    m.nom_magasin,
    m.type_magasin,
    m.ville                                 AS magasin_ville,
    m.region                                AS magasin_region,
    m.pays                                  AS magasin_pays,
    co.commercial_sk,
    co.commercial_id,
    co.nom || ' ' || co.prenom             AS nom_commercial,
    ca.libelle_canal,
    f.numero_commande,
    f.quantite,
    f.prix_unitaire_vente,
    f.taux_remise,
    f.montant_brut,
    f.montant_remise,
    f.montant_net,
    f.cout_total,
    f.marge
FROM dwh.fact_ventes f
JOIN dwh.dim_date d        ON d.date_id = f.date_id
JOIN dwh.dim_client cl     ON cl.client_sk = f.client_sk
JOIN dwh.dim_produit p     ON p.produit_sk = f.produit_sk
JOIN dwh.dim_magasin m     ON m.magasin_sk = f.magasin_sk
LEFT JOIN dwh.dim_commercial co ON co.commercial_sk = f.commercial_sk
JOIN dwh.dim_canal_vente ca ON ca.canal_sk = f.canal_sk
WHERE f.statut_commande = 'validee';

-- ----------------------------------------------------------------------------
-- v_ca_mensuel : chiffre d'affaires et évolution des ventes
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW mart.v_ca_mensuel AS
SELECT
    annee,
    mois,
    annee_mois,
    SUM(montant_net)                          AS chiffre_affaires,
    SUM(marge)                                AS marge_totale,
    SUM(quantite)                              AS quantite_vendue,
    COUNT(DISTINCT numero_commande)            AS nb_commandes,
    ROUND(SUM(montant_net) / NULLIF(COUNT(DISTINCT numero_commande), 0), 2) AS panier_moyen,
    -- évolution vs mois précédent (%)
    ROUND(
        100.0 * (SUM(montant_net) - LAG(SUM(montant_net)) OVER (ORDER BY annee_mois))
        / NULLIF(LAG(SUM(montant_net)) OVER (ORDER BY annee_mois), 0)
    , 2) AS evolution_pct_mois_precedent
FROM mart.v_ventes_detail
GROUP BY annee, mois, annee_mois
ORDER BY annee_mois;

-- ----------------------------------------------------------------------------
-- v_performance_produit : performance par produit / catégorie
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW mart.v_performance_produit AS
SELECT
    produit_id,
    nom_produit,
    categorie,
    sous_categorie,
    marque,
    SUM(montant_net)                    AS chiffre_affaires,
    SUM(marge)                          AS marge_totale,
    ROUND(100.0 * SUM(marge) / NULLIF(SUM(montant_net), 0), 2) AS taux_marge_pct,
    SUM(quantite)                        AS quantite_vendue,
    COUNT(DISTINCT numero_commande)      AS nb_commandes,
    RANK() OVER (ORDER BY SUM(montant_net) DESC) AS rang_ca
FROM mart.v_ventes_detail
GROUP BY produit_id, nom_produit, categorie, sous_categorie, marque;

-- ----------------------------------------------------------------------------
-- v_performance_zone : performance par zone géographique (magasin/région/pays)
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW mart.v_performance_zone AS
SELECT
    magasin_pays                          AS pays,
    magasin_region                        AS region,
    magasin_ville                         AS ville,
    magasin_id,
    nom_magasin,
    type_magasin,
    SUM(montant_net)                       AS chiffre_affaires,
    SUM(marge)                             AS marge_totale,
    SUM(quantite)                          AS quantite_vendue,
    COUNT(DISTINCT numero_commande)        AS nb_commandes,
    COUNT(DISTINCT client_id)              AS nb_clients_distincts
FROM mart.v_ventes_detail
GROUP BY magasin_pays, magasin_region, magasin_ville, magasin_id, nom_magasin, type_magasin;

-- ----------------------------------------------------------------------------
-- v_performance_commerciale : performance des commerciaux + atteinte objectifs
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW mart.v_performance_commerciale AS
SELECT
    v.commercial_id,
    v.nom_commercial,
    v.annee_mois,
    SUM(v.montant_net)                       AS ca_realise,
    SUM(v.quantite)                          AS quantite_realisee,
    COUNT(DISTINCT v.numero_commande)        AS nb_commandes,
    MAX(o.objectif_ca)                        AS objectif_ca,
    MAX(o.objectif_quantite)                  AS objectif_quantite,
    ROUND(100.0 * SUM(v.montant_net) / NULLIF(MAX(o.objectif_ca), 0), 2)       AS taux_atteinte_ca_pct,
    ROUND(100.0 * SUM(v.quantite) / NULLIF(MAX(o.objectif_quantite), 0), 2)    AS taux_atteinte_quantite_pct
FROM mart.v_ventes_detail v
LEFT JOIN dwh.fact_objectifs o
    ON o.commercial_sk = v.commercial_sk
   AND o.date_id = (v.annee * 10000 + v.mois * 100 + 1)
GROUP BY v.commercial_id, v.nom_commercial, v.annee_mois;

-- ----------------------------------------------------------------------------
-- v_atteinte_objectifs : synthèse mensuelle globale objectifs vs réalisé
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW mart.v_atteinte_objectifs AS
SELECT
    d.annee_mois,
    m.magasin_id,
    m.nom_magasin,
    m.region,
    SUM(o.objectif_ca)                          AS objectif_ca,
    COALESCE(SUM(v.ca_reel), 0)                  AS ca_realise,
    ROUND(100.0 * COALESCE(SUM(v.ca_reel), 0) / NULLIF(SUM(o.objectif_ca), 0), 2) AS taux_atteinte_pct
FROM dwh.fact_objectifs o
JOIN dwh.dim_date d      ON d.date_id = o.date_id
JOIN dwh.dim_magasin m   ON m.magasin_sk = o.magasin_sk
LEFT JOIN (
    SELECT commercial_sk, annee, mois, SUM(montant_net) AS ca_reel
    FROM mart.v_ventes_detail
    GROUP BY commercial_sk, annee, mois
) v ON v.commercial_sk = o.commercial_sk AND v.annee = d.annee AND v.mois = d.mois
GROUP BY d.annee_mois, m.magasin_id, m.nom_magasin, m.region;

-- ----------------------------------------------------------------------------
-- v_comportement_client : analyse RFM (Récence, Fréquence, Montant)
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW mart.v_comportement_client AS
WITH agg AS (
    SELECT
        client_id,
        nom_client,
        segment_client,
        client_region,
        client_pays,
        MAX(date_complete)                        AS derniere_commande,
        (SELECT MAX(date_complete) FROM mart.v_ventes_detail) - MAX(date_complete) AS recence_jours,
        COUNT(DISTINCT numero_commande)             AS frequence_commandes,
        SUM(montant_net)                            AS montant_total,
        ROUND(AVG(montant_net), 2)                  AS panier_moyen
    FROM mart.v_ventes_detail
    GROUP BY client_id, nom_client, segment_client, client_region, client_pays
)
SELECT
    *,
    NTILE(5) OVER (ORDER BY recence_jours DESC)      AS score_r,   -- 5 = récent
    NTILE(5) OVER (ORDER BY frequence_commandes ASC)  AS score_f,   -- 5 = fréquent
    NTILE(5) OVER (ORDER BY montant_total ASC)        AS score_m,   -- 5 = gros montant
    CASE
        WHEN NTILE(5) OVER (ORDER BY montant_total ASC) >= 4
         AND NTILE(5) OVER (ORDER BY frequence_commandes ASC) >= 4 THEN 'Client fidèle / à forte valeur'
        WHEN NTILE(5) OVER (ORDER BY recence_jours DESC) <= 2 THEN 'Client à risque de désengagement'
        WHEN NTILE(5) OVER (ORDER BY frequence_commandes ASC) <= 2 THEN 'Client occasionnel'
        ELSE 'Client régulier'
    END AS segment_comportemental
FROM agg;

-- ----------------------------------------------------------------------------
-- v_situation_stock : niveau de stock et ruptures
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW mart.v_situation_stock AS
SELECT
    d.date_complete,
    m.magasin_id,
    m.nom_magasin,
    m.region,
    p.produit_id,
    p.nom_produit,
    p.categorie,
    s.quantite_stock,
    s.seuil_alerte,
    s.valeur_stock,
    s.en_rupture
FROM dwh.fact_stock s
JOIN dwh.dim_date d     ON d.date_id = s.date_id
JOIN dwh.dim_magasin m  ON m.magasin_sk = s.magasin_sk
JOIN dwh.dim_produit p  ON p.produit_sk = s.produit_sk;

COMMENT ON SCHEMA mart IS 'Vues de restitution consommées par Superset - une vue par famille d''indicateur.';
