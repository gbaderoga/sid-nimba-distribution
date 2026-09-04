"""Configuration Superset - Nimba Distribution.

La majorité des réglages restent par défaut ; on ne surcharge que le
nécessaire (base de métadonnées, clé secrète, quelques options d'ergonomie).
"""
import os

POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB_SUPERSET = os.getenv("POSTGRES_DB_SUPERSET", "superset")

SQLALCHEMY_DATABASE_URI = (
    f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
    f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB_SUPERSET}"
)

SECRET_KEY = os.getenv("SUPERSET_SECRET_KEY", "change_moi_en_production")

FEATURE_FLAGS = {
    "DASHBOARD_NATIVE_FILTERS": True,
    "DASHBOARD_CROSS_FILTERS": True,
    "ENABLE_TEMPLATE_PROCESSING": True,
}

# Cache léger en mémoire, suffisant pour une démo (remplacer par Redis en prod)
CACHE_CONFIG = {"CACHE_TYPE": "SimpleCache", "CACHE_DEFAULT_TIMEOUT": 300}
DATA_CACHE_CONFIG = CACHE_CONFIG

LANGUAGES = {
    "fr": {"flag": "fr", "name": "Français"},
    "en": {"flag": "us", "name": "English"},
}
BABEL_DEFAULT_LOCALE = "fr"

# Locale de formatage numérique (D3) utilisée par tous les graphiques :
# séparateur de milliers = espace et décimale = virgule (convention
# française), et affixe de devise = "GNF" en suffixe. Un format de métrique
# comme "$,.0f" (le "$" signifie ici "utiliser l'affixe de devise de la
# locale", pas un dollar littéral) rend alors "20 984 000 GNF".
# Réf. : https://github.com/d3/d3-format/blob/main/README.md#formatLocale
D3_FORMAT = {
    "decimal": ",",
    "thousands": " ",
    "grouping": [3],
    "currency": ["", " GNF"],
}
