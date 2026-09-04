-- ============================================================================
-- Membres "inconnu" des dimensions (bonnes pratiques Kimball) : permettent de
-- rattacher un fait dont la clé de dimension est absente/invalide sans violer
-- les contraintes de clé étrangère (plutôt que de rejeter la ligne).
-- ============================================================================

INSERT INTO dwh.dim_client (client_id, nom, prenom, segment_client, ville, region, pays,
                             date_debut_validite, est_version_courante, hash_attributs)
SELECT 'INCONNU', 'Inconnu', 'Inconnu', 'Inconnu', 'Inconnu', 'Inconnu', 'Inconnu',
       '2023-01-01', TRUE, 'na'
WHERE NOT EXISTS (SELECT 1 FROM dwh.dim_client WHERE client_id = 'INCONNU');

INSERT INTO dwh.dim_produit (produit_id, nom_produit, categorie, sous_categorie, marque,
                              prix_unitaire, cout_unitaire, date_debut_validite, est_version_courante, hash_attributs)
SELECT 'INCONNU', 'Produit inconnu', 'Inconnu', 'Inconnu', 'Inconnu', 0, 0,
       '2023-01-01', TRUE, 'na'
WHERE NOT EXISTS (SELECT 1 FROM dwh.dim_produit WHERE produit_id = 'INCONNU');

INSERT INTO dwh.dim_magasin (magasin_id, nom_magasin, type_magasin, ville, region, pays)
SELECT 'INCONNU', 'Magasin inconnu', 'Inconnu', 'Inconnu', 'Inconnu', 'Inconnu'
WHERE NOT EXISTS (SELECT 1 FROM dwh.dim_magasin WHERE magasin_id = 'INCONNU');

INSERT INTO dwh.dim_commercial (commercial_id, matricule, nom, prenom, statut)
SELECT 'INCONNU', 'INCONNU', 'Inconnu', 'Inconnu', 'inactif'
WHERE NOT EXISTS (SELECT 1 FROM dwh.dim_commercial WHERE commercial_id = 'INCONNU');
