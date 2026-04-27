# 🎌 AniData Lab — Observatoire Anime/Manga

> Pipeline de données complet : Data Refinement → Elasticsearch + Grafana → Airflow
> Semaine du 23 au 27 mars 2026

---

## 📋 Prérequis

- **Docker Desktop** installé et lancé ([docker.com/get-started](https://www.docker.com/get-started))
- **VS Code** avec les extensions Python et Jupyter ([code.visualstudio.com](https://code.visualstudio.com/))
- **Python 3.10+** installé en local (pour le Data Refinement)
- **8 Go de RAM minimum** (fermer les applications inutiles)
- **10 Go d'espace disque** disponible

### Extensions VS Code recommandées

```
code --install-extension ms-python.python
code --install-extension ms-toolsai.jupyter
```

### Vérification rapide

```bash
docker --version        # Docker 24+ recommandé
docker compose version  # Docker Compose v2+
python --version        # Python 3.10+
code --version          # VS Code
```

---

## 🚀 Installation (5 minutes)

### Étape 1 — Copier le projet

```bash
cd ~/Desktop
unzip anidata-lab.zip && cd anidata-lab
```

### Étape 2 — Installer les dépendances Python locales

```bash
pip install pandas numpy matplotlib seaborn elasticsearch
```

### Étape 3 — Télécharger les données

1. Aller sur **https://www.kaggle.com/datasets/hernan4444/anime-recommendation-database-2020**
2. Se connecter (compte Kaggle gratuit)
3. Cliquer **Download** et extraire dans le dossier `data/` :

```
data/
├── anime.csv                  (~3 MB)
├── rating_complete.csv        (~700 MB)
└── anime_with_synopsis.csv    (~5 MB)
```

### Étape 4 — Lancer l'environnement Docker

```bash
# Linux / Mac
chmod +x start.sh && ./start.sh

# Windows
start.bat

# Ou directement :
docker compose up -d
```

### Étape 5 — Vérifier que tout fonctionne

| Service           | URL                          | Identifiants         |
|-------------------|------------------------------|----------------------|
| **Grafana**       | http://localhost:3000        | admin / anidata      |
| **Airflow**       | http://localhost:8080        | admin / admin        |
| **Elasticsearch** | http://localhost:9200        | (API directe)        |

### Étape 6 — Ouvrir le projet dans VS Code

```bash
code .
```

Les fichiers Python et notebooks (.ipynb) s'ouvrent directement dans VS Code.

---

## 🏗️ Architecture du projet

```
anidata-lab/
│
├── docker-compose.yml              # Orchestration des services Docker
├── .env                            # Variables de configuration
├── start.sh / start.bat            # Scripts de démarrage
│
├── data/                           # 📦 Datasets CSV (à télécharger)
│   ├── LIRE_MOI.txt
│   ├── anime.csv
│   ├── rating_complete.csv
│   └── anime_with_synopsis.csv
│
├── airflow/
│   ├── dags/                       # 🔄 Vos DAGs Airflow
│   │   └── 00_hello_anidata.py
│   ├── scripts/                    # Scripts Python utilitaires
│   ├── plugins/
│   └── logs/
│
├── elk/
│   └── logstash/
│       └── pipeline/               # Config Logstash
│           └── anime.conf
│
├── grafana/
│   ├── provisioning/
│   │   ├── datasources/            # Elasticsearch auto-configuré
│   │   └── dashboards/             # Chargement auto des dashboards
│   └── dashboards/                 # 📊 Fichiers JSON des dashboards
│       └── anidata-overview.json   # Dashboard de démarrage
│
└── notebooks/                      # 📓 Vos notebooks (VS Code)
    └── (créez vos .ipynb ici)
```

---

## 🧮 Consommation mémoire (optimisée pour 8 Go)

| Service            | RAM allouée | Rôle                              |
|--------------------|-------------|-----------------------------------|
| Elasticsearch      | 1 Go        | Stockage et recherche             |
| Airflow Webserver  | 512 Mo      | Interface web                     |
| Airflow Scheduler  | 512 Mo      | Exécution des DAGs                |
| PostgreSQL         | 256 Mo      | Base de données Airflow           |
| **Grafana**        | **128 Mo**  | **Dashboards (4x moins que Kibana)** |
| Logstash           | 512 Mo      | **À la demande uniquement**       |
| **Total permanent**| **~2,4 Go** | **Reste ~5,6 Go pour l'OS + VS Code** |

---

## 📊 Utilisation au fil de la semaine

### Lundi / Mardi matin — Data Refinement (VS Code)

Ouvrir le projet dans VS Code et créer des notebooks dans `notebooks/` :

```python
import pandas as pd
anime = pd.read_csv("data/anime.csv")
anime.head()
```

### Mardi après-midi — Elasticsearch + Grafana

**Indexer via Logstash :**

```bash
docker compose --profile ingest up logstash
# Logstash lit anime.csv et l'indexe dans Elasticsearch
# Attendre la fin, puis Ctrl+C
```

**Indexer via Python (alternative) :**

```python
from elasticsearch import Elasticsearch
es = Elasticsearch("http://localhost:9200")
es.index(index="anime", id=1, document={"name": "Naruto", "score": 8.0})
```

Puis ouvrir **Grafana** http://localhost:3000 (admin / anidata).
Un dashboard de démarrage est déjà pré-configuré !

### Mercredi → Vendredi — Airflow

Ouvrir **Airflow** http://localhost:8080 (admin / admin).
Créer vos DAGs dans `airflow/dags/` — ils apparaissent automatiquement.

---

## ⚡ Commandes utiles

```bash
# Démarrer tout
docker compose up -d

# Arrêter tout (conserve les données)
docker compose down

# Arrêter et SUPPRIMER toutes les données
docker compose down -v

# Voir les logs d'un service
docker compose logs -f elasticsearch
docker compose logs -f grafana
docker compose logs -f airflow-webserver

# Redémarrer un service
docker compose restart grafana

# Vérifier l'état
docker compose ps

# Lancer Logstash ponctuellement pour indexer
docker compose --profile ingest up logstash

# Installer un package Python dans Airflow
docker compose exec airflow-webserver pip install <package>

# Shell dans un container
docker compose exec airflow-webserver bash
```

---

## 🐛 Dépannage

### Elasticsearch ne démarre pas (Linux)

```bash
sudo sysctl -w vm.max_map_count=262144
echo "vm.max_map_count=262144" | sudo tee -a /etc/sysctl.conf
```

### Airflow "Database not initialized"

```bash
docker compose down
docker compose up airflow-init
docker compose up -d
```

### Grafana ne montre pas de données

1. Vérifier qu'Elasticsearch a des données : `curl http://localhost:9200/anime/_count`
2. Dans Grafana → Configuration → Data Sources → tester la connexion
3. Relancer Logstash si besoin : `docker compose --profile ingest up logstash`

### Un port est déjà utilisé

```bash
lsof -i :3000   # ou 9200, 8080
```

### Réinitialisation complète

```bash
docker compose down -v
docker compose up -d
```

---

## 📚 Ressources

- [Dataset Kaggle](https://www.kaggle.com/datasets/hernan4444/anime-recommendation-database-2020)
- [Documentation Elasticsearch](https://www.elastic.co/guide/en/elasticsearch/reference/current/index.html)
- [Documentation Grafana](https://grafana.com/docs/grafana/latest/)
- [Documentation Airflow](https://airflow.apache.org/docs/apache-airflow/stable/)
- [Pandas Documentation](https://pandas.pydata.org/docs/)
