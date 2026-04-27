"""
🎌 AniData Lab — Nettoyage du dataset anime.csv
=================================================
Séance 2 — Mardi 24 mars 2026 — Matin (Partie 1/3)

Ce script applique toutes les corrections identifiées lors de l'audit :
  - Traitement des valeurs manquantes (classiques et déguisées)
  - Suppression des doublons
  - Correction des types de données
  - Normalisation des encodages et formats
  - Nettoyage des colonnes multi-valuées (genres, studios...)

Usage : python 03_nettoyage.py
Entrée : data/anime.csv
Sortie : output/anime_cleaned.csv
"""

import pandas as pd
import numpy as np
import os
import sys

# ============================================
# CONFIG
# ============================================
DATA_DIR = "data"
OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

INPUT_FILE = os.path.join(DATA_DIR, "anime.csv")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "anime_cleaned.csv")

# Couleurs terminal
class C:
    H = "\033[95m"; B = "\033[94m"; G = "\033[92m"
    W = "\033[93m"; F = "\033[91m"; BOLD = "\033[1m"; END = "\033[0m"

def titre(t):
    print(f"\n{C.BOLD}{C.H}{'='*60}\n  {t}\n{'='*60}{C.END}\n")

def step(t):
    print(f"\n{C.BOLD}{C.B}--- {t} ---{C.END}")

def ok(t):
    print(f"  {C.G}✅ {t}{C.END}")

def warn(t):
    print(f"  {C.W}⚠️  {t}{C.END}")

def info(t):
    print(f"  {C.B}ℹ️  {t}{C.END}")

def delta(before, after, label):
    diff = before - after
    print(f"  {C.G}✅ {label} : {before:,} → {after:,} ({diff:,} retirées, -{diff/before*100:.1f}%){C.END}")


# ============================================
# CHARGEMENT
# ============================================
titre("NETTOYAGE — anime.csv")

if not os.path.exists(INPUT_FILE):
    print(f"{C.F}❌ Fichier introuvable : {INPUT_FILE}{C.END}")
    sys.exit(1)

print("  Chargement du fichier brut...")
df_raw = pd.read_csv(INPUT_FILE)
ok(f"Fichier chargé : {df_raw.shape[0]:,} lignes × {df_raw.shape[1]} colonnes")

# Copie de travail (on ne touche jamais au raw)
df = df_raw.copy()
n_initial = len(df)

print(f"\n  Colonnes : {list(df.columns)}")


# ============================================
# ÉTAPE 1 — NORMALISATION DES NOMS DE COLONNES
# ============================================
step("Étape 1 : Normalisation des noms de colonnes")

# Mettre tous les noms en snake_case minuscule
old_cols = list(df.columns)
df.columns = (
    df.columns
    .str.strip()
    .str.lower()
    .str.replace(" ", "_")
    .str.replace("-", "_")
)
new_cols = list(df.columns)

renamed = [(o, n) for o, n in zip(old_cols, new_cols) if o != n]
if renamed:
    for old, new in renamed:
        info(f"  '{old}' → '{new}'")
    ok(f"{len(renamed)} colonne(s) renommée(s)")
else:
    ok("Noms de colonnes déjà normalisés")


# ============================================
# ÉTAPE 2 — SUPPRESSION DES DOUBLONS
# ============================================
step("Étape 2 : Suppression des doublons")

n_before = len(df)

# Doublons exacts
doublons_exact = df.duplicated().sum()
if doublons_exact > 0:
    df = df.drop_duplicates()
    warn(f"{doublons_exact:,} doublons exacts supprimés")

# Doublons sur la clé primaire (mal_id ou anime_id)
id_col = None
for candidate in ["mal_id", "anime_id", "uid", "id"]:
    if candidate in df.columns:
        id_col = candidate
        break

if id_col:
    doublons_id = df[id_col].duplicated().sum()
    if doublons_id > 0:
        df = df.drop_duplicates(subset=[id_col], keep="first")
        warn(f"{doublons_id:,} doublons sur '{id_col}' supprimés (premier gardé)")
    else:
        ok(f"Clé '{id_col}' : aucun doublon")

delta(n_before, len(df), "Doublons")


# ============================================
# ÉTAPE 3 — TRAITEMENT DES NaN DÉGUISÉS
# ============================================
step("Étape 3 : Traitement des NaN déguisés")

# Valeurs textuelles suspectes → NaN
nan_values = ["Unknown", "unknown", "UNKNOWN", "N/A", "n/a", "NA",
              "None", "none", "-", ".", "", " "]

replacements = 0
for col in df.select_dtypes(include=["object"]).columns:
    mask = df[col].isin(nan_values)
    count = mask.sum()
    if count > 0:
        df.loc[mask, col] = np.nan
        replacements += count
        info(f"  '{col}' : {count:,} valeurs suspectes → NaN")

ok(f"Total : {replacements:,} valeurs textuelles remplacées par NaN")

# Score = 0 → NaN (pas assez de votes)
score_col = None
for candidate in ["score", "rating"]:
    if candidate in df.columns:
        score_col = candidate
        break

if score_col:
    # D'abord convertir en numérique
    df[score_col] = pd.to_numeric(df[score_col], errors="coerce")
    score_zeros = (df[score_col] == 0).sum()
    if score_zeros > 0:
        df.loc[df[score_col] == 0, score_col] = np.nan
        warn(f"'{score_col}' : {score_zeros:,} scores de 0 → NaN (pas assez de votes)")


# ============================================
# ÉTAPE 4 — CORRECTION DES TYPES DE DONNÉES
# ============================================
step("Étape 4 : Correction des types de données")

# Colonnes qui devraient être numériques
numeric_candidates = ["episodes", "ranked", "popularity", "members",
                      "favorites", "score", "rating", "scored_by",
                      "watching", "completed", "on_hold", "dropped",
                      "plan_to_watch", "score_10", "score_9", "score_8",
                      "score_7", "score_6", "score_5", "score_4",
                      "score_3", "score_2", "score_1"]

conversions = 0
for col in numeric_candidates:
    if col in df.columns and df[col].dtype == object:
        before_nan = df[col].isna().sum()
        df[col] = pd.to_numeric(df[col], errors="coerce")
        after_nan = df[col].isna().sum()
        new_nan = after_nan - before_nan
        if new_nan > 0:
            info(f"  '{col}' : str → numeric ({new_nan:,} valeurs non convertibles → NaN)")
        else:
            info(f"  '{col}' : str → numeric (ok)")
        conversions += 1

# Colonnes entières (episodes, members, favorites...)
int_candidates = ["episodes", "members", "favorites", "popularity",
                  "watching", "completed", "on_hold", "dropped", "plan_to_watch"]
for col in int_candidates:
    if col in df.columns:
        try:
            df[col] = df[col].astype("Int64")  # Int64 nullable (supporte NaN)
        except (ValueError, TypeError):
            pass

ok(f"{conversions} colonne(s) converties en type numérique")

# Afficher les types finaux
print("\n  Types après correction :")
for col in df.columns:
    print(f"    • {col:25s} → {str(df[col].dtype):15s}")


# ============================================
# ÉTAPE 5 — NETTOYAGE DES COLONNES TEXTUELLES
# ============================================
step("Étape 5 : Nettoyage des colonnes textuelles")

text_cols = df.select_dtypes(include=["object"]).columns.tolist()
for col in text_cols:
    # Trim (espaces en début/fin)
    df[col] = df[col].str.strip()

    # Supprimer les espaces multiples
    df[col] = df[col].str.replace(r"\s+", " ", regex=True)

ok(f"{len(text_cols)} colonnes textuelles nettoyées (trim + espaces multiples)")

# Normalisation des noms (name, english_name, japanese_name)
name_cols = [c for c in df.columns if "name" in c.lower()]
for col in name_cols:
    if col in df.columns:
        # Supprimer les guillemets parasites
        df[col] = df[col].str.replace('"', '', regex=False)
        df[col] = df[col].str.replace("'", "'", regex=False)
        info(f"  '{col}' : guillemets parasites nettoyés")


# ============================================
# ÉTAPE 6 — NETTOYAGE DES COLONNES MULTI-VALUÉES
# ============================================
step("Étape 6 : Normalisation des colonnes multi-valuées")

multi_value_cols = []
for candidate in ["genres", "genre", "producers", "licensors", "studios"]:
    if candidate in df.columns:
        multi_value_cols.append(candidate)

for col in multi_value_cols:
    # Vérifier que c'est bien multi-valué (contient des virgules)
    has_comma = df[col].dropna().str.contains(",").any()
    if has_comma:
        # Nettoyer chaque valeur dans la liste
        def clean_list(val):
            if pd.isna(val):
                return np.nan
            items = [item.strip() for item in str(val).split(",")]
            items = [item for item in items if item and item not in ["Unknown", ""]]
            return ", ".join(items) if items else np.nan

        df[col] = df[col].apply(clean_list)
        n_unique = df[col].dropna().str.split(", ").explode().nunique()
        ok(f"  '{col}' : nettoyé — {n_unique:,} valeurs uniques")
    else:
        info(f"  '{col}' : pas multi-valué")


# ============================================
# ÉTAPE 7 — NETTOYAGE DES DATES
# ============================================
step("Étape 7 : Normalisation des dates")

date_cols = [c for c in df.columns if c.lower() in ["aired", "premiered"]]
for col in date_cols:
    if col in df.columns:
        # La colonne "aired" contient souvent "Apr 1, 1998 to Apr 24, 1999"
        # On extrait juste la date de début
        if df[col].dropna().str.contains(" to ").any():
            df[col + "_start"] = df[col].str.split(" to ").str[0].str.strip()
            df[col + "_end"] = df[col].str.split(" to ").str[1].str.strip()

            # Tenter la conversion en datetime
            df[col + "_start"] = pd.to_datetime(df[col + "_start"], errors="coerce")
            df[col + "_end"] = pd.to_datetime(df[col + "_end"], errors="coerce")

            ok(f"  '{col}' → '{col}_start' + '{col}_end' (datetime)")
        else:
            df[col] = pd.to_datetime(df[col], errors="coerce")
            ok(f"  '{col}' → datetime")


# ============================================
# ÉTAPE 8 — TRAITEMENT DES VALEURS ABERRANTES
# ============================================
step("Étape 8 : Détection et marquage des outliers")

# On ne supprime PAS les outliers, on les marque
df["is_outlier"] = False

if score_col and score_col in df.columns:
    # Score hors bornes (doit être entre 1 et 10)
    mask_score = (df[score_col] < 1) | (df[score_col] > 10)
    mask_score = mask_score & df[score_col].notna()
    outliers_score = mask_score.sum()
    if outliers_score > 0:
        df.loc[mask_score, "is_outlier"] = True
        warn(f"  Score hors [1, 10] : {outliers_score:,} marqués comme outliers")

# Épisodes aberrants (> 5000 ?)
if "episodes" in df.columns:
    mask_ep = df["episodes"].notna() & (df["episodes"] > 5000)
    outliers_ep = mask_ep.sum()
    if outliers_ep > 0:
        df.loc[mask_ep, "is_outlier"] = True
        warn(f"  Episodes > 5000 : {outliers_ep:,} marqués comme outliers")

# Members = 0 (suspect)
if "members" in df.columns:
    mask_mem = df["members"].notna() & (df["members"] == 0)
    outliers_mem = mask_mem.sum()
    if outliers_mem > 0:
        df.loc[mask_mem, "is_outlier"] = True
        warn(f"  Members = 0 : {outliers_mem:,} marqués comme outliers")

total_outliers = df["is_outlier"].sum()
ok(f"Total outliers marqués : {total_outliers:,} (non supprimés, juste flaggés)")


# ============================================
# RAPPORT DE NETTOYAGE
# ============================================
titre("RAPPORT DE NETTOYAGE")

n_final = len(df)
nan_before = df_raw.isnull().sum().sum()
nan_after = df.isnull().sum().sum()

print(f"""
{C.BOLD}                          AVANT           APRÈS{C.END}
{"─"*55}
  Lignes                  {n_initial:>10,}      {n_final:>10,}
  Colonnes                {df_raw.shape[1]:>10}      {df.shape[1]:>10}
  NaN classiques          {nan_before:>10,}      {nan_after:>10,}
  Outliers marqués                        {total_outliers:>10,}
""")

print("  Valeurs manquantes restantes par colonne :")
missing = df.isnull().sum()
missing = missing[missing > 0].sort_values(ascending=False)
if len(missing) > 0:
    for col, count in missing.items():
        pct = count / len(df) * 100
        bar = "█" * int(pct / 2)
        print(f"    {col:25s} {count:>7,}  ({pct:5.1f}%) {bar}")
else:
    ok("Aucune valeur manquante !")


# ============================================
# EXPORT
# ============================================
step("Export du fichier nettoyé")

df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8")
taille = os.path.getsize(OUTPUT_FILE) / (1024 * 1024)
ok(f"Fichier exporté : {OUTPUT_FILE} ({taille:.1f} MB)")
ok(f"{df.shape[0]:,} lignes × {df.shape[1]} colonnes")

print(f"\n{C.BOLD}{C.G}✅ Nettoyage terminé !{C.END}")
print(f"{C.B}→ Prochaine étape : python 04_feature_engineering.py{C.END}\n")
