"""
🎌 AniData Lab — DAG 1 : Ingestion & Conversion
=================================================
Rôle : porte d'entrée des données brutes.

  1. Scanner le dossier data/input/ pour trouver un fichier .json ou .xml
  2. Détecter automatiquement le format (BranchPythonOperator)
  3. Convertir en CSV normalisé → data/anime.csv (entrée de DAG 2)
  4. Valider le CSV produit et écrire les métriques dans pipeline_metadata.json
  5. Déclencher DAG 2 (01_pipeline_anidata)

Mapping de colonnes (source → cible DAG 2) :
  anime_id  → MAL_ID
  name      → Name
  genre     → Genres   (liste → chaîne séparée par virgules)
  type      → Type
  episodes  → Episodes
  rating    → Score
  members   → Members
  year      → Aired    (formaté "Jan 1, YEAR")
  studio    → Studios

Déclenchement : manuel ou schedulé
Auteur        : anidata-lab
"""

import os
import json
import logging
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator


# ══════════════════════════════════════════════════════════════════════════════
# CHEMINS
# ══════════════════════════════════════════════════════════════════════════════

INPUT_DIR    = "/opt/airflow/data/input"           # → ./data/input/
ARCHIVE_DIR  = "/opt/airflow/data/archive"          # → ./data/archive/
OUTPUT_DIR   = "/opt/airflow/data/output"          # → ./data/output/
ANIME_CSV    = "/opt/airflow/data/anime.csv"         # fichier cible pour DAG 2
METADATA     = "/opt/airflow/data/output/pipeline_metadata.json"
PIPELINE_LOG = "/opt/airflow/logs/pipeline/echecs_pipeline.log"
LOG_DIR      = "/opt/airflow/logs/pipeline"

# Mapping de colonnes : nom source → nom cible (standard DAG 2)
COL_MAP = {
    "anime_id": "MAL_ID",
    "name":     "Name",
    "genre":    "Genres",   # JSON : liste ou chaîne
    "genres":   "Genres",   # XML  : balise plurielle imbriquée
    "type":     "Type",
    "episodes": "Episodes",
    "rating":   "Score",
    "members":  "Members",
    "year":     "Aired",
    "studio":   "Studios",
    # champs supplémentaires acceptés (non bloquants)
    "status":   "Status",
}


# ══════════════════════════════════════════════════════════════════════════════
# ON FAILURE CALLBACK
# ══════════════════════════════════════════════════════════════════════════════

def on_failure_callback(context: dict) -> None:
    task_id   = context["task_instance"].task_id
    dag_id    = context["task_instance"].dag_id
    run_id    = context.get("run_id", "inconnu")
    exception = context.get("exception", "Erreur inconnue")
    ts        = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    msg = (
        f"\n{'═' * 60}\n"
        f"[ÉCHEC] {ts}\n"
        f"  DAG     : {dag_id}\n"
        f"  Tâche   : {task_id}\n"
        f"  Run ID  : {run_id}\n"
        f"  Erreur  : {exception}\n"
        f"{'═' * 60}\n"
    )
    logging.error(msg)
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        with open(PIPELINE_LOG, "a", encoding="utf-8") as f:
            f.write(msg)
    except Exception as e:
        logging.warning(f"⚠️  Impossible d'écrire dans {PIPELINE_LOG} : {e}")


# ══════════════════════════════════════════════════════════════════════════════
# DEFAULT ARGS
# ══════════════════════════════════════════════════════════════════════════════

default_args = {
    "owner": "anidata-lab",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=0.25),
    "on_failure_callback": on_failure_callback,
}


# ══════════════════════════════════════════════════════════════════════════════
# TÂCHE 1 — SCANNER LE DOSSIER INPUT
# ══════════════════════════════════════════════════════════════════════════════

def scanner_dossier(**kwargs) -> str:
    """
    Parcourt data/input/ et trouve le premier fichier .json ou .xml.
    Pousse le chemin et le format via XCom.
    Lève une erreur si aucun fichier éligible n'est trouvé.
    """
    log = logging.getLogger(__name__)
    os.makedirs(INPUT_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    fichiers_trouves = []
    for f in os.listdir(INPUT_DIR):
        ext = os.path.splitext(f)[1].lower()
        if ext in (".json", ".xml"):
            fichiers_trouves.append(os.path.join(INPUT_DIR, f))

    if not fichiers_trouves:
        raise FileNotFoundError(
            f"❌ Aucun fichier .json ou .xml trouvé dans {INPUT_DIR}\n"
            f"   Déposez un fichier à convertir dans ce dossier."
        )

    # Prend le fichier le plus récent
    fichier = sorted(fichiers_trouves, key=os.path.getmtime, reverse=True)[0]
    ext     = os.path.splitext(fichier)[1].lower().lstrip(".")

    taille_kb = os.path.getsize(fichier) / 1024
    log.info(f"✅ Fichier détecté : {os.path.basename(fichier)} ({taille_kb:.1f} KB)")
    log.info(f"   Format          : {ext.upper()}")
    log.info(f"   Chemin complet  : {fichier}")

    if len(fichiers_trouves) > 1:
        log.warning(f"⚠️  {len(fichiers_trouves)} fichiers trouvés — traitement du plus récent uniquement")

    kwargs["ti"].xcom_push(key="fichier_source", value=fichier)
    kwargs["ti"].xcom_push(key="format_source",  value=ext)

    return f"scanner_ok | {os.path.basename(fichier)} | format={ext.upper()}"


# ══════════════════════════════════════════════════════════════════════════════
# TÂCHE 2 — DÉTECTER LE FORMAT (branchement)
# ══════════════════════════════════════════════════════════════════════════════

def detecter_format(**kwargs) -> str:
    """
    BranchPythonOperator : lit le format détecté dans XCom
    et retourne le task_id de la branche à emprunter.
    """
    fmt = kwargs["ti"].xcom_pull(task_ids="scanner_dossier", key="format_source")
    log = logging.getLogger(__name__)
    log.info(f"🔀 Format détecté : {fmt.upper()} → branche 'convertir_{fmt}'")

    if fmt == "json":
        return "convertir_json"
    elif fmt == "xml":
        return "convertir_xml"
    else:
        raise ValueError(f"❌ Format non supporté : {fmt} (attendu : json ou xml)")


# ══════════════════════════════════════════════════════════════════════════════
# TÂCHE 3a — CONVERSION JSON → CSV
# ══════════════════════════════════════════════════════════════════════════════

def convertir_json(**kwargs) -> str:
    """
    Lit un fichier JSON structuré (liste de records ou objet avec clé 'records')
    et le convertit en CSV normalisé pour DAG 2.

    Formats JSON acceptés :
      - {"records": [...]}   ← format avec clé wrapper
      - [...]                ← liste directe
    """
    import pandas as pd

    log     = logging.getLogger(__name__)
    fichier = kwargs["ti"].xcom_pull(task_ids="scanner_dossier", key="fichier_source")

    log.info(f"📂 Lecture JSON : {fichier}")

    with open(fichier, "r", encoding="utf-8") as f:
        raw = json.load(f)

    # Gestion des deux structures possibles
    if isinstance(raw, list):
        records = raw
    elif isinstance(raw, dict):
        # Cherche une clé contenant une liste
        for key, val in raw.items():
            if isinstance(val, list):
                records = val
                log.info(f"   Clé wrapper détectée : '{key}'")
                break
        else:
            raise ValueError(f"❌ Aucune liste de records trouvée dans le JSON")
    else:
        raise ValueError(f"❌ Structure JSON non reconnue (type={type(raw)})")

    df = pd.DataFrame(records)
    log.info(f"   {len(df)} lignes × {len(df.columns)} colonnes brutes")
    log.info(f"   Colonnes source : {list(df.columns)}")

    df = _normaliser_colonnes(df, log)
    _sauvegarder_csv(df, log)

    kwargs["ti"].xcom_push(key="nb_lignes_converties", value=len(df))
    kwargs["ti"].xcom_push(key="format_converti", value="JSON")

    return f"convertir_json_ok | {len(df)} lignes converties → anime.csv"


# ══════════════════════════════════════════════════════════════════════════════
# TÂCHE 3b — CONVERSION XML → CSV
# ══════════════════════════════════════════════════════════════════════════════

def convertir_xml(**kwargs) -> str:
    """
    Lit un fichier XML structuré (<anime_database><anime>...</anime></anime_database>)
    et le convertit en CSV normalisé pour DAG 2.
    """
    import pandas as pd
    import xml.etree.ElementTree as ET

    log     = logging.getLogger(__name__)
    fichier = kwargs["ti"].xcom_pull(task_ids="scanner_dossier", key="fichier_source")

    log.info(f"📂 Lecture XML : {fichier}")

    tree = ET.parse(fichier)
    root = tree.getroot()

    # Détection automatique de la balise répétée (premier enfant)
    balise_anime = None
    for child in root:
        if len(list(root.findall(child.tag))) > 0:
            balise_anime = child.tag
            break

    if balise_anime is None:
        raise ValueError("❌ Impossible de détecter la balise répétée dans le XML")

    log.info(f"   Balise anime détectée : <{balise_anime}>")

    records = []
    for element in root.findall(balise_anime):
        record = {}
        for child in element:
            sous_enfants = list(child)
            if sous_enfants:
                # Champ imbriqué : <genres><genre>X</genre><genre>Y</genre></genres>
                # → "X, Y"
                record[child.tag] = ", ".join(
                    sc.text.strip() for sc in sous_enfants if sc.text
                )
            else:
                # Champ texte simple : <name>Spy x Family</name>
                record[child.tag] = child.text.strip() if child.text else None
        records.append(record)

    if not records:
        raise ValueError(f"❌ Aucun enregistrement <{balise_anime}> trouvé dans le XML")

    df = pd.DataFrame(records)
    log.info(f"   {len(df)} lignes × {len(df.columns)} colonnes brutes")
    log.info(f"   Colonnes source : {list(df.columns)}")

    df = _normaliser_colonnes(df, log)
    _sauvegarder_csv(df, log)

    kwargs["ti"].xcom_push(key="nb_lignes_converties", value=len(df))
    kwargs["ti"].xcom_push(key="format_converti", value="XML")

    return f"convertir_xml_ok | {len(df)} lignes converties → anime.csv"


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS PARTAGÉS (non exposés comme tâches)
# ══════════════════════════════════════════════════════════════════════════════

def _normaliser_colonnes(df, log) -> "pd.DataFrame":
    """
    Renomme les colonnes selon COL_MAP et normalise les types.
    Colonnes non mappées conservées telles quelles.
    """
    import pandas as pd

    # Renommage
    colonnes_presentes = {k: v for k, v in COL_MAP.items() if k in df.columns}
    df = df.rename(columns=colonnes_presentes)
    log.info(f"   Colonnes renommées : {colonnes_presentes}")

    # Normalisation genre : liste Python ou chaîne → chaîne CSV
    if "Genres" in df.columns:
        def normaliser_genre(g):
            if isinstance(g, list):
                return ", ".join(str(x).strip() for x in g)
            return str(g).strip() if g else ""
        df["Genres"] = df["Genres"].apply(normaliser_genre)

    # Normalisation Aired : year int/str → "Jan 1, YEAR"
    if "Aired" in df.columns:
        def normaliser_aired(y):
            try:
                return f"Jan 1, {int(float(str(y)))}"
            except (ValueError, TypeError):
                return str(y)
        df["Aired"] = df["Aired"].apply(normaliser_aired)

    # Normalisation types numériques
    for col in ["Score", "Members", "Episodes", "MAL_ID"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    colonnes_finales = list(df.columns)
    log.info(f"   Colonnes finales  : {colonnes_finales}")
    return df


def _sauvegarder_csv(df, log) -> None:
    """
    Écrit le DataFrame dans data/anime.csv via un fichier temporaire.
    Stratégie : écriture dans un .tmp puis os.replace() atomique
    → évite le [Errno 35] Resource deadlock sur macOS/Docker VirtioFS.
    Retente jusqu'à 5 fois avec 1s de délai si le lock persiste.
    """
    import time
    import tempfile

    os.makedirs(os.path.dirname(ANIME_CSV), exist_ok=True)
    dir_csv   = os.path.dirname(ANIME_CSV)
    max_tries = 5

    for tentative in range(1, max_tries + 1):
        tmp_path = None
        try:
            # 1. Écriture dans un fichier temporaire du même dossier
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".tmp", dir=dir_csv,
                delete=False, encoding="utf-8"
            ) as tmp:
                tmp_path = tmp.name

            df.to_csv(tmp_path, index=False, encoding="utf-8")

            # 2. Remplacement atomique → pas de lock sur anime.csv pendant l'écriture
            os.replace(tmp_path, ANIME_CSV)

            taille = os.path.getsize(ANIME_CSV) / 1024
            log.info(f"✅ anime.csv écrit : {len(df)} lignes ({taille:.1f} KB)")
            return

        except OSError as e:
            # Nettoyage du fichier temporaire si créé
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

            if e.errno == 35 and tentative < max_tries:
                log.warning(
                    f"⚠️  Lock fichier macOS/Docker (tentative {tentative}/{max_tries})"
                    f" — retry dans 1s"
                )
                time.sleep(1)
            else:
                raise


# ══════════════════════════════════════════════════════════════════════════════
# TÂCHE 4 — VALIDER LE CSV ET ÉCRIRE LES MÉTRIQUES
# ══════════════════════════════════════════════════════════════════════════════

def valider_et_ecrire_metadata(**kwargs) -> str:
    """
    Vérifie que le CSV produit est lisible et contient les colonnes minimales.
    Écrit les métriques de ce run dans pipeline_metadata.json
    (lu ensuite par DAG 3 pour générer le rapport).
    """
    import pandas as pd

    log = logging.getLogger(__name__)
    ti  = kwargs["ti"]

    if not os.path.exists(ANIME_CSV):
        raise FileNotFoundError(f"❌ anime.csv introuvable après conversion : {ANIME_CSV}")

    df = pd.read_csv(ANIME_CSV)
    log.info(f"✅ CSV validé : {len(df)} lignes × {len(df.columns)} colonnes")

    # Colonnes minimales attendues par DAG 2
    COLONNES_MIN = ["MAL_ID", "Name", "Score", "Members"]
    manquantes = [c for c in COLONNES_MIN if c not in df.columns]
    if manquantes:
        raise ValueError(
            f"❌ Colonnes manquantes après conversion : {manquantes}\n"
            f"   Colonnes présentes : {list(df.columns)}"
        )

    nb_nan   = int(df.isnull().sum().sum())
    taux_nan = nb_nan / (len(df) * len(df.columns))

    fichier_source = ti.xcom_pull(task_ids="scanner_dossier", key="fichier_source")
    format_source  = ti.xcom_pull(task_ids="scanner_dossier", key="format_source")
    nb_lignes      = ti.xcom_pull(task_ids=f"convertir_{format_source}", key="nb_lignes_converties")

    log.info(f"   NaN total    : {nb_nan:,} ({taux_nan:.1%})")
    log.info(f"   Score moyen  : {df['Score'].mean():.2f}" if "Score" in df.columns else "")

    # ── Écriture metadata partagée ────────────────────────────────────────────
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    metadata = {
        "dag1": {
            "timestamp":      datetime.now().isoformat(),
            "fichier_source": os.path.basename(fichier_source) if fichier_source else "?",
            "format_source":  (format_source or "?").upper(),
            "nb_lignes":      nb_lignes or len(df),
            "nb_colonnes":    len(df.columns),
            "nb_nan":         nb_nan,
            "taux_nan":       round(taux_nan, 4),
            "statut":         "✅ succès",
        },
        "dag2": {},  # sera rempli par DAG 2
        "dag3": {},  # sera rempli par DAG 3
    }

    with open(METADATA, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    log.info(f"✅ Métadonnées écrites : {METADATA}")

    return (
        f"validation_ok | {len(df)} lignes | "
        f"{manquantes or 'colonnes OK'} | format={format_source.upper()}"
    )


# ══════════════════════════════════════════════════════════════════════════════
# TÂCHE 5 — NETTOYER LE DOSSIER INPUT (archivage)
# ══════════════════════════════════════════════════════════════════════════════

def nettoyer_input(**kwargs) -> str:
    """
    Déplace le fichier source traité vers data/input/archive/
    avec un suffixe horodaté, pour vider input/ avant le prochain run.

    Exemple : anime_3.xml → archive/anime_3_20260326-1307.xml
    """
    import shutil

    log = logging.getLogger(__name__)
    ti  = kwargs["ti"]

    fichier_source = ti.xcom_pull(task_ids="scanner_dossier", key="fichier_source")

    if not fichier_source or not os.path.exists(fichier_source):
        log.warning(f"⚠️  Fichier source introuvable pour archivage : {fichier_source}")
        return "nettoyage_skip | fichier source absent"

    os.makedirs(ARCHIVE_DIR, exist_ok=True)

    # Construit le nom archivé : nom_YYYYMMDD-HHMM.ext
    nom      = os.path.splitext(os.path.basename(fichier_source))[0]
    ext      = os.path.splitext(fichier_source)[1]
    ts       = datetime.now().strftime("%Y%m%d-%H%M")
    nom_arch = f"{nom}_{ts}{ext}"
    dest     = os.path.join(ARCHIVE_DIR, nom_arch)

    shutil.move(fichier_source, dest)
    log.info(f"📦 Fichier archivé : {os.path.basename(fichier_source)} → archive/{nom_arch}")

    # Vérifie qu'il ne reste plus de .json/.xml dans input/
    restants = [
        f for f in os.listdir(INPUT_DIR)
        if os.path.splitext(f)[1].lower() in (".json", ".xml")
    ]
    if restants:
        log.warning(f"⚠️  Autres fichiers restants dans input/ : {restants}")
    else:
        log.info(f"✅ Dossier input/ vide — prêt pour le prochain run")

    return f"nettoyage_ok | archivé → archive/{nom_arch}"


# ══════════════════════════════════════════════════════════════════════════════
# DAG
# ══════════════════════════════════════════════════════════════════════════════

with DAG(
    dag_id="00_ingestion_conversion",
    description="🎌 DAG 1 — Détecte le format (JSON/XML) et convertit en CSV pour DAG 2",
    default_args=default_args,
    schedule_interval=None,   # déclenché manuellement ou par un scheduler externe
    start_date=datetime(2026, 3, 25),
    catchup=False,
    tags=["anidata", "ingestion", "conversion"],
) as dag:

    t_scanner = PythonOperator(
        task_id="scanner_dossier",
        python_callable=scanner_dossier,
        doc_md="**Tâche 1** — Scanne data/input/ et détecte le fichier source",
    )

    t_branche = BranchPythonOperator(
        task_id="detecter_format",
        python_callable=detecter_format,
        doc_md="**Tâche 2** — Branche vers convertir_json ou convertir_xml",
    )

    t_json = PythonOperator(
        task_id="convertir_json",
        python_callable=convertir_json,
        doc_md="**Tâche 3a** — Lit le JSON et écrit anime.csv normalisé",
    )

    t_xml = PythonOperator(
        task_id="convertir_xml",
        python_callable=convertir_xml,
        doc_md="**Tâche 3b** — Lit le XML et écrit anime.csv normalisé",
    )

    t_valider = PythonOperator(
        task_id="valider_et_ecrire_metadata",
        python_callable=valider_et_ecrire_metadata,
        trigger_rule="none_failed_min_one_success",  # ← attend json OU xml
        doc_md="**Tâche 4** — Valide le CSV produit et écrit pipeline_metadata.json",
    )

    t_nettoyer = PythonOperator(
        task_id="nettoyer_input",
        python_callable=nettoyer_input,
        doc_md="**Tâche 5** — Archive le fichier source dans data/input/archive/ et vide input/",
    )

    t_trigger = TriggerDagRunOperator(
        task_id="declencher_dag2",
        trigger_dag_id="01_pipeline_anidata",
        wait_for_completion=False,
        doc_md="**Tâche 6** — Déclenche DAG 2 (pipeline audit/nettoyage)",
    )

    # ── Flux ─────────────────────────────────────────────────────────────────
    #
    #   scanner_dossier
    #        │
    #   detecter_format ──┬── convertir_json
    #                     └── convertir_xml
    #                              │ (none_failed_min_one_success)
    #                     valider_et_ecrire_metadata
    #                              │
    #                     nettoyer_input        ← archive le fichier source
    #                              │
    #                     declencher_dag2
    #
    t_scanner >> t_branche >> [t_json, t_xml] >> t_valider >> t_nettoyer >> t_trigger
