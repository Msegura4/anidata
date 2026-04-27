# =============================================================================
# Image Docker custom AniData Airflow
# =============================================================================
# Étend l'image officielle Apache Airflow 2.x avec :
# - le code du scraper (package anidata_scraper)
# - les DAGs (scraper_dag, etl_dag)
# - les dépendances Python supplémentaires
#
# Cette image est buildée et publiée automatiquement par .github/workflows/ci-cd.yml
# sur GitHub Container Registry (GHCR) à chaque merge sur main.
#
# Le docker-compose.yml d'Airflow (semaine 1, étendu en semaine 2) pointe vers
# cette image via la variable AIRFLOW_IMAGE_NAME.
# =============================================================================

# Image de base officielle, version pinnée pour la reproductibilité
FROM apache/airflow:2.10.4-python3.10

# Métadonnées (visibles sur GHCR)
LABEL org.opencontainers.image.title="AniData Airflow"
LABEL org.opencontainers.image.description="Airflow custom pour AniData Lab — scraper + DAGs"
LABEL org.opencontainers.image.source="https://github.com/sakura-analytics/anidata-scraper"
LABEL org.opencontainers.image.licenses="MIT"

# On reste en utilisateur airflow pour la sécurité (jamais en root pour pip)
USER airflow

# --- Dépendances Python --------------------------------------------------------
# On copie d'abord uniquement les requirements pour profiter du cache Docker :
# tant que requirements.txt n'a pas changé, cette couche n'est pas reconstruite.
COPY --chown=airflow:root requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# --- Code du scraper -----------------------------------------------------------
# Le package est installé en mode "editable" pour qu'il soit importable
# depuis n'importe quel DAG via `from anidata_scraper import scrape_to_file`.
COPY --chown=airflow:root pyproject.toml /opt/airflow/scraper/pyproject.toml
COPY --chown=airflow:root anidata_scraper/ /opt/airflow/scraper/anidata_scraper/
RUN pip install --no-cache-dir /opt/airflow/scraper/

# --- DAGs ---------------------------------------------------------------------
# Les DAGs sont copiés dans le dossier que Airflow scanne par défaut.
COPY --chown=airflow:root dags/ /opt/airflow/dags/

# --- Dossier de données --------------------------------------------------------
# Création du dossier raw où le scraper écrit ses fichiers JSON.
# Ce dossier sera monté en volume dans docker-compose pour persistance.
RUN mkdir -p /opt/airflow/data/raw

# Vérification rapide à la fin du build : le package s'importe correctement
RUN python -c "import anidata_scraper; print(f'AniData Scraper {anidata_scraper.__version__} OK')"
