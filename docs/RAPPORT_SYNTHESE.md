# Rapport de synthèse - Système d'Information Décisionnel Nimba Distribution

## 1. Contexte retenu

Nimba Distribution est une entreprise fictive spécialisée dans la distribution d'électroménager et de
produits électroniques en Guinée. Elle dispose d'un réseau de 8 magasins et agences répartis dans
plusieurs villes du pays, notamment Conakry, Kindia, Kankan, Nzérékoré, Boké et Labé.

L'entreprise commercialise plusieurs centaines de références à travers différents canaux de vente : en
magasin, en ligne et par téléphone. Elle s'appuie également sur une force de vente composée de commerciaux
rattachés à différents magasins et suivis à travers des objectifs commerciaux mensuels.

Le développement de l'activité et la multiplicité des points de vente génèrent des données provenant de
plusieurs domaines : ventes, clients, produits, magasins, commerciaux, commandes, stocks et objectifs
commerciaux. Leur centralisation dans un Système d'Information Décisionnel (SID) permet de disposer d'une
vision consolidée de l'activité et de faciliter l'analyse des performances.

Ce contexte se prête ainsi particulièrement bien à la mise en place d'un entrepôt de données (Data
Warehouse) permettant notamment d'analyser le chiffre d'affaires, les quantités vendues, les performances
des magasins et des commerciaux, l'évolution des ventes dans le temps ainsi que l'atteinte des objectifs
commerciaux.

La présence de plusieurs magasins répartis dans différentes villes de Guinée permet également d'intégrer
une véritable dimension géographique dans les analyses et de comparer les performances entre zones.

Ce contexte constitue une proposition originale, inspirée du fonctionnement d'une entreprise de
distribution multi-sites, mais entièrement fictive. Il respecte ainsi le principe du sujet tout en
fournissant un cadre réaliste pour la conception et la mise en œuvre d'un système décisionnel complet.

## 2. Sources de données et formats

Le SID s'alimente à partir de quatre sources hétérogènes, représentatives de la réalité d'un système d'information d'entreprise où les données ne proviennent jamais d'un unique référentiel :

| Source | Format | Contenu | Justification du choix de format |
|---|---|---|---|
| `clients.csv` | CSV | Référentiel clients (export CRM) | Le CSV est le format d'échange le plus courant pour un export périodique d'un outil tiers (CRM, par exemple) |
| `produits.xlsx` | Excel | Catalogue produits (prix, coût, catégorie) | Le catalogue est en pratique souvent maintenu à la main par l'équipe merchandising dans un classeur Excel |
| `objectifs.xlsx` | Excel | Objectifs commerciaux mensuels par commercial | Document de pilotage RH/direction commerciale, typiquement un tableur |
| `magasins.json` | JSON | Référentiel des magasins/agences (géolocalisation) | Format naturel pour un export d'une application de gestion de sites (API interne, outil de facilities management) |
| Base **erp_source** (PostgreSQL) | Base relationnelle | Commerciaux, commandes, lignes de commande, stocks | Représente le système transactionnel (ERP/CRM) de l'entreprise, où sont enregistrées les opérations du quotidien |

Cette diversité (fichiers plats, tableur, JSON, base OLTP) est délibérée : elle oblige le pipeline ETL à mettre en œuvre des connecteurs différenciés et une zone de staging homogénéisante, comme dans un SID réel.

## 3. Choix techniques et justifications

### 3.1 PostgreSQL comme SGBD / Data Warehouse

PostgreSQL a été retenu pour l'ensemble des besoins de stockage : base opérationnelle source (`erp_source`), Data Warehouse (`dwh`, avec les schémas `staging`, `dwh` et `mart`), métadonnées Airflow et métadonnées Superset. Un seul moteur (mais des bases distinctes) simplifie le déploiement Docker tout en respectant la séparation logique attendue (une vraie base OLTP source, séparée du DWH). PostgreSQL est open-source, dispose de fonctions analytiques avancées (fenêtrage, `NTILE`, etc. utilisées dans les vues de restitution) et s'intègre nativement à Superset et Airflow.

### 3.2 Modèle en étoile (schéma de Kimball)

Le choix d'un modèle en étoile classique (tables de faits + dimensions) plutôt qu'un modèle en flocon ou une architecture Data Vault se justifie par la taille modérée du référentiel et l'objectif premier de restitution décisionnelle rapide dans Superset : un schéma en étoile minimise les jointures nécessaires aux requêtes analytiques et est directement lisible par un outil de BI en self-service.

Trois grains ont été identifiés (détaillés dans `docs/MODELE_DIMENSIONNEL.md`) :
- **fact_ventes** : une ligne de commande (le grain le plus fin disponible dans la source, permettant tous les regroupements ultérieurs) ;
- **fact_stock** : un relevé quotidien de stock par magasin et par produit ;
- **fact_objectifs** : un objectif mensuel par commercial.

### 3.3 Gestion des dimensions à évolution lente (SCD)

Plutôt que d'adopter une stratégie unique et simpliste (écrasement systématique), le projet met en œuvre deux techniques SCD différentes pour illustrer leur usage approprié :
- **SCD Type 2** (historisation complète, avec `date_debut_validite`/`date_fin_validite`/`est_version_courante`) pour `dim_client` et `dim_produit`, dont les attributs (segment client, ville, prix, catégorie...) évoluent dans le temps et dont l'historique a un intérêt analytique direct (ex. : mesurer un CA au prix en vigueur à la date de vente) ;
- **SCD Type 1** (écrasement) pour `dim_magasin` et `dim_commercial`, dont les changements d'attributs sont rares et sans enjeu d'historisation pour ce périmètre.

Cette logique est implémentée génériquement dans `etl/load/scd_utils.py` (calcul d'empreinte SHA-256 des attributs suivis pour détecter un changement) et a été testée en conditions réelles (voir §5).

### 3.4 ETL en Python/pandas plutôt qu'un outil ETL graphique

Le choix d'un pipeline codé en Python (pandas + SQLAlchemy) plutôt qu'un outil ETL graphique (Talend, etc.) répond à la contrainte du sujet, mais présente aussi des avantages réels : versionnable avec Git au même titre que le reste du projet, testable unitairement, sans dépendance à une licence ou à une plateforme propriétaire, et suffisamment flexible pour gérer les quatre formats de source hétérogènes du projet dans un cadre de code unique et cohérent.

Le pipeline suit une architecture **ELT-friendly en 4 étapes** systématiques : extraction brute vers une zone de **staging** (aucune transformation), puis chargement des **dimensions**, puis chargement des **faits** (qui résolvent les clés de substitution via les dimensions déjà chargées), puis **contrôles qualité**. Chaque étape est idempotente (rejouable sans dupliquer les données), ce qui a été vérifié expérimentalement.

### 3.5 Apache Airflow pour l'orchestration

Airflow orchestre le pipeline quotidien (`etl/dags/dag_sid_nimba_distribution.py`) en respectant les dépendances métier réelles : les 7 extractions sont indépendantes et parallélisables, les 4 chargements de dimensions le sont également, mais doivent impérativement précéder les chargements de faits (qui ont besoin des clés de substitution), eux-mêmes suivis des contrôles qualité. Cette structure est exprimée avec `cross_downstream` (dépendances many-to-many entre étapes), plus fidèle à la réalité du pipeline qu'un simple enchaînement linéaire.

### 3.6 Apache Superset pour la restitution

Superset a été choisi pour sa gratuité, son intégration native à PostgreSQL, et sa capacité à être piloté par API (utilisée ici pour provisionner automatiquement les datasets, graphiques et le tableau de bord — voir `dashboard/provision_dashboard.py` — plutôt que de documenter une suite de clics dans une interface). Une couche de vues SQL dédiées (schéma `mart`) a été intercalée entre le modèle en étoile et Superset : elle encapsule la logique métier de chaque indicateur (calcul de marge, segmentation RFM, taux d'atteinte des objectifs...) une seule fois, en SQL, plutôt que de la dupliquer dans chaque graphique.

### 3.7 Docker Compose et GitHub

L'ensemble de la stack (PostgreSQL, Airflow, Superset) est conteneurisé via Docker Compose, avec des images officielles étendues au strict nécessaire (dépendances Python additionnelles pour Airflow, configuration applicative pour Superset). Cela garantit la reproductibilité du déploiement sur n'importe quelle machine disposant de Docker, indépendamment de l'environnement de développement. Git/GitHub assure le versionnement et la traçabilité des choix (historique de commits par grande étape du projet).

## 4. Indicateurs couverts

| Indicateur demandé | Implémentation |
|---|---|
| Chiffre d'affaires | `mart.v_ca_mensuel.chiffre_affaires`, KPI Superset |
| Évolution des ventes | `mart.v_ca_mensuel.evolution_pct_mois_precedent` + courbe temporelle Superset |
| Performance par produit | `mart.v_performance_produit` (CA, marge, rang) |
| Performance par zone géographique | `mart.v_performance_zone` (magasin, ville) |
| Performance commerciale | `mart.v_performance_commerciale` et `mart.v_atteinte_objectifs` |
| Comportement client | `mart.v_comportement_client` (segmentation RFM : Récence/Fréquence/Montant) |
| Atteinte des objectifs | `mart.v_atteinte_objectifs` (objectif vs réalisé, taux d'atteinte) |
| *(Bonus)* Situation des stocks | `mart.v_situation_stock` (ruptures, valorisation) |

## 5. Tests et validation effectués

Contrainte technique propre à l'environnement de développement utilisé pour ce projet : l'accès aux registres d'images Docker (Docker Hub, ghcr.io, etc.) était bloqué par la politique réseau du bac à sable dans lequel ce projet a été construit, empêchant l'exécution de `docker compose up` à cet endroit précis. Pour autant, **l'intégralité de la logique applicative a été testée en conditions réelles**, avec les mêmes versions logicielles que celles utilisées par les images Docker du projet :

- **PostgreSQL** installé nativement et utilisé pour dérouler les scripts SQL (`sql/`), générer un jeu de données (8 magasins, 8 000 commandes, ~15 100 lignes de vente, 15 600 relevés de stock) et exécuter le pipeline ETL complet de bout en bout, y compris un test explicite de la mécanique SCD2 (modification d'un client, vérification de la double version en base) ;
- **Apache Airflow 2.10.4** installé via pip et utilisé pour valider le parsing du DAG (`airflow dags list-import-errors`) puis pour l'**exécuter réellement** (`airflow dags test`), les 15 tâches se terminant toutes en succès dans le bon ordre de dépendance ;
- **Apache Superset 4.1.1** installé via pip, connecté à la base `dwh` locale ; le script `dashboard/provision_dashboard.py` a été exécuté contre une instance Superset réelle, créant effectivement la connexion, les 7 datasets, les 10 graphiques et le tableau de bord, avec **capture d'écran du rendu final** (`docs/img/dashboard_superset.png`) confirmant que chaque graphique restitue des données cohérentes.

Le `docker-compose.yml` et les `Dockerfile` associés ont été validés structurellement (`docker compose config`) et suivent les pratiques officielles (image Airflow étendue via fichier de contraintes officiel, image Superset étendue par une configuration applicative standard). Leur exécution complète nécessite simplement un environnement disposant d'un accès normal aux registres Docker.

## 6. Limites et pistes d'amélioration

Le système développé répond aux objectifs du projet, mais certaines améliorations pourraient être
envisagées pour renforcer sa robustesse et préparer son utilisation à plus grande échelle.

-Premièrement, la gestion de l'historique des dimensions avec le mécanisme SCD Type 2 repose actuellement
sur la détection des modifications de l'ensemble des attributs suivis. Une amélioration consisterait à
limiter cette détection aux attributs réellement importants à historiser, afin d'éviter la création de
versions inutiles.

-Deuxièmement, le jeu de données utilisé reste relativement limité, avec environ 15 100 lignes de ventes.
Des tests sur des volumes beaucoup plus importants permettraient de mieux évaluer les performances et la
capacité de montée en charge du système. Néanmoins, l'utilisation de tables de staging, d'index et de vues
constitue une base adaptée à l'évolution du volume des données.

-Enfin, l'environnement Docker Compose actuel est principalement adapté au développement et à la
démonstration. Un passage en production nécessiterait notamment de renforcer la sécurité des accès avec
HTTPS, d'automatiser les sauvegardes de PostgreSQL et, si la charge de traitement augmente, de faire
évoluer Airflow vers une architecture distribuée capable d'exécuter les traitements sur plusieurs workers.