"""
🎌 AniData Lab — Pipeline Airflow
==================================
DAG : Audit → Nettoyage → Feature Engineering → Validation & Export

Chaque tâche :
  - Logue ses résultats via le logger Airflow
  - Pousse un résumé via XCom
  - Déclenche on_failure_callback en cas d'échec
    → écrit dans logs/pipeline/echecs_pipeline.log

Déclenchement : tous les jours à 6h00 (ou manuel)
Auteur        : anidata-lab
"""

import os
import json
import logging
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator


# ══════════════════════════════════════════════════════════════════════════════
# CHEMINS (relatifs aux volumes Docker)
# ══════════════════════════════════════════════════════════════════════════════

DATA_DIR   = "/opt/airflow/data"          # → ./data/
OUTPUT_DIR = "/opt/airflow/data/output"   # → ./data/output/  (persisté ✅)
LOG_DIR    = "/opt/airflow/logs/pipeline" # → ./airflow/logs/pipeline/

ANIME_CSV      = os.path.join(DATA_DIR,   "anime.csv")
RATING_CSV     = os.path.join(DATA_DIR,   "rating_complete.csv")
SYNOPSIS_CSV   = os.path.join(DATA_DIR,   "anime_with_synopsis.csv")

CLEANED_CSV    = os.path.join(OUTPUT_DIR, "anime_cleaned.csv")
GOLD_CSV       = os.path.join(OUTPUT_DIR, "anime_gold.csv")
VALIDATED_CSV  = os.path.join(OUTPUT_DIR, "anime_gold_validated.csv")
VALIDATED_JSON = os.path.join(OUTPUT_DIR, "anime_gold.json")
RAPPORT_TXT    = os.path.join(OUTPUT_DIR, "rapport_validation.txt")
AUDIT_JSON     = os.path.join(OUTPUT_DIR, "rapport_audit.json")

PIPELINE_LOG   = os.path.join(LOG_DIR,    "echecs_pipeline.log")
METADATA       = os.path.join(OUTPUT_DIR, "pipeline_metadata.json")


# ══════════════════════════════════════════════════════════════════════════════
# ON FAILURE CALLBACK
# ══════════════════════════════════════════════════════════════════════════════

def on_failure_callback(context: dict) -> None:
    """
    Appelé automatiquement par Airflow à chaque échec de tâche.
    Écrit un rapport structuré dans logs/pipeline/echecs_pipeline.log
    ET dans les logs Airflow natifs (visible dans l'UI).
    """
    task_id   = context["task_instance"].task_id
    dag_id    = context["task_instance"].dag_id
    run_id    = context.get("run_id", "inconnu")
    exec_date = context.get("execution_date", "?")
    exception = context.get("exception", "Erreur inconnue")
    ts        = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    msg = (
        f"\n{'═' * 60}\n"
        f"[ÉCHEC] {ts}\n"
        f"  DAG        : {dag_id}\n"
        f"  Tâche      : {task_id}\n"
        f"  Run ID     : {run_id}\n"
        f"  Exec date  : {exec_date}\n"
        f"  Erreur     : {exception}\n"
        f"{'═' * 60}\n"
    )

    # 1. Log Airflow (visible dans l'UI → onglet Logs de la tâche)
    logging.error(msg)

    # 2. Log fichier persistant (accessible hors container)
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        with open(PIPELINE_LOG, "a", encoding="utf-8") as f:
            f.write(msg)
    except Exception as write_err:
        logging.warning(f"⚠️  Impossible d'écrire dans {PIPELINE_LOG} : {write_err}")


# ══════════════════════════════════════════════════════════════════════════════
# DEFAULT ARGS
# ══════════════════════════════════════════════════════════════════════════════

default_args = {
    "owner": "anidata-lab",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=3),
    "on_failure_callback": on_failure_callback,  # ← appliqué à toutes les tâches
}


# ══════════════════════════════════════════════════════════════════════════════
# TÂCHE 1 — AUDIT COMPLET
# ══════════════════════════════════════════════════════════════════════════════

def audit_complet(**kwargs) -> str:
    """
    Vérifie la présence des fichiers CSV et produit un rapport d'audit :
      - Nombre de lignes / colonnes
      - Doublons
      - Valeurs manquantes (NaN classiques + valeurs déguisées)
    Sauvegarde le rapport dans output/rapport_audit.json
    Pousse nb_lignes_brut via XCom pour la tâche suivante.
    """
    import pandas as pd

    log = logging.getLogger(__name__)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # ── Vérification des fichiers sources ──────────────────────────────────
    sources = {
        "anime.csv":               ANIME_CSV,
        "rating_complete.csv":     RATING_CSV,
        "anime_with_synopsis.csv": SYNOPSIS_CSV,
    }
    for nom, chemin in sources.items():
        if not os.path.exists(chemin):
            raise FileNotFoundError(
                f"❌ Fichier source manquant : {chemin}\n"
                f"   Téléchargez-le depuis Kaggle et placez-le dans ./data/"
            )
        taille_mb = os.path.getsize(chemin) / (1024 ** 2)
        log.info(f"✅ {nom} trouvé ({taille_mb:.1f} MB)")

    # ── Audit principal : anime.csv ─────────────────────────────────────────
    df = pd.read_csv(ANIME_CSV)

    nb_doublons  = int(df.duplicated().sum())
    nb_nan       = int(df.isnull().sum().sum())
    nb_deguises  = int((df == "Unknown").sum().sum() + (df == -1).sum().sum())

    nan_par_col = (
        df.isnull().sum()[df.isnull().sum() > 0]
        .sort_values(ascending=False)
        .to_dict()
    )

    rapport = {
        "timestamp":       datetime.now().isoformat(),
        "fichier":         "anime.csv",
        "nb_lignes":       len(df),
        "nb_colonnes":     len(df.columns),
        "nb_doublons":     nb_doublons,
        "nb_nan_total":    nb_nan,
        "nb_deguises":     nb_deguises,
        "nan_par_colonne": nan_par_col,
        "colonnes":        list(df.columns),
    }

    log.info(f"📊 anime.csv : {rapport['nb_lignes']:,} lignes × {rapport['nb_colonnes']} colonnes")
    log.info(f"   Doublons          : {nb_doublons:,}")
    log.info(f"   NaN totaux        : {nb_nan:,}")
    log.info(f"   Valeurs déguisées : {nb_deguises:,}")
    if nan_par_col:
        log.info("   NaN par colonne :")
        for col, n in list(nan_par_col.items())[:10]:
            log.info(f"     {col:30s} {n:>7,}")

    # ── Sauvegarde rapport ──────────────────────────────────────────────────
    with open(AUDIT_JSON, "w", encoding="utf-8") as f:
        json.dump(rapport, f, indent=2, ensure_ascii=False)
    log.info(f"✅ Rapport d'audit sauvegardé : {AUDIT_JSON}")

    # ── XCom ────────────────────────────────────────────────────────────────
    kwargs["ti"].xcom_push(key="nb_lignes_brut", value=rapport["nb_lignes"])

    return (
        f"audit_ok | {rapport['nb_lignes']:,} lignes | "
        f"{nb_doublons} doublons | {nb_nan:,} NaN | {nb_deguises:,} déguisées"
    )


# ══════════════════════════════════════════════════════════════════════════════
# TÂCHE 2 — NETTOYAGE
# ══════════════════════════════════════════════════════════════════════════════

def nettoyage(**kwargs) -> str:
    """
    Nettoie anime.csv :
      - Suppression des doublons (sur anime_id)
      - Remplacement des valeurs déguisées (Unknown, -1) par NaN
      - Correction des types numériques (rating, members, episodes)
      - Neutralisation des outliers rating hors [0, 10]
      - Strip whitespace sur les colonnes texte
    Exporte output/anime_cleaned.csv
    """
    import pandas as pd
    import numpy as np

    log = logging.getLogger(__name__)

    if not os.path.exists(ANIME_CSV):
        raise FileNotFoundError(f"❌ Fichier source manquant : {ANIME_CSV}")

    df = pd.read_csv(ANIME_CSV)
    n_initial = len(df)
    log.info(f"📂 Dataset chargé : {n_initial:,} lignes × {len(df.columns)} colonnes")

    # ── 1. Doublons ─────────────────────────────────────────────────────────
    subset_dup = ["MAL_ID"] if "MAL_ID" in df.columns else None
    n_avant = len(df)
    df = df.drop_duplicates(subset=subset_dup)
    n_suppr = n_avant - len(df)
    log.info(f"   Doublons supprimés : {n_suppr}")

    # ── 2. Valeurs déguisées → NaN ───────────────────────────────────────────
    n_deguises = int((df == "Unknown").sum().sum() + (df == -1).sum().sum())
    df.replace("Unknown", np.nan, inplace=True)
    df.replace(-1, np.nan, inplace=True)
    log.info(f"   Valeurs déguisées remplacées : {n_deguises}")

    # ── 3. Correction des types ───────────────────────────────────────────────
    for col in ["Score", "Members", "Episodes"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    log.info("   Types numériques corrigés : Score, Members, Episodes")

    # ── 4. Outliers Score ─────────────────────────────────────────────────────
    if "Score" in df.columns:
        mask = (df["Score"] < 0) | (df["Score"] > 10)
        n_out = int(mask.sum())
        df.loc[mask, "Score"] = np.nan
        log.info(f"   Outliers Score neutralisés : {n_out}")

    # ── 5. Strip whitespace ───────────────────────────────────────────────────
    str_cols = df.select_dtypes(include="object").columns
    for col in str_cols:
        df[col] = df[col].str.strip()
    log.info(f"   Strip whitespace sur {len(str_cols)} colonnes texte")

    # ── Rapport ───────────────────────────────────────────────────────────────
    n_final      = len(df)
    nan_restants = int(df.isnull().sum().sum())
    log.info(f"✅ Nettoyage terminé : {n_initial:,} → {n_final:,} lignes")
    log.info(f"   NaN restants : {nan_restants:,}")

    # ── Export ────────────────────────────────────────────────────────────────
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    df.to_csv(CLEANED_CSV, index=False, encoding="utf-8")
    taille = os.path.getsize(CLEANED_CSV) / (1024 ** 2)
    log.info(f"✅ anime_cleaned.csv exporté ({taille:.1f} MB)")

    # ── XCom ──────────────────────────────────────────────────────────────────
    kwargs["ti"].xcom_push(key="nb_lignes_nettoyees", value=n_final)

    return (
        f"nettoyage_ok | {n_initial:,} → {n_final:,} lignes | "
        f"{nan_restants:,} NaN restants"
    )


# ══════════════════════════════════════════════════════════════════════════════
# TÂCHE 3 — FEATURE ENGINEERING
# ══════════════════════════════════════════════════════════════════════════════

def feature_engineering(**kwargs) -> str:
    """
    Crée de nouvelles features métier depuis anime_cleaned.csv :
      - score_popularite  : Bayesian average (pondération membres × rating)
      - annee_diffusion   : extraction depuis la colonne 'aired'
      - decennie          : regroupement par décennie
      - categorie_score   : mauvais / moyen / bon / excellent
      - nb_genres         : nombre de genres par anime
      - genre_principal   : premier genre listé
    Exporte output/anime_gold.csv
    """
    import pandas as pd
    import numpy as np

    log = logging.getLogger(__name__)

    if not os.path.exists(CLEANED_CSV):
        raise FileNotFoundError(
            f"❌ Fichier source manquant : {CLEANED_CSV}\n"
            f"   Assurez-vous que la tâche 'nettoyage' s'est bien exécutée."
        )

    df = pd.read_csv(CLEANED_CSV)
    n_cols_avant = len(df.columns)
    log.info(f"📂 Dataset nettoyé chargé : {len(df):,} lignes × {n_cols_avant} colonnes")

    # ── 1. Score de popularité pondéré (Bayesian average) ─────────────────
    if "Score" in df.columns and "Members" in df.columns:
        m = df["Members"].quantile(0.8)   # seuil vote minimum (percentile 80)
        C = df["Score"].mean()            # score moyen global
        df["score_popularite"] = (
            (df["Members"] / (df["Members"] + m)) * df["Score"]
            + (m / (df["Members"] + m)) * C
        ).round(3)
        log.info(f"   ✅ score_popularite — moyenne globale : {C:.2f}")

    # ── 2. Année et décennie de diffusion ──────────────────────────────────
    if "Aired" in df.columns:
        df["annee_diffusion"] = pd.to_numeric(
            df["Aired"].str.extract(r"(\d{4})")[0], errors="coerce"
        )
        df["decennie"] = (df["annee_diffusion"] // 10 * 10).astype("Int64")
        log.info("   ✅ annee_diffusion + decennie calculées")

    # ── 3. Catégorie de score ──────────────────────────────────────────────
    if "Score" in df.columns:
        bins   = [0, 5.0, 6.5, 7.5, 10.1]
        labels = ["mauvais", "moyen", "bon", "excellent"]
        df["categorie_score"] = pd.cut(
            df["Score"], bins=bins, labels=labels, right=False
        )
        dist = df["categorie_score"].value_counts().to_dict()
        log.info(f"   ✅ categorie_score : {dist}")

    # ── 4. Nombre de genres + genre principal ─────────────────────────────
    if "Genres" in df.columns:
        df["nb_genres"] = df["Genres"].fillna("").apply(
            lambda x: len([g for g in x.split(",") if g.strip()])
        )
        df["genre_principal"] = df["Genres"].fillna("").apply(
            lambda x: x.split(",")[0].strip() if x.strip() else "Inconnu"
        )
        log.info(f"   ✅ nb_genres (moy: {df['nb_genres'].mean():.1f}) + genre_principal")

    # ── Résumé ──────────────────────────────────────────────────────────────
    n_nouvelles = len(df.columns) - n_cols_avant
    log.info(f"✅ Feature engineering : +{n_nouvelles} nouvelles colonnes")

    # ── Export ───────────────────────────────────────────────────────────────
    df.to_csv(GOLD_CSV, index=False, encoding="utf-8")
    taille = os.path.getsize(GOLD_CSV) / (1024 ** 2)
    log.info(f"✅ anime_gold.csv exporté ({taille:.1f} MB)")

    # ── XCom ─────────────────────────────────────────────────────────────────
    kwargs["ti"].xcom_push(key="nb_colonnes_gold", value=len(df.columns))

    return (
        f"feature_engineering_ok | {len(df):,} lignes × {len(df.columns)} colonnes "
        f"| +{n_nouvelles} features"
    )


# ══════════════════════════════════════════════════════════════════════════════
# TÂCHE 4 — VALIDATION & EXPORT
# ══════════════════════════════════════════════════════════════════════════════

def validation_export(**kwargs) -> str:
    """
    Valide le dataset gold par assertions puis exporte :
      - output/anime_gold_validated.csv
      - output/anime_gold.json
      - output/rapport_validation.txt
    Lève une ValueError si une assertion échoue (déclenchant le callback).
    """
    import pandas as pd

    log = logging.getLogger(__name__)

    if not os.path.exists(GOLD_CSV):
        raise FileNotFoundError(
            f"❌ Fichier source manquant : {GOLD_CSV}\n"
            f"   Assurez-vous que la tâche 'feature_engineering' s'est bien exécutée."
        )

    df = pd.read_csv(GOLD_CSV)
    log.info(f"📂 Dataset gold chargé : {len(df):,} lignes × {len(df.columns)} colonnes")

    erreurs  = []
    warnings = []

    # ── ASSERTIONS ────────────────────────────────────────────────────────────

    # 1. Colonnes obligatoires
    # Members absent du scraper (mock-site ne fournit pas ce champ)
    COLONNES_REQUISES = ["MAL_ID", "Name", "Score"]
    for col in COLONNES_REQUISES:
        if col not in df.columns:
            erreurs.append(f"Colonne obligatoire manquante : '{col}'")
        else:
            log.info(f"   ✅ Colonne '{col}' présente")

    # 2. Pas de doublons sur MAL_ID
    if "MAL_ID" in df.columns:
        n_dup = int(df.duplicated(subset=["MAL_ID"]).sum())
        if n_dup > 0:
            erreurs.append(f"{n_dup} doublons détectés sur MAL_ID")
        else:
            log.info("   ✅ Aucun doublon sur MAL_ID")

    # 3. Score dans [0, 10]
    if "Score" in df.columns:
        hors_range = int(((df["Score"] < 0) | (df["Score"] > 10)).sum())
        if hors_range > 0:
            erreurs.append(f"{hors_range} scores hors de [0, 10]")
        else:
            log.info("   ✅ Tous les scores dans [0, 10]")

    # 4. Members >= 0
    if "Members" in df.columns:
        negatifs = int((df["Members"] < 0).sum())
        if negatifs > 0:
            erreurs.append(f"{negatifs} valeurs Members négatives")
        else:
            log.info("   ✅ Tous les Members >= 0")

    # 5. Taux de remplissage Score >= 50 %
    if "Score" in df.columns:
        taux = df["Score"].notna().mean()
        if taux < 0.50:
            erreurs.append(f"Taux remplissage Score trop bas : {taux:.1%} (min 50%)")
        else:
            log.info(f"   ✅ Taux remplissage Score : {taux:.1%}")

    # 6. Avertissements (non bloquants)
    if "score_popularite" not in df.columns:
        warnings.append("Colonne 'score_popularite' absente (feature engineering incomplet ?)")
    if "genre_principal" not in df.columns:
        warnings.append("Colonne 'genre_principal' absente")

    for w in warnings:
        log.warning(f"   ⚠️  {w}")

    # ── Résultat validation ───────────────────────────────────────────────────
    if erreurs:
        detail = "\n  - ".join(erreurs)
        raise ValueError(
            f"❌ Validation échouée — {len(erreurs)} erreur(s) :\n  - {detail}"
        )

    log.info(f"✅ Validation réussie — 0 erreur, {len(warnings)} avertissement(s)")

    # ── Export CSV ────────────────────────────────────────────────────────────
    df.to_csv(VALIDATED_CSV, index=False, encoding="utf-8")
    taille_csv = os.path.getsize(VALIDATED_CSV) / (1024 ** 2)
    log.info(f"✅ anime_gold_validated.csv exporté ({taille_csv:.1f} MB)")

    # ── Export JSON ───────────────────────────────────────────────────────────
    df.to_json(VALIDATED_JSON, orient="records", force_ascii=False, indent=2)
    taille_json = os.path.getsize(VALIDATED_JSON) / (1024 ** 2)
    log.info(f"✅ anime_gold.json exporté ({taille_json:.1f} MB)")

    # ── Rapport texte ─────────────────────────────────────────────────────────
    taux_rating = df["Score"].notna().mean() if "Score" in df.columns else 0
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    rapport_txt = "\n".join([
        f"RAPPORT DE VALIDATION — {ts}",
        "=" * 55,
        f"Source        : {GOLD_CSV}",
        f"Lignes        : {len(df):,}",
        f"Colonnes      : {len(df.columns)}",
        f"Taux rating   : {taux_rating:.1%}",
        f"Avertissements: {len(warnings)}",
        "",
        "Fichiers exportés :",
        f"  CSV    → {VALIDATED_CSV} ({taille_csv:.1f} MB)",
        f"  JSON   → {VALIDATED_JSON} ({taille_json:.1f} MB)",
        "",
        "Résultat      : ✅ VALIDATION RÉUSSIE",
        "=" * 55,
    ])

    with open(RAPPORT_TXT, "w", encoding="utf-8") as f:
        f.write(rapport_txt)
    log.info(f"✅ Rapport de validation sauvegardé : {RAPPORT_TXT}")

    # ── XCom ──────────────────────────────────────────────────────────────────
    kwargs["ti"].xcom_push(key="nb_lignes_validees", value=len(df))

    # ── Mise à jour metadata partagée (lue par DAG 3) ─────────────────────────
    try:
        meta = {}
        if os.path.exists(METADATA):
            with open(METADATA, "r", encoding="utf-8") as f:
                meta = json.load(f)
        meta["dag2"] = {
            "timestamp":       datetime.now().isoformat(),
            "nb_lignes":       len(df),
            "nb_colonnes":     len(df.columns),
            "taux_score":      round(df["Score"].notna().mean(), 4) if "Score" in df.columns else 0,
            "nb_warnings":     len(warnings),
            "fichiers_export": ["anime_gold_validated.csv", "anime_gold.json"],
            "statut":          "✅ succès",
        }
        with open(METADATA, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)
        log.info(f"✅ Metadata DAG 2 mise à jour")
    except Exception as e:
        log.warning(f"⚠️  Impossible de mettre à jour metadata : {e}")

    return (
        f"validation_ok | {len(df):,} lignes | "
        f"CSV ({taille_csv:.1f} MB) + JSON ({taille_json:.1f} MB) exportés"
    )


# ══════════════════════════════════════════════════════════════════════════════
# DAG
# ══════════════════════════════════════════════════════════════════════════════

with DAG(
    dag_id="01_pipeline_anidata",
    description="🎌 Pipeline complet : Audit → Nettoyage → Feature Engineering → Validation",
    default_args=default_args,
    schedule_interval=None,  # Déclenché uniquement par DAG 1 (00_ingestion_conversion)
    start_date=datetime(2026, 3, 25),
    catchup=False,
    tags=["anidata", "audit", "nettoyage", "ml-prep"],
) as dag:

    t_audit = PythonOperator(
        task_id="audit_complet",
        python_callable=audit_complet,
        doc_md="**Tâche 1** — Vérifie les fichiers CSV et produit rapport_audit.json",
    )

    t_nettoyage = PythonOperator(
        task_id="nettoyage",
        python_callable=nettoyage,
        doc_md="**Tâche 2** — Nettoie anime.csv → anime_cleaned.csv",
    )

    t_features = PythonOperator(
        task_id="feature_engineering",
        python_callable=feature_engineering,
        doc_md="**Tâche 3** — Crée les features métier → anime_gold.csv",
    )

    t_validation = PythonOperator(
        task_id="validation_export",
        python_callable=validation_export,
        doc_md="**Tâche 4** — Valide le gold et exporte CSV + JSON",
    )

    t_trigger_dag4 = TriggerDagRunOperator(
        task_id="declencher_dag4",
        trigger_dag_id="03_elasticsearch_grafana",
        wait_for_completion=False,
        doc_md="**Tâche 5** — Déclenche DAG 4 (Elasticsearch + Grafana)",
    )

    # ── Pipeline séquentiel ──────────────────────────────────────────────────
    t_audit >> t_nettoyage >> t_features >> t_validation >> t_trigger_dag4
