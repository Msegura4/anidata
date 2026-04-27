# AniData Scraper

Scraper du mock-site AniDex pour le projet **AniData Lab — Semaine 2 DevOps & CI/CD**.

Extrait les données anime et les actualités depuis le mock-site HTML local
(cf. dépôt `mock-site`), les enrichit, et produit un JSON consommable par le
DAG ETL Airflow.

---

## Installation

```bash
# Création d'un environnement virtuel (recommandé)
python3 -m venv .venv
source .venv/bin/activate   # Linux/Mac
# .venv\Scripts\activate    # Windows

# Dépendances runtime
pip install -r requirements.txt

# OU dépendances dev (runtime + tests + lint)
pip install -r requirements-dev.txt
```

---

## Usage

### En ligne de commande

```bash
# Scraping complet vers ./data/raw/
python -m anidata_scraper.scraper --base-url http://localhost:8088 --output-dir ./data/raw

# Scraping rapide (sans enrichissement via pages détail)
python -m anidata_scraper.scraper --no-enrich

# Mode verbeux (DEBUG)
python -m anidata_scraper.scraper -v
```

Le scraper produit un fichier `anime_YYYYMMDD_HHMMSS.json` dans le répertoire
de sortie (créé s'il n'existe pas).

### Depuis un DAG Airflow

```python
from datetime import datetime
from airflow import DAG
from airflow.operators.python import PythonOperator

from anidata_scraper import scrape_to_file

with DAG(
    "scraper_dag",
    schedule="@daily",
    start_date=datetime(2026, 4, 27),
    catchup=False,
) as dag:

    scrape_task = PythonOperator(
        task_id="scrape_anidex",
        python_callable=scrape_to_file,
        op_kwargs={
            "output_dir": "/opt/airflow/data/raw",
            "base_url": "http://mock-site",  # nom du service Docker
        },
    )
```

La fonction `scrape_to_file` renvoie le chemin du fichier produit, qui est
automatiquement poussé dans XCom et peut être consommé par le DAG ETL en aval.

---

## Structure du projet

```
anidata-scraper/
├── anidata_scraper/
│   ├── __init__.py
│   └── scraper.py          # Module principal
├── tests/
│   ├── __init__.py
│   ├── fixtures.py         # Fragments HTML pour les tests
│   └── test_scraper.py     # Tests pytest
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml          # Config pytest, ruff
├── .gitignore
└── README.md
```

---

## Tests & qualité

```bash
# Tests unitaires
pytest

# Avec couverture
pytest --cov=anidata_scraper --cov-report=term-missing

# Lint
ruff check anidata_scraper/ tests/

# Formatage auto
ruff format anidata_scraper/ tests/
```

Les tests sont conçus pour tourner **sans le mock-site actif** : ils utilisent
des fragments HTML embarqués (`tests/fixtures.py`) et mockent les appels HTTP
via `monkeypatch`. Ils sont donc parfaitement adaptés à l'exécution en CI.

---

## Structure du JSON produit

```json
{
  "scraped_at": "2026-04-27T09:15:23+00:00",
  "source": "http://mock-site",
  "stats": {
    "animes_count": 103,
    "news_count": 8,
    "missing_scores": 4,
    "missing_studios": 3
  },
  "animes": [
    {
      "id": 1,
      "title_en": "Attack on Titan",
      "title_jp": "進撃の巨人",
      "detail_url": "/anime/attack-on-titan.html",
      "year": 2013,
      "studio": "Wit Studio",
      "score": 9.0,
      "genres": ["Action", "Drama", "Fantasy"],
      "type": "TV",
      "episodes": 25,
      "status": "Finished Airing",
      "synopsis": "Dans un monde où l'humanité..."
    }
  ],
  "news": [
    {
      "title": "Les animes les plus attendus du printemps 2026",
      "url": "/news/printemps-2026.html",
      "category": "Saisonnier",
      "published_at": "2026-04-01",
      "body": null
    }
  ]
}
```

---

## Fonctionnalités

- **Scraping paginé** : détecte dynamiquement le nombre de pages du catalogue
- **Enrichissement** : parcourt les pages détail pour récupérer synopsis,
  épisodes, type, statut
- **Robustesse** :
  - Retry exponentiel sur erreurs réseau et 5xx
  - Pas de retry sur 4xx (erreurs client)
  - Gestion défensive des valeurs manquantes (score "N/A", studio vide)
  - Support des deux structures HTML présentes sur le site (`<table>` ET `<dl>`)
- **Observabilité** : logging structuré, stats de qualité dans la sortie

---

## Intégration avec le pipeline ETL

Le fichier JSON produit est déposé dans un volume Docker partagé avec le
service Airflow (`/opt/airflow/data/raw/`). Le DAG `etl_dag` (démarré par
`TriggerDagRunOperator` depuis le DAG scraper) lit ce fichier, transforme
les données et les indexe dans l'index Elasticsearch existant
(`anidex_animes`), enrichissant ainsi la base constituée en semaine 1.
