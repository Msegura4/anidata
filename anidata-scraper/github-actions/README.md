# GitHub Actions — AniData Lab

Ce dossier contient deux workflows GitHub Actions et un Dockerfile, à intégrer
au repo `anidata-scraper`. Ils sont conçus pour être introduits progressivement
au cours de la semaine.

---

## Quoi mettre où

```
anidata-scraper/
├── .github/
│   └── workflows/
│       ├── ci.yml          ← séance 2
│       └── ci-cd.yml       ← séance 3 (remplace ou complète ci.yml)
├── Dockerfile              ← séance 3 (à la racine du repo)
├── anidata_scraper/
├── tests/
├── dags/                   ← à créer en séance 4
└── ...
```

---

## Progression pédagogique

### Séance 2 — `ci.yml`

**Objectif :** mettre en place une CI qui valide le code à chaque modification.

Ce workflow fait deux choses simples :

1. **Lint** avec ruff sur le code et les tests
2. **Tests** avec pytest, sur Python 3.10 et 3.11 en parallèle (matrice)

Le workflow est déclenché à chaque `push` sur main et à chaque Pull Request
ciblant main. Une PR ne peut pas être mergée si la CI est rouge (à condition
d'avoir activé la branch protection sur GitHub).

**Concepts abordés :**

- Structure d'un fichier YAML GitHub Actions (`on`, `jobs`, `steps`)
- Actions du Marketplace (`actions/checkout`, `actions/setup-python`)
- Matrice de versions pour tester plusieurs environnements
- Cache pip (clé `cache: pip`) pour accélérer les runs successifs
- Concurrency : annulation automatique des runs obsolètes
- Artefacts : upload du rapport de couverture pour le télécharger après le run

### Séance 3 — `ci-cd.yml` + `Dockerfile`

**Objectif :** étendre la CI avec un job de build et publication d'image
Docker, qui ne s'exécute que si la CI est verte.

Ce workflow fait tout ce que `ci.yml` fait, plus :

3. **Build** d'une image Docker Airflow custom (avec scraper + DAGs)
4. **Push** de l'image sur GitHub Container Registry (GHCR), automatiquement
   tagguée avec le SHA du commit, `latest`, et la version sémantique si tag.

**Concepts abordés :**

- Permissions du `GITHUB_TOKEN` (lecture code, écriture packages)
- `needs:` pour exprimer des dépendances entre jobs
- Conditions `if:` pour différencier push et PR
- `docker/login-action`, `docker/build-push-action`, `docker/metadata-action`
- Cache de build Docker (gha) pour accélérer les builds successifs
- Tags sémantiques générés automatiquement
- `$GITHUB_STEP_SUMMARY` pour produire un résumé visible dans l'UI GitHub

---

## Configuration requise sur GitHub

Avant que `ci-cd.yml` puisse pousser sur GHCR, il faut :

1. **Activer GHCR sur le repo**

   GHCR est activé par défaut sur GitHub. Aucune action manuelle nécessaire.

2. **Vérifier les permissions du `GITHUB_TOKEN`**

   Aller dans **Settings → Actions → General → Workflow permissions** et choisir :
   - **Read and write permissions** (au lieu de "Read repository contents
     and packages permissions")

   Cette case est nécessaire pour que `permissions: packages: write` dans
   le YAML soit honorée.

3. **Configurer la branch protection sur main**

   Settings → Branches → Add rule sur `main` :
   - ☑ Require a pull request before merging
   - ☑ Require approvals (1 reviewer)
   - ☑ Require status checks to pass before merging
     - Cocher les checks `Lint (ruff)` et `Tests (Python 3.10)`
   - ☑ Do not allow bypassing the above settings

---

## Récupérer l'image depuis Airflow local

Après le premier push réussi, l'image est disponible sur :

```
ghcr.io/<organisation>/<repo>-airflow:latest
```

Pour l'utiliser dans le `docker-compose.yml` Airflow local :

```yaml
services:
  airflow-webserver:
    image: ghcr.io/sakura-analytics/anidata-scraper-airflow:latest
    # ... reste de la config
```

Ou via une variable d'environnement (plus propre) :

```yaml
services:
  airflow-webserver:
    image: ${AIRFLOW_IMAGE:-ghcr.io/sakura-analytics/anidata-scraper-airflow:latest}
```

**Note** : si le repo est privé, il faut authentifier Docker auprès de GHCR avec
un Personal Access Token (PAT) avec le scope `read:packages` :

```bash
echo $CR_PAT | docker login ghcr.io -u <github-username> --password-stdin
```

---

## Exécuter localement (debug)

GitHub Actions ne se simule pas vraiment en local, mais on peut tester
les commandes manuellement :

```bash
# Reproduire le job lint
ruff check anidata_scraper/ tests/

# Reproduire le job tests
pytest --cov=anidata_scraper --cov-report=term-missing

# Reproduire le build Docker (nécessite le Dockerfile en place)
docker build -t anidata-airflow:local .
docker run --rm anidata-airflow:local python -c "import anidata_scraper; print('OK')"
```

Pour aller plus loin, l'outil [`act`](https://github.com/nektos/act) permet
d'exécuter un workflow GitHub Actions complet en local via Docker, mais il
n'est pas requis pour le cours.

---

## Quand le pipeline est-il déclenché ?

| Événement | `ci.yml` | `ci-cd.yml` (lint+tests) | `ci-cd.yml` (build+push) |
|---|---|---|---|
| Push sur `main` | ✅ | ✅ | ✅ pousse `:latest` + `:sha-xxx` |
| Push sur autre branche | ❌ | ❌ | ❌ |
| Pull Request vers `main` | ✅ | ✅ | ✅ build seulement, pas de push |
| Création d'un tag `v1.2.3` | ❌ | ✅ | ✅ pousse `:1.2.3` + `:1.2` |

---

## Schéma du pipeline complet

```
       ┌──────────────┐
       │  git push    │
       └──────┬───────┘
              │
              ▼
    ┌──────────────────┐
    │   GitHub Actions │
    │   (ci-cd.yml)    │
    └──────┬───────────┘
           │
       ┌───┴────┐
       ▼        ▼
    ┌──────┐ ┌──────┐
    │ Lint │ │Tests │   ← jobs en parallèle
    └──┬───┘ └──┬───┘
       │        │
       └────┬───┘
            │ (les deux verts)
            ▼
    ┌─────────────────┐
    │ Build & Push    │
    │ Docker → GHCR   │
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐
    │ Airflow local   │
    │ pull + redémarre│
    └─────────────────┘
```

---

## Pièges courants observés

- **L'image ne pousse pas** : vérifier les permissions du workflow dans
  Settings → Actions → General. Doit être en "Read and write".
- **Le job Docker tourne trop longtemps** : c'est normal au premier run
  (~3 minutes). Les suivants sont sous la minute grâce au cache `gha`.
- **`docker pull` échoue depuis Airflow local** : si le repo est privé, il
  faut un PAT (cf. plus haut). Pour un repo public, aucune authentification
  n'est nécessaire.
- **Tests qui passent en local mais échouent en CI** : presque toujours dû à
  une dépendance manquante de `requirements-dev.txt`, ou à des fichiers
  ignorés par `.gitignore` mais utilisés par les tests. Vérifier d'abord ces
  deux points.
