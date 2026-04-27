"""
🎌 AniData Lab — Script d'audit du dataset MyAnimeList
=======================================================
Séance 1 — Lundi 23 mars 2026 — Après-midi

Ce script réalise un audit complet des 3 fichiers CSV :
  - anime.csv (17 562 animes)
  - rating_complete.csv (57M ratings)
  - anime_with_synopsis.csv (~17 000 synopsis)

Usage : python 01_audit_complet.py
Prérequis : pip install pandas matplotlib seaborn
"""

import pandas as pd
import os
import sys

# ============================================
# CONFIGURATION
# ============================================
DATA_DIR = "data"  # Chemin vers le dossier data/

# Couleurs terminal
class C:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    BOLD = "\033[1m"
    END = "\033[0m"


def titre(text):
    """Affiche un titre de section."""
    print(f"\n{C.BOLD}{C.HEADER}{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}{C.END}\n")


def sous_titre(text):
    """Affiche un sous-titre."""
    print(f"\n{C.BOLD}{C.CYAN}--- {text} ---{C.END}")


def ok(text):
    print(f"  {C.GREEN}✅ {text}{C.END}")


def warn(text):
    print(f"  {C.WARNING}⚠️  {text}{C.END}")


def fail(text):
    print(f"  {C.FAIL}❌ {text}{C.END}")


def info(text):
    print(f"  {C.BLUE}ℹ️  {text}{C.END}")


# ============================================
# VÉRIFICATION DES FICHIERS
# ============================================
titre("1. VÉRIFICATION DES FICHIERS")

fichiers = {
    "anime.csv": "Informations générales sur les animes",
    "rating_complete.csv": "Ratings des utilisateurs (animes complétés)",
    "anime_with_synopsis.csv": "Synopsis textuels des animes",
}

fichiers_ok = True
for fichier, description in fichiers.items():
    chemin = os.path.join(DATA_DIR, fichier)
    if os.path.exists(chemin):
        taille = os.path.getsize(chemin) / (1024 * 1024)
        ok(f"{fichier} ({taille:.1f} MB) — {description}")
    else:
        fail(f"{fichier} — MANQUANT !")
        fichiers_ok = False

if not fichiers_ok:
    print(f"\n{C.FAIL}Des fichiers sont manquants !")
    print(f"Téléchargez-les depuis : https://www.kaggle.com/datasets/hernan4444/anime-recommendation-database-2020{C.END}")
    sys.exit(1)


# ============================================
# CHARGEMENT DES DONNÉES
# ============================================
titre("2. CHARGEMENT DES DONNÉES")

print("  Chargement de anime.csv...")
anime = pd.read_csv(os.path.join(DATA_DIR, "anime.csv"))
ok(f"anime.csv : {anime.shape[0]:,} lignes × {anime.shape[1]} colonnes")

print("  Chargement de anime_with_synopsis.csv...")
synopsis = pd.read_csv(os.path.join(DATA_DIR, "anime_with_synopsis.csv"))
ok(f"anime_with_synopsis.csv : {synopsis.shape[0]:,} lignes × {synopsis.shape[1]} colonnes")

# Pour rating_complete.csv, on ne charge qu'un échantillon (trop gros pour 8 Go)
print("  Chargement de rating_complete.csv (échantillon 500 000 lignes)...")
rating_sample = pd.read_csv(
    os.path.join(DATA_DIR, "rating_complete.csv"),
    nrows=500_000
)
# Compter le nombre total de lignes sans tout charger
print("  Comptage du nombre total de lignes (peut prendre 1-2 min)...")
total_ratings = sum(1 for _ in open(os.path.join(DATA_DIR, "rating_complete.csv"))) - 1
ok(f"rating_complete.csv : {total_ratings:,} lignes au total (échantillon : 500 000)")

memoire = (anime.memory_usage(deep=True).sum() +
           synopsis.memory_usage(deep=True).sum() +
           rating_sample.memory_usage(deep=True).sum()) / (1024 * 1024)
info(f"Mémoire utilisée par les DataFrames : {memoire:.1f} MB")


# ============================================
# AUDIT DE anime.csv
# ============================================
titre("3. AUDIT — anime.csv")

sous_titre("3.1 Structure et types")
print(f"\n  Colonnes ({anime.shape[1]}) :")
for col in anime.columns:
    dtype = anime[col].dtype
    print(f"    • {col:25s} → {str(dtype):10s}")

sous_titre("3.2 Valeurs manquantes")
missing = anime.isnull().sum()
missing_pct = (missing / len(anime) * 100).round(2)
missing_df = pd.DataFrame({
    "NaN": missing,
    "% NaN": missing_pct
}).sort_values("NaN", ascending=False)

print(missing_df[missing_df["NaN"] > 0].to_string())

total_nan = missing.sum()
total_cells = anime.shape[0] * anime.shape[1]
if total_nan > 0:
    warn(f"Total valeurs manquantes : {total_nan:,} / {total_cells:,} cellules ({total_nan/total_cells*100:.2f}%)")
else:
    ok("Aucune valeur manquante détectée (attention aux NaN déguisés !)")

# Détection des NaN déguisés
sous_titre("3.3 Valeurs manquantes DÉGUISÉES")
nan_deguises = {}
for col in anime.columns:
    if anime[col].dtype == object:
        suspects = anime[col].isin(["Unknown", "unknown", "N/A", "n/a", "-", "None", "none", ""]).sum()
        if suspects > 0:
            nan_deguises[col] = suspects

if nan_deguises:
    for col, count in nan_deguises.items():
        warn(f"{col} : {count:,} valeurs suspectes ('Unknown', 'N/A', '-'...)")
else:
    ok("Aucun NaN déguisé évident détecté dans les colonnes textuelles.")

# Score = 0 comme NaN déguisé
score_zero = (anime["Score"] == 0).sum() if "Score" in anime.columns else 0
if score_zero == 0:
    # Essayer avec minuscule
    for col_name in anime.columns:
        if col_name.lower() == "score":
            score_zero = (anime[col_name].astype(str).isin(["0", "0.0", "0.00"])).sum()
            break

if score_zero > 0:
    warn(f"Score = 0 : {score_zero:,} animes → Probablement des NaN déguisés (pas assez de votes)")

sous_titre("3.4 Doublons")
doublons_exact = anime.duplicated().sum()
if doublons_exact > 0:
    warn(f"{doublons_exact:,} doublons exacts détectés")
else:
    ok("Aucun doublon exact")

# Doublons sur MAL_ID ou la colonne identifiant
id_col = None
for candidate in ["MAL_ID", "mal_id", "anime_id", "uid"]:
    if candidate in anime.columns:
        id_col = candidate
        break

if id_col:
    doublons_id = anime[id_col].duplicated().sum()
    if doublons_id > 0:
        warn(f"{doublons_id:,} doublons sur la clé {id_col}")
    else:
        ok(f"Clé {id_col} : toutes les valeurs sont uniques")

sous_titre("3.5 Statistiques descriptives (colonnes numériques)")
num_cols = anime.select_dtypes(include=["int64", "float64"]).columns.tolist()
if num_cols:
    stats = anime[num_cols].describe().round(2)
    print(stats.to_string())

    # Détection des outliers basiques
    sous_titre("3.6 Valeurs aberrantes potentielles")
    for col in num_cols:
        col_data = pd.to_numeric(anime[col], errors="coerce").dropna()
        if len(col_data) > 0:
            q1 = col_data.quantile(0.25)
            q3 = col_data.quantile(0.75)
            iqr = q3 - q1
            lower = q1 - 1.5 * iqr
            upper = q3 + 1.5 * iqr
            outliers = ((col_data < lower) | (col_data > upper)).sum()
            if outliers > 0:
                warn(f"{col} : {outliers:,} outliers (hors [{lower:.1f}, {upper:.1f}])")

sous_titre("3.7 Colonnes catégorielles — valeurs uniques")
cat_cols = anime.select_dtypes(include=["object"]).columns.tolist()
for col in cat_cols:
    n_unique = anime[col].nunique()
    exemples = anime[col].dropna().unique()[:5]
    exemples_str = ", ".join([str(e)[:40] for e in exemples])
    print(f"  • {col:25s} → {n_unique:,} valeurs uniques — Ex: {exemples_str}")

sous_titre("3.8 Problèmes d'encodage potentiels")
encoding_issues = 0
for col in cat_cols:
    for val in anime[col].dropna().sample(min(100, len(anime[col].dropna()))):
        try:
            str(val).encode("ascii")
        except UnicodeEncodeError:
            encoding_issues += 1
            break

if encoding_issues > 0:
    info(f"{encoding_issues} colonne(s) contiennent des caractères non-ASCII (japonais, accents...) — normal pour ce dataset")
else:
    ok("Pas de problème d'encodage détecté")


# ============================================
# AUDIT DE anime_with_synopsis.csv
# ============================================
titre("4. AUDIT — anime_with_synopsis.csv")

sous_titre("4.1 Structure")
print(f"  {synopsis.shape[0]:,} lignes × {synopsis.shape[1]} colonnes")
print(f"  Colonnes : {list(synopsis.columns)}")

sous_titre("4.2 Valeurs manquantes")
missing_syn = synopsis.isnull().sum()
for col, count in missing_syn.items():
    if count > 0:
        warn(f"{col} : {count:,} NaN ({count/len(synopsis)*100:.1f}%)")
    else:
        ok(f"{col} : aucun NaN")

sous_titre("4.3 Longueur des synopsis")
for col in synopsis.columns:
    if synopsis[col].dtype == object:
        lengths = synopsis[col].dropna().str.len()
        if lengths.mean() > 50:  # Probablement la colonne synopsis
            print(f"  Colonne '{col}' :")
            print(f"    Longueur min    : {lengths.min():,} caractères")
            print(f"    Longueur max    : {lengths.max():,} caractères")
            print(f"    Longueur moyenne: {lengths.mean():,.0f} caractères")
            empty = (lengths < 10).sum()
            if empty > 0:
                warn(f"    {empty:,} synopsis très courts (< 10 caractères)")

sous_titre("4.4 Doublons")
doublons_syn = synopsis.duplicated().sum()
if doublons_syn > 0:
    warn(f"{doublons_syn:,} doublons exacts")
else:
    ok("Aucun doublon exact")


# ============================================
# AUDIT DE rating_complete.csv (échantillon)
# ============================================
titre("5. AUDIT — rating_complete.csv (échantillon 500K)")

sous_titre("5.1 Structure")
print(f"  Total réel : {total_ratings:,} lignes")
print(f"  Échantillon : {rating_sample.shape[0]:,} lignes × {rating_sample.shape[1]} colonnes")
print(f"  Colonnes : {list(rating_sample.columns)}")

sous_titre("5.2 Valeurs manquantes")
missing_rat = rating_sample.isnull().sum()
for col, count in missing_rat.items():
    if count > 0:
        warn(f"{col} : {count:,} NaN ({count/len(rating_sample)*100:.1f}%)")
    else:
        ok(f"{col} : aucun NaN")

sous_titre("5.3 Distribution des ratings")
for col in rating_sample.columns:
    if rating_sample[col].dtype in ["int64", "float64"]:
        col_data = rating_sample[col]
        if col_data.max() <= 10 and col_data.min() >= 0:  # Probablement le score
            print(f"  Colonne '{col}' (probable rating) :")
            print(f"    Min     : {col_data.min()}")
            print(f"    Max     : {col_data.max()}")
            print(f"    Moyenne : {col_data.mean():.2f}")
            print(f"    Médiane : {col_data.median():.1f}")
            print(f"\n  Distribution :")
            dist = col_data.value_counts().sort_index()
            for val, count in dist.items():
                bar = "█" * int(count / dist.max() * 40)
                print(f"    {val:4} : {count:>7,} {bar}")

sous_titre("5.4 Utilisateurs et animes uniques")
for col in rating_sample.columns:
    n_unique = rating_sample[col].nunique()
    print(f"  • {col:20s} → {n_unique:,} valeurs uniques")


# ============================================
# RAPPORT DE SYNTHÈSE
# ============================================
titre("6. RAPPORT DE SYNTHÈSE")

print(f"""
{C.BOLD}Fichier            Lignes          Colonnes    NaN total{C.END}
{"─"*60}
anime.csv          {anime.shape[0]:>10,}    {anime.shape[1]:>5}        {anime.isnull().sum().sum():>8,}
synopsis.csv       {synopsis.shape[0]:>10,}    {synopsis.shape[1]:>5}        {synopsis.isnull().sum().sum():>8,}
ratings.csv        {total_ratings:>10,}    {rating_sample.shape[1]:>5}        {rating_sample.isnull().sum().sum():>8,} (sur 500K)
""")

sous_titre("Problèmes identifiés à traiter")
print(f"""
  1. Valeurs manquantes classiques (NaN) dans anime.csv
  2. Valeurs manquantes DÉGUISÉES (score=0, 'Unknown' dans episodes...)
  3. Types de données incorrects (colonnes numériques stockées en texte)
  4. Caractères spéciaux dans les titres japonais/coréens
  5. Colonnes multi-valuées (genres, studios = listes dans une string)
  6. Outliers potentiels à vérifier avec la connaissance métier
""")

sous_titre("Prochaines étapes")
print(f"""
  → Mardi matin : Nettoyage + Feature Engineering (script 02_nettoyage.py)
  → Mardi après-midi : Indexation dans Elasticsearch + Grafana
  → Mercredi-Vendredi : Pipeline Airflow pour automatiser tout ça
""")

print(f"\n{C.BOLD}{C.GREEN}✅ Audit terminé avec succès !{C.END}")
print(f"{C.BLUE}Les résultats ci-dessus constituent votre rapport d'audit.{C.END}")
print(f"{C.BLUE}Copiez-collez la sortie dans un fichier texte pour le conserver.{C.END}\n")
