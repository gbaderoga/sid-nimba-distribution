#!/usr/bin/env python3
# ============================================================================
# NIMBA DISTRIBUTION - Générateur de données d'exemple
# ============================================================================
# Génère un jeu de données synthétique réaliste couvrant toutes les sources
# du SID :
#   - data/raw/csv/clients.csv                 (source CSV)
#   - data/raw/excel/produits.xlsx              (source Excel)
#   - data/raw/excel/objectifs.xlsx              (source Excel)
#   - data/raw/json/magasins.json                 (source JSON)
#   - base "erp_source" (Postgres) : commerciaux, commandes, lignes_commande,
#     stocks                                        (source base relationnelle)
#
# Usage :
#   python data/scripts/generate_sample_data.py [--seed 42] [--nb-clients 400]
#                                                [--nb-produits 250] [--annees 2]
# ============================================================================
import argparse
import json
import os
import random
import sys
import unicodedata
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd
from faker import Faker
from sqlalchemy import create_engine, text

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from etl.utils.db import get_erp_engine  # noqa: E402
from etl.utils.paths import RAW_CSV, RAW_EXCEL, RAW_JSON  # noqa: E402

fake = Faker("fr_FR")

# ----------------------------------------------------------------------------
# Référentiel géographique : Nimba Distribution opère uniquement en Guinée,
# avec un réseau de 8 magasins/agences répartis sur 6 villes.
# ----------------------------------------------------------------------------
GEOGRAPHIE = {
    "Guinée": {
        "Conakry":    (9.6412, -13.5784),
        "Kindia":     (10.0569, -12.8658),
        "Kankan":     (10.3853, -9.3057),
        "Nzérékoré":  (7.7566, -8.8179),
        "Boké":       (10.9401, -14.2960),
        "Labé":       (11.3182, -12.2831),
    },
}

CATEGORIES_PRODUITS = {
    "Électroménager": ["Réfrigérateurs", "Congélateurs", "Machines à laver", "Climatiseurs", "Cuisinières"],
    "Électronique":   ["Téléviseurs", "Téléphones", "Ordinateurs", "Tablettes", "Audio"],
    "Petit électroménager": ["Mixeurs", "Bouilloires", "Fers à repasser", "Ventilateurs"],
}

MARQUES = ["Samsung", "LG", "Hisense", "Nasco", "Bosch", "Philips", "TCL", "Sony", "Binatone", "Ramtons"]

SEGMENTS_CLIENT = ["Particulier", "Particulier", "Particulier", "Professionnel", "VIP"]

random.seed(42)
np.random.seed(42)


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def slugify_store_id(pays: str, ville: str, idx: int) -> str:
    return f"MAG-{_strip_accents(pays)[:2].upper()}-{_strip_accents(ville)[:3].upper()}-{idx:02d}"


def generate_magasins() -> pd.DataFrame:
    rows = []
    mid = 1
    for pays, villes in GEOGRAPHIE.items():
        for ville, (lat, lon) in villes.items():
            nb_magasins = 3 if ville == "Conakry" else 1
            for i in range(1, nb_magasins + 1):
                magasin_id = slugify_store_id(pays, ville, i)
                rows.append({
                    "magasin_id": magasin_id,
                    "nom_magasin": f"Nimba Distribution {ville} {i}",
                    "type_magasin": random.choice(["agence", "agence", "boutique"]),
                    "adresse": fake.street_address(),
                    "ville": ville,
                    "region": ville,  # simplification : la région = la ville principale
                    "pays": pays,
                    "latitude": round(lat + random.uniform(-0.02, 0.02), 6),
                    "longitude": round(lon + random.uniform(-0.02, 0.02), 6),
                    "date_ouverture": fake.date_between(start_date="-6y", end_date="-1y").isoformat(),
                })
                mid += 1
    return pd.DataFrame(rows)


def generate_produits(n: int) -> pd.DataFrame:
    rows = []
    for i in range(1, n + 1):
        categorie = random.choice(list(CATEGORIES_PRODUITS.keys()))
        sous_categorie = random.choice(CATEGORIES_PRODUITS[categorie])
        cout = round(random.uniform(15, 800), 2)
        marge_cible = random.uniform(0.15, 0.45)
        prix = round(cout * (1 + marge_cible), 2)
        rows.append({
            "produit_id": f"PRD-{i:05d}",
            "nom_produit": f"{sous_categorie[:-1] if sous_categorie.endswith('s') else sous_categorie} {random.choice(MARQUES)} {fake.word().capitalize()}",
            "categorie": categorie,
            "sous_categorie": sous_categorie,
            "marque": random.choice(MARQUES),
            "prix_unitaire": prix,
            "cout_unitaire": cout,
            "date_maj": fake.date_between(start_date="-2y", end_date="today").isoformat(),
        })
    return pd.DataFrame(rows)


def generate_clients(n: int) -> pd.DataFrame:
    rows = []
    for i in range(1, n + 1):
        pays = random.choice(list(GEOGRAPHIE.keys()))
        ville = random.choice(list(GEOGRAPHIE[pays].keys()))
        rows.append({
            "client_code": f"CLI-{i:06d}",
            "nom": fake.last_name(),
            "prenom": fake.first_name(),
            "email": fake.unique.email(),
            "telephone": fake.phone_number(),
            "date_inscription": fake.date_between(start_date="-5y", end_date="today").isoformat(),
            "segment": random.choice(SEGMENTS_CLIENT),
            "ville": ville,
            "region": ville,
            "pays": pays,
        })
    return pd.DataFrame(rows)


def generate_commerciaux(magasins: pd.DataFrame, n_per_store: int = 2) -> pd.DataFrame:
    rows = []
    i = 1
    for _, mag in magasins.iterrows():
        for _ in range(random.randint(1, n_per_store)):
            rows.append({
                "matricule": f"COM-{i:04d}",
                "nom": fake.last_name(),
                "prenom": fake.first_name(),
                "email": fake.unique.email(),
                "magasin_id": mag["magasin_id"],
                "date_embauche": fake.date_between(start_date="-5y", end_date="-3m").isoformat(),
                "statut": "actif" if random.random() > 0.05 else "inactif",
            })
            i += 1
    return pd.DataFrame(rows)


def generate_objectifs(commerciaux: pd.DataFrame, mois_liste: list) -> pd.DataFrame:
    rows = []
    for _, com in commerciaux.iterrows():
        if com["statut"] != "actif":
            continue
        for mois in mois_liste:
            base = random.uniform(22000, 42000)  # calibré pour être du même ordre de grandeur que le CA réalisé
            rows.append({
                "annee_mois": mois,
                "matricule_commercial": com["matricule"],
                "magasin_id": com["magasin_id"],
                "objectif_ca": round(base, 2),
                "objectif_quantite": random.randint(30, 150),
            })
    return pd.DataFrame(rows)


def generate_ventes(clients, produits, magasins, commerciaux, date_debut, date_fin, nb_lignes_cible):
    commerciaux_actifs = commerciaux[commerciaux["statut"] == "actif"].reset_index(drop=True)
    magasins_ids = magasins["magasin_id"].tolist()
    commerciaux_par_magasin = commerciaux_actifs.groupby("magasin_id")["matricule"].apply(list).to_dict()

    jours = (date_fin - date_debut).days
    # pondération saisonnière simple : décembre (fêtes) et juillet (rentrée) plus forts
    def poids_jour(d):
        w = 1.0
        if d.month == 12:
            w *= 1.6
        if d.month in (6, 7):
            w *= 1.25
        if d.weekday() >= 5:
            w *= 1.3
        return w

    commandes_rows = []
    lignes_rows = []
    commande_id = 1
    ligne_id = 1

    poids_jours = np.array([poids_jour(date_debut + timedelta(days=d)) for d in range(jours)])
    poids_jours = poids_jours / poids_jours.sum()
    nb_commandes = max(1, nb_lignes_cible // 2)  # ~2 lignes/commande en moyenne
    jours_tires = np.random.choice(np.arange(jours), size=nb_commandes, p=poids_jours)

    client_ids = clients["client_code"].tolist()
    produit_ids = produits["produit_id"].tolist()
    prix_par_produit = dict(zip(produits["produit_id"], produits["prix_unitaire"]))

    for jour_offset in jours_tires:
        d = date_debut + timedelta(days=int(jour_offset))
        magasin_id = random.choice(magasins_ids)
        equipe = commerciaux_par_magasin.get(magasin_id)
        commercial_matricule = random.choice(equipe) if equipe else None
        canal = random.choices(["magasin", "en_ligne", "telephone"], weights=[0.65, 0.25, 0.10])[0]
        numero_commande = f"CMD-{d.strftime('%Y%m%d')}-{commande_id:06d}"
        heure = timedelta(hours=random.randint(8, 19), minutes=random.randint(0, 59))
        commandes_rows.append({
            "commande_id": commande_id,
            "numero_commande": numero_commande,
            "client_code": random.choice(client_ids),
            "magasin_id": magasin_id,
            "commercial_id": commercial_matricule,
            "canal_vente": canal,
            "date_commande": (datetime.combine(d, datetime.min.time()) + heure).isoformat(),
            "statut_commande": random.choices(["validee", "annulee", "remboursee"], weights=[0.93, 0.04, 0.03])[0],
        })

        nb_produits_ligne = random.choices([1, 2, 3, 4], weights=[0.45, 0.30, 0.15, 0.10])[0]
        produits_choisis = random.sample(produit_ids, k=min(nb_produits_ligne, len(produit_ids)))
        for pid in produits_choisis:
            prix_catalogue = float(prix_par_produit[pid])
            remise = random.choices([0, 0.05, 0.10, 0.15], weights=[0.6, 0.2, 0.15, 0.05])[0]
            lignes_rows.append({
                "ligne_id": ligne_id,
                "commande_id": commande_id,
                "produit_id": pid,
                "quantite": random.choices([1, 2, 3], weights=[0.7, 0.22, 0.08])[0],
                "prix_unitaire_vente": round(prix_catalogue * random.uniform(0.97, 1.03), 2),
                "taux_remise": remise,
            })
            ligne_id += 1
        commande_id += 1

    return pd.DataFrame(commandes_rows), pd.DataFrame(lignes_rows)


def generate_stocks(magasins, produits, date_debut, date_fin):
    rows = []
    dates = pd.date_range(date_fin - timedelta(days=90), date_fin, freq="7D")  # relevés hebdo sur 90j pour rester léger
    for d in dates:
        for _, mag in magasins.iterrows():
            produits_echantillon = produits.sample(frac=0.6, random_state=abs(hash((mag["magasin_id"], str(d)))) % (2**31))
            for _, p in produits_echantillon.iterrows():
                qte = max(0, int(np.random.poisson(15)))
                rows.append({
                    "date_releve": d.date().isoformat(),
                    "magasin_id": mag["magasin_id"],
                    "produit_id": p["produit_id"],
                    "quantite_stock": qte,
                    "seuil_alerte": 5,
                })
    return pd.DataFrame(rows)




def load_erp_tables(commerciaux, commandes, lignes, stocks):
    engine = get_erp_engine()
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE erp.lignes_commande, erp.commandes, erp.stocks, erp.commerciaux RESTART IDENTITY CASCADE"))

    commerciaux.to_sql("commerciaux", engine, schema="erp", if_exists="append", index=False,
                        method="multi", chunksize=500)
    # commerciaux.commercial_id doit être remappé : on relit la table pour récupérer les ids générés
    with engine.begin() as conn:
        mapping = pd.read_sql("SELECT commercial_id, matricule FROM erp.commerciaux", conn)
    matricule_to_id = dict(zip(mapping["matricule"], mapping["commercial_id"]))

    commandes = commandes.copy()
    commandes["commercial_id"] = commandes["commercial_id"].map(matricule_to_id)
    commandes.drop(columns=["commande_id"]).to_sql(
        "commandes", engine, schema="erp", if_exists="append", index=False, method="multi", chunksize=1000
    )
    with engine.begin() as conn:
        mapping_cmd = pd.read_sql("SELECT commande_id, numero_commande FROM erp.commandes", conn)
    numero_to_id = dict(zip(mapping_cmd["numero_commande"], mapping_cmd["commande_id"]))

    lignes = lignes.copy()
    lignes["commande_id"] = lignes["commande_id"].map(
        dict(zip(commandes.index + 1, commandes["numero_commande"]))
    ).map(numero_to_id)
    # Le mapping ci-dessus suppose que l'index des commandes correspond à l'ordre d'insertion (commande_id d'origine).
    lignes.drop(columns=["ligne_id"]).to_sql(
        "lignes_commande", engine, schema="erp", if_exists="append", index=False, method="multi", chunksize=2000
    )

    stocks.to_sql("stocks", engine, schema="erp", if_exists="append", index=False, method="multi", chunksize=2000)

    return len(commerciaux), len(commandes), len(lignes), len(stocks)


def main():
    parser = argparse.ArgumentParser(description="Génère le jeu de données d'exemple de Nimba Distribution.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--nb-clients", type=int, default=400)
    parser.add_argument("--nb-produits", type=int, default=250)
    parser.add_argument("--annees", type=float, default=1.5, help="Nombre d'années d'historique de ventes")
    parser.add_argument("--nb-lignes-ventes", type=int, default=16000)
    args = parser.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)
    Faker.seed(args.seed)

    print(f"[1/7] Génération des magasins...")
    magasins = generate_magasins()

    print(f"[2/7] Génération de {args.nb_produits} produits...")
    produits = generate_produits(args.nb_produits)

    print(f"[3/7] Génération de {args.nb_clients} clients...")
    clients = generate_clients(args.nb_clients)

    print(f"[4/7] Génération des commerciaux...")
    commerciaux = generate_commerciaux(magasins)

    date_fin = date.today()
    date_debut = date_fin - timedelta(days=int(args.annees * 365))
    mois_liste = sorted({
        (date_debut + timedelta(days=d)).strftime("%Y-%m")
        for d in range(0, (date_fin - date_debut).days, 28)
    })

    print(f"[5/7] Génération des objectifs commerciaux ({len(mois_liste)} mois)...")
    objectifs = generate_objectifs(commerciaux, mois_liste)

    print(f"[6/7] Génération des ventes (~{args.nb_lignes_ventes} lignes) et des stocks...")
    commandes, lignes = generate_ventes(clients, produits, magasins, commerciaux, date_debut, date_fin, args.nb_lignes_ventes)
    stocks = generate_stocks(magasins, produits, date_debut, date_fin)

    print(f"[7/7] Écriture des fichiers sources et chargement de la base ERP...")

    os.makedirs(RAW_CSV, exist_ok=True)
    os.makedirs(RAW_EXCEL, exist_ok=True)
    os.makedirs(RAW_JSON, exist_ok=True)

    clients.to_csv(os.path.join(RAW_CSV, "clients.csv"), index=False, encoding="utf-8")

    with pd.ExcelWriter(os.path.join(RAW_EXCEL, "produits.xlsx"), engine="openpyxl") as writer:
        produits.to_excel(writer, sheet_name="Produits", index=False)
    with pd.ExcelWriter(os.path.join(RAW_EXCEL, "objectifs.xlsx"), engine="openpyxl") as writer:
        objectifs.to_excel(writer, sheet_name="Objectifs", index=False)

    magasins_json = json.loads(magasins.to_json(orient="records"))
    with open(os.path.join(RAW_JSON, "magasins.json"), "w", encoding="utf-8") as f:
        json.dump({"magasins": magasins_json}, f, ensure_ascii=False, indent=2)

    nb_com, nb_cmd, nb_lig, nb_stk = load_erp_tables(commerciaux, commandes, lignes, stocks)

    print("\n--- Résumé ---")
    print(f"  magasins            : {len(magasins)}")
    print(f"  produits (xlsx)     : {len(produits)}")
    print(f"  clients (csv)       : {len(clients)}")
    print(f"  commerciaux (erp)   : {nb_com}")
    print(f"  objectifs (xlsx)    : {len(objectifs)}")
    print(f"  commandes (erp)     : {nb_cmd}")
    print(f"  lignes commande (erp): {nb_lig}")
    print(f"  stocks (erp)        : {nb_stk}")
    print(f"  période ventes      : {date_debut} -> {date_fin}")
    print("\nDonnées générées avec succès.")


if __name__ == "__main__":
    main()
