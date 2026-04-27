# AniDex — Mock-site pour AniData Lab (semaine DevOps & CI/CD)

Site HTML statique simulant une encyclopédie d'anime type MyAnimeList, destiné
à servir de cible de scraping dans le cadre du cours **AniData Lab — semaine 2
DevOps & CI/CD**.

Totalement local, légal, stable, offline-compatible.

---

## Contenu

- **103 fiches anime** (titre FR, titre JP, année, studio, type, épisodes,
  statut, genres, score, synopsis)
- **4 pages de catalogue paginées** (30 animes par page)
- **8 articles d'actualité** saisonnière (pour illustrer l'aspect
  "nouveautés à indexer" du pipeline)
- **Page d'accueil** avec top notés + sorties récentes
- Pièges pédagogiques volontairement injectés : scores manquants (`N/A`),
  studios non renseignés, variations de structure HTML sur ~10% des pages
  (pour tester la robustesse du scraper)

## Structure du projet

```
mock-site/
├── docker-compose.yml        # Service nginx standalone
├── README.md                 # Ce fichier
├── generator/
│   ├── generate_site.py      # Générateur principal
│   └── seed_data.py          # Données source (animes + news)
└── site/                     # Site HTML généré (118 pages)
    ├── index.html
    ├── about.html
    ├── robots.txt
    ├── assets/style.css
    ├── animes/page-{1..4}.html
    ├── anime/<slug>.html      # 103 fiches détail
    └── news/
        ├── index.html
        └── <slug>.html        # 8 articles
```

---

## Démarrage rapide (standalone)

Pour tester le site seul, sans l'environnement Airflow complet :

```bash
cd mock-site/
docker compose up -d
```

Le site est accessible sur : **http://localhost:8088**

Pour l'arrêter :
```bash
docker compose down
```

---

## Intégration au projet AniData Lab

En conditions réelles de cours, le mock-site doit être dans le même réseau
Docker que Airflow pour que le DAG scraper puisse l'atteindre par son nom
de service.

### Option 1 — Ajouter le service au docker-compose Airflow existant

Dans le `docker-compose.yml` d'Airflow (celui de la semaine 1, étendu pour la
semaine 2), ajouter ce bloc au niveau `services:` :

```yaml
  mock-site:
    image: nginx:alpine
    container_name: anidata-mock-site
    volumes:
      - ./mock-site/site:/usr/share/nginx/html:ro
    restart: unless-stopped
    networks:
      - default  # ou le réseau commun utilisé par Airflow
```

Depuis un DAG, le site est alors accessible sur :
```
http://mock-site/
```
(port 80 par défaut — pas besoin de préciser le port depuis le réseau Docker)

### Option 2 — Réseau partagé inter-compose

Les deux `docker-compose.yml` (mock-site et Airflow) rejoignent un réseau
nommé `anidata-network` défini en `external: true`. Voir la section dédiée du
syllabus semaine 2 si nécessaire.

---

## Régénération du site

Le site dans `site/` est **déjà généré**. Pour le reconstruire (utile si on
veut modifier le contenu) :

```bash
cd generator/
python3 generate_site.py
```

Aucune dépendance externe requise (stdlib uniquement). Le dossier `site/`
est entièrement réécrit à chaque exécution.

### Modification du contenu

Tout passe par `generator/seed_data.py` :

- Liste `ANIMES` : tuples avec toutes les métadonnées
- Dict `ANOMALIES` : pièges injectés (index → type d'anomalie)
- Liste `NEWS` : actualités saisonnières

Types d'anomalies supportées :
- `{"score_na": True}` → score affiché "N/A" au lieu d'une note
- `{"studio_empty": True}` → champ studio vide

Pour ajouter un piège supplémentaire, il suffit de modifier `generate_site.py`
(fonctions `render_anime_card` et `generate_anime_detail`).

---

## Éléments pédagogiques ciblés

Ce mock-site permet de travailler les points suivants en cours :

### 1. Scraping de base avec BeautifulSoup

- Sélecteurs CSS (`.anime-card`, `.score`, `.genre-tag`)
- Attributs `data-*` (`data-anime-id`, `data-year`, `data-score`)
- Extraction texte vs attributs

### 2. Pagination

- Détection du lien "Suivant" via `.pagination .next`
- Bouclage sur toutes les pages du catalogue
- Extraction du nombre total de pages depuis le titre

### 3. Navigation multi-niveaux

- Liste (catalogue) → détail (fiche anime)
- Collecte des URLs depuis la liste
- Enrichissement avec les infos de la fiche détail

### 4. Gestion d'erreurs et cas limites

- Scores manquants (`N/A`) → conversion en `None` ou filtrage
- Studios vides → champ optionnel
- Variations de structure (quelques cartes sans `.meta`, quelques fiches avec
  `<dl>` au lieu de `<table>`) → code défensif

### 5. Catégorisation de contenu

- Articles d'actualité avec `data-news-category` → filtrage thématique
- Genres multiples par anime → relations many-to-many

---

## Exemple de scraper (référence pour le formateur)

Un scraper de référence fonctionnel est fourni dans `generator/example_scraper.py`.
À ne **pas** distribuer tel quel aux apprenants, mais utile pour :
- vérifier que le site reste scrapable après une modification,
- debug rapide si un binôme bloque,
- base pour les corrections de TP.

---

## Points d'attention pour le déploiement en salle

- Le site pèse **~280 Ko** en tout, pas de problème de performance.
- Nginx en Alpine = image très légère (~50 Mo).
- Pas de JS, pas de cookies, pas de sessions : scraping direct.
- `robots.txt` autorise tout (c'est un site pédagogique).
- Encodage UTF-8 partout, y compris sur les titres japonais (pour éviter les
  galères de décodage qui feraient sortir du périmètre du cours).

---

## Licence & crédits

Données fictives à usage éducatif. Les titres d'anime mentionnés sont utilisés
de façon purement référentielle dans un cadre pédagogique non-commercial.
Ne pas redistribuer hors contexte de formation.
