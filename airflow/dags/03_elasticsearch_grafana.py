"""
🎌 AniData Lab — DAG 4 : Indexation Elasticsearch + Annotation Grafana
=======================================================================
Rôle : après validation des données (DAG 2), indexer le dataset gold
       dans Elasticsearch et marquer le run dans Grafana.

  1. Charger anime_gold_validated.csv
  2. Créer/mettre à jour l'index Elasticsearch 'anidata-anime'
     avec mapping typé (float, int, keyword, text)
  3. Bulk-indexer tous les documents
  4. Créer une annotation de run dans Grafana via son API HTTP

Services requis :
  - Elasticsearch : http://anidata-elasticsearch:9200
  - Grafana        : http://anidata-grafana:3000  (admin / anidata)

Déclenchement : automatique via TriggerDagRunOperator depuis DAG 2
Auteur        : anidata-lab
"""

import os
import json
import logging
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator


# ══════════════════════════════════════════════════════════════════════════════
# CONSTANTES
# ══════════════════════════════════════════════════════════════════════════════

OUTPUT_DIR    = "/opt/airflow/data/output"
VALIDATED_CSV = os.path.join(OUTPUT_DIR, "anime_gold_validated.csv")
METADATA      = os.path.join(OUTPUT_DIR, "pipeline_metadata.json")
PIPELINE_LOG  = "/opt/airflow/logs/pipeline/echecs_pipeline.log"
LOG_DIR       = "/opt/airflow/logs/pipeline"

ES_HOST       = "http://anidata-elasticsearch:9200"
ES_INDEX      = "anidata-anime"

GRAFANA_HOST  = "http://anidata-grafana:3000"
GRAFANA_USER  = "admin"
GRAFANA_PASS  = "anidata"


# ══════════════════════════════════════════════════════════════════════════════
# ON FAILURE CALLBACK
# ══════════════════════════════════════════════════════════════════════════════

def on_failure_callback(context: dict) -> None:
    task_id   = context["task_instance"].task_id
    dag_id    = context["task_instance"].dag_id
    exception = context.get("exception", "Erreur inconnue")
    ts        = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    msg = (
        f"\n{'═' * 60}\n[ÉCHEC] {ts}\n"
        f"  DAG    : {dag_id}\n  Tâche  : {task_id}\n  Erreur : {exception}\n"
        f"{'═' * 60}\n"
    )
    logging.error(msg)
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        with open(PIPELINE_LOG, "a", encoding="utf-8") as f:
            f.write(msg)
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════════════════
# DEFAULT ARGS
# ══════════════════════════════════════════════════════════════════════════════

default_args = {
    "owner": "anidata-lab",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=2),
    "on_failure_callback": on_failure_callback,
}


# ══════════════════════════════════════════════════════════════════════════════
# TÂCHE 1 — CHARGER LES DONNÉES
# ══════════════════════════════════════════════════════════════════════════════

def charger_donnees(**kwargs) -> str:
    """
    Lit anime_gold_validated.csv produit par DAG 2.
    Pousse les records via XCom pour la tâche d'indexation.
    """
    import pandas as pd

    log = logging.getLogger(__name__)

    if not os.path.exists(VALIDATED_CSV):
        raise FileNotFoundError(
            f"❌ Fichier introuvable : {VALIDATED_CSV}\n"
            f"   Assurez-vous que DAG 2 a bien tourné."
        )

    df = pd.read_csv(VALIDATED_CSV)
    log.info(f"📂 Dataset gold chargé : {len(df)} lignes × {len(df.columns)} colonnes")
    log.info(f"   Colonnes : {list(df.columns)}")

    # Nettoyage pour ES : NaN → None, int64 → int
    df = df.where(pd.notnull(df), other=None)
    for col in df.select_dtypes(include="int64").columns:
        df[col] = df[col].apply(lambda x: int(x) if x is not None else None)
    for col in df.select_dtypes(include="float64").columns:
        df[col] = df[col].apply(lambda x: round(float(x), 4) if x is not None else None)

    records = df.to_dict(orient="records")
    log.info(f"✅ {len(records)} documents prêts pour Elasticsearch")

    kwargs["ti"].xcom_push(key="records",   value=records)
    kwargs["ti"].xcom_push(key="nb_lignes", value=len(records))
    kwargs["ti"].xcom_push(key="colonnes",  value=list(df.columns))

    return f"chargement_ok | {len(records)} documents | {len(df.columns)} colonnes"


# ══════════════════════════════════════════════════════════════════════════════
# TÂCHE 2 — INDEXER DANS ELASTICSEARCH
# ══════════════════════════════════════════════════════════════════════════════

def indexer_elasticsearch(**kwargs) -> str:
    """
    Crée (ou recrée) l'index 'anidata-anime' dans Elasticsearch
    avec un mapping typé, puis bulk-indexe tous les documents.

    Index créé : anidata-anime
    Mapping    :
      MAL_ID   → integer    Name     → text + keyword
      Score    → float      Members  → integer
      Genres   → keyword    Type     → keyword
      Episodes → integer    Aired    → keyword
      Studios  → keyword    Status   → keyword
      + colonnes feature engineering (Score_norm, etc.)
    """
    from elasticsearch import Elasticsearch, helpers

    log     = logging.getLogger(__name__)
    ti      = kwargs["ti"]
    records = ti.xcom_pull(task_ids="charger_donnees", key="records") or []

    if not records:
        raise ValueError("❌ Aucun document reçu depuis charger_donnees")

    # ── Connexion ─────────────────────────────────────────────────────────────
    es = Elasticsearch(ES_HOST)
    if not es.ping():
        raise ConnectionError(f"❌ Impossible de joindre Elasticsearch : {ES_HOST}")
    log.info(f"✅ Connecté à Elasticsearch : {ES_HOST}")

    # ── Mapping ───────────────────────────────────────────────────────────────
    mapping = {
        "mappings": {
            "properties": {
                "MAL_ID":        {"type": "integer"},
                "Name":          {"type": "text",    "fields": {"keyword": {"type": "keyword"}}},
                "Score":         {"type": "float"},
                "Members":       {"type": "integer"},
                "Genres":        {"type": "keyword"},
                "Type":          {"type": "keyword"},
                "Episodes":      {"type": "integer"},
                "Aired":         {"type": "keyword"},
                "Studios":       {"type": "keyword"},
                "Status":        {"type": "keyword"},
                "Score_norm":    {"type": "float"},
                "Members_log":   {"type": "float"},
                "Score_tier":    {"type": "keyword"},
                "Members_tier":  {"type": "keyword"},
                "run_timestamp": {"type": "date", "format": "yyyy-MM-dd HH:mm:ss||strict_date_optional_time"},
            }
        },
        "settings": {
            "number_of_shards":   1,
            "number_of_replicas": 0,   # pas de replica en local
        }
    }

    # Supprime et recrée l'index pour avoir des données fraîches à chaque run
    if es.indices.exists(index=ES_INDEX):
        es.indices.delete(index=ES_INDEX)
        log.info(f"🗑️  Index existant supprimé : {ES_INDEX}")

    es.indices.create(index=ES_INDEX, body=mapping)
    log.info(f"✅ Index créé : {ES_INDEX}")

    # ── Ajout du timestamp de run ─────────────────────────────────────────────
    ts_run = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for rec in records:
        rec["run_timestamp"] = ts_run

    # ── Bulk indexation ───────────────────────────────────────────────────────
    actions = [
        {
            "_index": ES_INDEX,
            "_id":    rec.get("MAL_ID"),
            "_source": rec,
        }
        for rec in records
    ]

    succes, erreurs = helpers.bulk(es, actions, raise_on_error=False)
    log.info(f"✅ Indexation terminée : {succes} documents indexés")

    if erreurs:
        log.warning(f"⚠️  {len(erreurs)} erreur(s) lors du bulk :")
        for e in erreurs[:5]:
            log.warning(f"   {e}")

    # ── Stats de l'index ──────────────────────────────────────────────────────
    count = es.count(index=ES_INDEX)["count"]
    log.info(f"📊 Documents dans '{ES_INDEX}' : {count}")

    kwargs["ti"].xcom_push(key="nb_indexes", value=succes)
    kwargs["ti"].xcom_push(key="ts_run",     value=ts_run)

    return f"indexation_ok | {succes}/{len(records)} documents → {ES_INDEX}"


# ══════════════════════════════════════════════════════════════════════════════
# TÂCHE 3 — ANNOTATION GRAFANA
# ══════════════════════════════════════════════════════════════════════════════

def annoter_grafana(**kwargs) -> str:
    """
    Crée une annotation dans Grafana pour marquer le run du pipeline.
    L'annotation apparaît sur tous les dashboards comme marqueur temporel.

    En cas d'erreur Grafana (service down, auth incorrecte) :
    → warning non bloquant, la tâche ne fail pas.
    """
    import urllib.request
    import urllib.error
    import base64

    log       = logging.getLogger(__name__)
    ti        = kwargs["ti"]
    nb_indexes = ti.xcom_pull(task_ids="indexer_elasticsearch", key="nb_indexes") or 0
    ts_run     = ti.xcom_pull(task_ids="indexer_elasticsearch", key="ts_run") or datetime.now().isoformat()
    nb_lignes  = ti.xcom_pull(task_ids="charger_donnees",       key="nb_lignes") or 0

    annotation = {
        "time":    int(datetime.now().timestamp() * 1000),  # ms epoch
        "tags":    ["anidata", "pipeline_run", "dag4"],
        "text":    (
            f"🎌 AniData Pipeline — Run {ts_run} | "
            f"{nb_indexes}/{nb_lignes} anime indexés dans ES"
        ),
    }

    url     = f"{GRAFANA_HOST}/api/annotations"
    payload = json.dumps(annotation).encode("utf-8")
    creds   = base64.b64encode(f"{GRAFANA_USER}:{GRAFANA_PASS}".encode()).decode()

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type":  "application/json",
            "Authorization": f"Basic {creds}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode()
            log.info(f"✅ Annotation Grafana créée : {body}")
            return f"grafana_ok | annotation créée | {nb_indexes} docs indexés"

    except urllib.error.URLError as e:
        # Grafana pas démarré → warning non bloquant
        log.warning(f"⚠️  Grafana inaccessible ({GRAFANA_HOST}) : {e}")
        log.warning(f"   Lance Grafana avec : docker compose up -d grafana")
        log.info(f"   Données disponibles dans Elasticsearch : index={ES_INDEX}, docs={nb_indexes}")
        return f"grafana_skip | Grafana non joignable | ES={ES_INDEX} ({nb_indexes} docs)"


# ══════════════════════════════════════════════════════════════════════════════
# DAG
# ══════════════════════════════════════════════════════════════════════════════

with DAG(
    dag_id="03_elasticsearch_grafana",
    description="🎌 DAG 4 — Indexe les données gold dans Elasticsearch + annote Grafana",
    default_args=default_args,
    schedule_interval=None,   # déclenché par DAG 2 uniquement
    start_date=datetime(2026, 3, 25),
    catchup=False,
    tags=["anidata", "elasticsearch", "grafana"],
) as dag:

    t_charger = PythonOperator(
        task_id="charger_donnees",
        python_callable=charger_donnees,
        doc_md="**Tâche 1** — Lit anime_gold_validated.csv et prépare les documents",
    )

    t_indexer = PythonOperator(
        task_id="indexer_elasticsearch",
        python_callable=indexer_elasticsearch,
        doc_md="**Tâche 2** — Crée l'index anidata-anime et bulk-indexe tous les documents",
    )

    t_grafana = PythonOperator(
        task_id="annoter_grafana",
        python_callable=annoter_grafana,
        doc_md="**Tâche 3** — Crée une annotation de run dans Grafana via API HTTP",
    )

    # ── Flux ─────────────────────────────────────────────────────────────────
    #
    #   charger_donnees
    #         │
    #   indexer_elasticsearch
    #         │
    #   annoter_grafana
    #
    t_charger >> t_indexer >> t_grafana
