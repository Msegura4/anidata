"""
🎌 AniData Lab — Indexation dans Elasticsearch
================================================
Séance 3 — Mardi 24 mars 2026 — Après-midi

Ce script :
  1. Vérifie la connexion à Elasticsearch
  2. Crée l'index "anime" avec un mapping optimisé
  3. Indexe le dataset anime_gold.json en bulk
  4. Vérifie l'indexation avec des requêtes de test
  5. Affiche des statistiques

Usage : python 06_indexation_es.py
Prérequis : pip install elasticsearch pandas
Entrée : output/anime_gold.json (généré par 05_validation.py)
"""

import json
import os
import sys
import time

try:
    from elasticsearch import Elasticsearch, helpers
except ImportError:
    print("❌ Module 'elasticsearch' non installé.")
    print("   Installez-le avec : pip install elasticsearch")
    sys.exit(1)

# ============================================
# CONFIG
# ============================================
ES_HOST = "http://localhost:9200"
INDEX_NAME = "anime"
INPUT_FILE = os.path.join("output", "anime_gold.json")
BULK_CHUNK_SIZE = 500

class C:
    H = "\033[95m"; B = "\033[94m"; G = "\033[92m"
    W = "\033[93m"; F = "\033[91m"; BOLD = "\033[1m"
    CYAN = "\033[96m"; END = "\033[0m"

def titre(t):
    print(f"\n{C.BOLD}{C.H}{'='*60}\n  {t}\n{'='*60}{C.END}\n")

def step(t):
    print(f"\n{C.BOLD}{C.B}--- {t} ---{C.END}")

def ok(t):
    print(f"  {C.G}✅ {t}{C.END}")

def warn(t):
    print(f"  {C.W}⚠️  {t}{C.END}")

def fail(t):
    print(f"  {C.F}❌ {t}{C.END}")

def info(t):
    print(f"  {C.B}ℹ️  {t}{C.END}")


# ============================================
# MAPPING ELASTICSEARCH
# ============================================
ANIME_MAPPING = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
        "analysis": {
            "analyzer": {
                "anime_analyzer": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase", "asciifolding"]
                }
            }
        }
    },
    "mappings": {
        "properties": {
            # --- Identifiants ---
            "mal_id":           { "type": "integer" },

            # --- Noms (recherche full-text) ---
            "name":             { "type": "text", "analyzer": "anime_analyzer",
                                  "fields": { "keyword": { "type": "keyword" } } },
            "english_name":     { "type": "text", "analyzer": "anime_analyzer" },
            "japanese_name":    { "type": "text" },

            # --- Scores ---
            "score":            { "type": "float" },
            "weighted_score":   { "type": "float" },
            "score_category":   { "type": "keyword" },

            # --- Catégories ---
            "type":             { "type": "keyword" },
            "source":           { "type": "keyword" },
            "rating":           { "type": "keyword" },

            # --- Genres ---
            "genres":           { "type": "keyword" },
            "main_genre":       { "type": "keyword" },
            "n_genres":         { "type": "integer" },

            # --- Studios ---
            "studios":          { "type": "keyword" },
            "main_studio":      { "type": "keyword" },
            "studio_tier":      { "type": "keyword" },

            # --- Statistiques numériques ---
            "episodes":         { "type": "integer" },
            "members":          { "type": "long" },
            "favorites":        { "type": "long" },
            "popularity":       { "type": "integer" },
            "ranked":           { "type": "float" },

            # --- Métriques calculées ---
            "drop_ratio":       { "type": "float" },
            "engagement_ratio": { "type": "float" },
            "duration_minutes": { "type": "integer" },

            # --- Compteurs de statut ---
            "watching":         { "type": "long" },
            "completed":        { "type": "long" },
            "on_hold":          { "type": "long" },
            "dropped":          { "type": "long" },
            "plan_to_watch":    { "type": "long" },

            # --- Temporel ---
            "aired":            { "type": "text" },
            "aired_start":      { "type": "date", "format": "yyyy-MM-dd||epoch_millis||strict_date_optional_time", "ignore_malformed": True },
            "aired_end":        { "type": "date", "format": "yyyy-MM-dd||epoch_millis||strict_date_optional_time", "ignore_malformed": True },
            "premiered":        { "type": "keyword" },
            "year":             { "type": "integer" },
            "decade":           { "type": "integer" },

            # --- Scores détaillés ---
            "score_10":         { "type": "long" },
            "score_9":          { "type": "long" },
            "score_8":          { "type": "long" },
            "score_7":          { "type": "long" },
            "score_6":          { "type": "long" },
            "score_5":          { "type": "long" },
            "score_4":          { "type": "long" },
            "score_3":          { "type": "long" },
            "score_2":          { "type": "long" },
            "score_1":          { "type": "long" },

            # --- Flags ---
            "is_outlier":       { "type": "boolean" },

            # --- Autres textes ---
            "duration":         { "type": "keyword" },
            "producers":        { "type": "keyword" },
            "licensors":        { "type": "keyword" },
        }
    }
}


# ============================================
# 1. VÉRIFIER LA CONNEXION
# ============================================
titre("INDEXATION ELASTICSEARCH")

step("Étape 1 : Connexion à Elasticsearch")

print(f"  Tentative de connexion à {ES_HOST}...")

es = Elasticsearch(ES_HOST, request_timeout=30)

# Attendre que ES soit prêt (peut prendre du temps au démarrage)
max_retries = 10
for attempt in range(max_retries):
    try:
        health = es.cluster.health()
        cluster_name = health.get("cluster_name", "?")
        status = health.get("status", "?")
        ok(f"Connecté au cluster '{cluster_name}' (status: {status})")
        break
    except Exception as e:
        if attempt < max_retries - 1:
            print(f"  ⏳ ES pas encore prêt (tentative {attempt + 1}/{max_retries})... attente 5s")
            time.sleep(5)
        else:
            fail(f"Impossible de se connecter à {ES_HOST}")
            print(f"  Erreur : {e}")
            print(f"\n  Vérifiez que Docker tourne :")
            print(f"    docker compose ps")
            print(f"    docker compose logs elasticsearch")
            sys.exit(1)


# ============================================
# 2. VÉRIFIER LE FICHIER D'ENTRÉE
# ============================================
step("Étape 2 : Vérification du fichier source")

if not os.path.exists(INPUT_FILE):
    fail(f"Fichier introuvable : {INPUT_FILE}")
    print(f"  Lancez d'abord les scripts de nettoyage :")
    print(f"    python scripts/03_nettoyage.py")
    print(f"    python scripts/04_feature_engineering.py")
    print(f"    python scripts/05_validation.py")
    sys.exit(1)

# Compter les documents
with open(INPUT_FILE, "r", encoding="utf-8") as f:
    docs = [json.loads(line) for line in f if line.strip()]

taille_mb = os.path.getsize(INPUT_FILE) / (1024 * 1024)
ok(f"Fichier chargé : {len(docs):,} documents ({taille_mb:.1f} MB)")

# Aperçu du premier document
if docs:
    first = docs[0]
    info(f"Premier document : {list(first.keys())[:8]}...")
    name_key = "name" if "name" in first else list(first.keys())[0]
    info(f"Exemple : {first.get(name_key, '?')} (score: {first.get('score', '?')})")


# ============================================
# 3. CRÉER / RECRÉER L'INDEX
# ============================================
step("Étape 3 : Création de l'index")

# Supprimer l'index existant si présent
if es.indices.exists(index=INDEX_NAME):
    warn(f"L'index '{INDEX_NAME}' existe déjà — suppression...")
    es.indices.delete(index=INDEX_NAME)
    ok("Ancien index supprimé")

# Créer l'index avec le mapping
print(f"  Création de l'index '{INDEX_NAME}' avec mapping...")
try:
    es.indices.create(index=INDEX_NAME, body=ANIME_MAPPING)
    ok(f"Index '{INDEX_NAME}' créé avec succès")

    # Afficher le mapping
    mapping_fields = list(ANIME_MAPPING["mappings"]["properties"].keys())
    info(f"Mapping : {len(mapping_fields)} champs définis")
    print(f"  Types principaux :")
    type_counts = {}
    for field, config in ANIME_MAPPING["mappings"]["properties"].items():
        t = config.get("type", "?")
        type_counts[t] = type_counts.get(t, 0) + 1
    for t, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"    • {t:12s} : {count} champs")

except Exception as e:
    fail(f"Erreur lors de la création de l'index : {e}")
    sys.exit(1)


# ============================================
# 4. INDEXATION BULK
# ============================================
step(f"Étape 4 : Indexation bulk ({len(docs):,} documents)")

print(f"  Taille des chunks : {BULK_CHUNK_SIZE} documents")
print(f"  Début de l'indexation...\n")

# Préparer les actions bulk
def generate_actions(documents):
    for doc in documents:
        # Déterminer l'ID du document
        doc_id = doc.get("mal_id", doc.get("anime_id", None))

        # Nettoyer les valeurs NaN/None pour ES
        clean_doc = {}
        for key, value in doc.items():
            if value is None:
                continue
            if isinstance(value, float) and (value != value):  # NaN check
                continue
            clean_doc[key] = value

        action = {
            "_index": INDEX_NAME,
            "_source": clean_doc,
        }
        if doc_id is not None:
            action["_id"] = str(doc_id)

        yield action

# Indexation avec suivi de progression
start_time = time.time()
success_count = 0
error_count = 0
errors = []

try:
    for ok_flag, result in helpers.streaming_bulk(
        es,
        generate_actions(docs),
        chunk_size=BULK_CHUNK_SIZE,
        raise_on_error=False,
        raise_on_exception=False,
    ):
        if ok_flag:
            success_count += 1
        else:
            error_count += 1
            if len(errors) < 5:  # Garder les 5 premières erreurs
                errors.append(result)

        # Progression
        total = success_count + error_count
        if total % 2000 == 0 or total == len(docs):
            elapsed = time.time() - start_time
            rate = total / elapsed if elapsed > 0 else 0
            pct = total / len(docs) * 100
            bar = "█" * int(pct / 2.5) + "░" * (40 - int(pct / 2.5))
            print(f"\r  [{bar}] {pct:5.1f}% — {total:,}/{len(docs):,} — {rate:.0f} docs/s", end="", flush=True)

except Exception as e:
    fail(f"Erreur pendant l'indexation : {e}")

print()  # Nouvelle ligne après la barre de progression

elapsed = time.time() - start_time
ok(f"Indexation terminée en {elapsed:.1f} secondes")
ok(f"  Succès : {success_count:,}")
if error_count > 0:
    warn(f"  Erreurs : {error_count:,}")
    for err in errors[:3]:
        print(f"    → {err}")

# Rafraîchir l'index pour que les documents soient disponibles immédiatement
es.indices.refresh(index=INDEX_NAME)


# ============================================
# 5. VÉRIFICATION
# ============================================
step("Étape 5 : Vérification de l'indexation")

# Comptage
count = es.count(index=INDEX_NAME)["count"]
ok(f"Documents dans l'index : {count:,}")

if count != success_count:
    warn(f"Attention : {success_count:,} indexés mais {count:,} dans l'index")

# Taille de l'index
stats = es.indices.stats(index=INDEX_NAME)
size_bytes = stats["indices"][INDEX_NAME]["total"]["store"]["size_in_bytes"]
size_mb = size_bytes / (1024 * 1024)
info(f"Taille de l'index : {size_mb:.1f} MB")

# Test de recherche
print(f"\n  Tests de recherche rapides :")
print(f"  {'─'*50}")

# Test 1 : match all
result = es.search(index=INDEX_NAME, body={"query": {"match_all": {}}, "size": 1})
total_hits = result["hits"]["total"]["value"]
ok(f"match_all : {total_hits:,} résultats")

# Test 2 : recherche par nom
test_queries = [
    ("Naruto", {"query": {"match": {"name": "naruto"}}}),
    ("Score > 9", {"query": {"range": {"score": {"gte": 9}}}}),
    ("Genre: Action", {"query": {"term": {"main_genre": "Action"}}}),
    ("Studio: Bones", {"query": {"match": {"main_studio": "Bones"}}}),
]

for name, query in test_queries:
    try:
        result = es.search(index=INDEX_NAME, body={**query, "size": 3})
        hits = result["hits"]["total"]["value"]
        top_name = result["hits"]["hits"][0]["_source"].get("name", "?") if result["hits"]["hits"] else "aucun"
        ok(f"{name:20s} → {hits:,} résultats (top: {top_name})")
    except Exception as e:
        warn(f"{name:20s} → Erreur : {e}")

# Test 3 : agrégation top genres
print(f"\n  Agrégation : Top 5 genres")
print(f"  {'─'*50}")
agg_result = es.search(index=INDEX_NAME, body={
    "size": 0,
    "aggs": {
        "top_genres": {
            "terms": {"field": "main_genre", "size": 5}
        }
    }
})
for bucket in agg_result["aggregations"]["top_genres"]["buckets"]:
    genre = bucket["key"]
    count = bucket["doc_count"]
    bar = "█" * int(count / 500)
    print(f"    {genre:20s} : {count:>5,} {bar}")

# Test 4 : agrégation score moyen par type
print(f"\n  Agrégation : Score moyen par type")
print(f"  {'─'*50}")
agg_result = es.search(index=INDEX_NAME, body={
    "size": 0,
    "aggs": {
        "by_type": {
            "terms": {"field": "type", "size": 10},
            "aggs": {
                "avg_score": {"avg": {"field": "score"}}
            }
        }
    }
})
for bucket in agg_result["aggregations"]["by_type"]["buckets"]:
    anime_type = bucket["key"]
    avg = bucket["avg_score"]["value"]
    count = bucket["doc_count"]
    if avg:
        print(f"    {anime_type:12s} : score moyen {avg:.2f} ({count:,} animes)")


# ============================================
# 6. RÉSUMÉ FINAL
# ============================================
titre("INDEXATION TERMINÉE")

print(f"""
{C.BOLD}{C.CYAN}  Index           : {INDEX_NAME}
  Documents       : {count:,}
  Taille          : {size_mb:.1f} MB
  Temps           : {elapsed:.1f}s
  Débit           : {count/elapsed:.0f} docs/s{C.END}

{C.BOLD}  Accès :{C.END}
  {C.B}📊 Grafana        → http://localhost:3000  (admin / anidata){C.END}
  {C.B}🔍 Elasticsearch  → http://localhost:9200/anime/_search{C.END}

{C.BOLD}  Requêtes utiles :{C.END}
  {C.CYAN}curl http://localhost:9200/anime/_count{C.END}
  {C.CYAN}curl "http://localhost:9200/anime/_search?q=name:naruto&pretty"{C.END}
  {C.CYAN}curl "http://localhost:9200/anime/_search?q=main_genre:Action&size=5&pretty"{C.END}

{C.BOLD}{C.G}✅ Les données sont prêtes dans Elasticsearch !
   Ouvrez Grafana pour créer vos dashboards.{C.END}
""")