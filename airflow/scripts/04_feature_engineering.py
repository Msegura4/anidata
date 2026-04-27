"""
🎌 AniData Lab — Feature Engineering
======================================
Séance 2 — Mardi 24 mars 2026 — Matin (Partie 2/3)

Ce script crée de nouvelles features métier à partir du dataset nettoyé :
  - Score de popularité pondéré
  - Ratio d'abandon
  - Classification des studios (top / mid / indie)
  - Catégorie de score (mauvais / moyen / bon / excellent)
  - Décennie de diffusion
  - Nombre de genres par anime
  - Genre principal

Usage : python 04_feature_engineering.py
Entrée : output/anime_cleaned.csv
Sortie : output/anime_gold.csv
"""

import pandas as pd
import numpy as np
import os
import sys

# ============================================
# CONFIG
# ============================================
OUTPUT_DIR = "output"
INPUT_FILE = os.path.join(OUTPUT_DIR, "anime_cleaned.csv")
GOLD_FILE = os.path.join(OUTPUT_DIR, "anime_gold.csv")

class C:
    H = "\033[95m"; B = "\033[94m"; G = "\033[92m"
    W = "\033[93m"; F = "\033[91m"; BOLD = "\033[1m"; END = "\033[0m"

def titre(t):
    print(f"\n{C.BOLD}{C.H}{'='*60}\n  {t}\n{'='*60}{C.END}\n")

def step(t):
    print(f"\n{C.BOLD}{C.B}--- {t} ---{C.END}")

def ok(t):
    print(f"  {C.G}✅ {t}{C.END}")

def info(t):
    print(f"  {C.B}ℹ️  {t}{C.END}")

def warn(t):
    print(f"  {C.W}⚠️  {t}{C.END}")


# ============================================
# CHARGEMENT
# ============================================
titre("FEATURE ENGINEERING — Enrichissement du dataset")

if not os.path.exists(INPUT_FILE):
    print(f"{C.F}❌ Fichier introuvable : {INPUT_FILE}")
    print(f"   Lancez d'abord : python 03_nettoyage.py{C.END}")
    sys.exit(1)

print("  Chargement du dataset nettoyé...")
df = pd.read_csv(INPUT_FILE)
ok(f"Fichier chargé : {df.shape[0]:,} lignes × {df.shape[1]} colonnes")

n_cols_before = df.shape[1]


# ============================================
# FEATURE 1 — SCORE DE POPULARITÉ PONDÉRÉ
# ============================================
step("Feature 1 : Score de popularité pondéré")

info("Formule : weighted_score = score × log10(members + 1)")
info("Idée : un score de 8.5 avec 1M de membres vaut plus qu'un 8.5 avec 100 membres")

if "score" in df.columns and "members" in df.columns:
    df["score"] = pd.to_numeric(df["score"], errors="coerce")
    df["members"] = pd.to_numeric(df["members"], errors="coerce")

    df["weighted_score"] = (
        df["score"] * np.log10(df["members"].fillna(0) + 1)
    ).round(2)

    # Mettre NaN si le score original est NaN
    df.loc[df["score"].isna(), "weighted_score"] = np.nan

    top5 = df.nlargest(5, "weighted_score")[["name" if "name" in df.columns else df.columns[1], "score", "members", "weighted_score"]]
    ok("Colonne 'weighted_score' créée")
    print(f"\n  Top 5 par score pondéré :")
    print(top5.to_string(index=False))
else:
    warn("Colonnes 'score' ou 'members' introuvables — feature ignorée")


# ============================================
# FEATURE 2 — RATIO D'ABANDON
# ============================================
step("Feature 2 : Ratio d'abandon")

info("Formule : drop_ratio = dropped / (dropped + completed)")
info("Mesure la capacité d'un anime à retenir son audience")

if "dropped" in df.columns and "completed" in df.columns:
    df["dropped"] = pd.to_numeric(df["dropped"], errors="coerce")
    df["completed"] = pd.to_numeric(df["completed"], errors="coerce")

    total = df["dropped"].fillna(0) + df["completed"].fillna(0)
    df["drop_ratio"] = np.where(
        total > 0,
        (df["dropped"].fillna(0) / total).round(4),
        np.nan
    )

    # Stats
    valid = df["drop_ratio"].dropna()
    ok(f"Colonne 'drop_ratio' créée — Moyenne : {valid.mean():.2%}, Médiane : {valid.median():.2%}")

    # Top 5 animes les plus abandonnés (avec au moins 1000 interactions)
    mask = total > 1000
    if mask.sum() > 0:
        worst5 = df.loc[mask].nlargest(5, "drop_ratio")
        name_col = "name" if "name" in df.columns else df.columns[1]
        print(f"\n  Top 5 animes les plus abandonnés (>1000 viewers) :")
        for _, row in worst5.iterrows():
            print(f"    • {row.get(name_col, '?'):40s} — abandon : {row['drop_ratio']:.1%}")
else:
    warn("Colonnes 'dropped' ou 'completed' introuvables — feature ignorée")


# ============================================
# FEATURE 3 — CATÉGORIE DE SCORE
# ============================================
step("Feature 3 : Catégorie de score")

info("Discrétisation : < 5 = Mauvais, 5-6.5 = Moyen, 6.5-8 = Bon, ≥ 8 = Excellent")

if "score" in df.columns:
    df["score_category"] = pd.cut(
        df["score"],
        bins=[0, 5, 6.5, 8, 10],
        labels=["Mauvais", "Moyen", "Bon", "Excellent"],
        include_lowest=True
    )

    dist = df["score_category"].value_counts().sort_index()
    ok("Colonne 'score_category' créée")
    print(f"\n  Distribution :")
    for cat, count in dist.items():
        pct = count / dist.sum() * 100
        bar = "█" * int(pct / 2)
        print(f"    {cat:12s} : {count:>6,} ({pct:5.1f}%) {bar}")
else:
    warn("Colonne 'score' introuvable — feature ignorée")


# ============================================
# FEATURE 4 — CLASSIFICATION DES STUDIOS
# ============================================
step("Feature 4 : Classification des studios")

info("Top studio (≥50 animes), Mid (10-49), Indie (<10)")

studio_col = None
for candidate in ["studios", "studio"]:
    if candidate in df.columns:
        studio_col = candidate
        break

if studio_col:
    # Compter les productions par studio (premier studio seulement)
    df["main_studio"] = df[studio_col].str.split(", ").str[0]

    studio_counts = df["main_studio"].value_counts()

    def classify_studio(studio):
        if pd.isna(studio):
            return np.nan
        count = studio_counts.get(studio, 0)
        if count >= 50:
            return "Top"
        elif count >= 10:
            return "Mid"
        else:
            return "Indie"

    df["studio_tier"] = df["main_studio"].apply(classify_studio)

    tier_dist = df["studio_tier"].value_counts()
    ok("Colonnes 'main_studio' et 'studio_tier' créées")
    print(f"\n  Répartition :")
    for tier, count in tier_dist.items():
        print(f"    {tier:8s} : {count:>6,} animes")

    # Top 5 studios
    top_studios = studio_counts.head(5)
    print(f"\n  Top 5 studios :")
    for studio, count in top_studios.items():
        print(f"    • {studio:30s} — {count:,} productions")
else:
    warn("Colonne 'studios' introuvable — feature ignorée")


# ============================================
# FEATURE 5 — DÉCENNIE DE DIFFUSION
# ============================================
step("Feature 5 : Décennie de diffusion")

info("Extraite de la date de début de diffusion")

# Chercher une colonne de date
date_col = None
for candidate in ["aired_start", "aired", "premiered", "start_date"]:
    if candidate in df.columns:
        date_col = candidate
        break

if date_col:
    dates = pd.to_datetime(df[date_col], errors="coerce")
    df["year"] = dates.dt.year
    df["decade"] = (df["year"] // 10 * 10).astype("Int64")

    decade_dist = df["decade"].value_counts().sort_index()
    ok("Colonnes 'year' et 'decade' créées")
    print(f"\n  Animes par décennie :")
    for decade, count in decade_dist.items():
        if pd.notna(decade):
            bar = "█" * int(count / decade_dist.max() * 30)
            print(f"    {int(decade)}s : {count:>5,} {bar}")
else:
    warn("Aucune colonne de date trouvée — feature ignorée")


# ============================================
# FEATURE 6 — NOMBRE DE GENRES
# ============================================
step("Feature 6 : Nombre de genres & genre principal")

genre_col = None
for candidate in ["genres", "genre"]:
    if candidate in df.columns:
        genre_col = candidate
        break

if genre_col:
    # Nombre de genres
    df["n_genres"] = df[genre_col].str.split(", ").str.len()
    df.loc[df[genre_col].isna(), "n_genres"] = np.nan

    # Genre principal (le premier de la liste)
    df["main_genre"] = df[genre_col].str.split(", ").str[0]

    avg_genres = df["n_genres"].mean()
    ok(f"Colonnes 'n_genres' et 'main_genre' créées — Moyenne : {avg_genres:.1f} genres/anime")

    # Top genres principaux
    top_genres = df["main_genre"].value_counts().head(10)
    print(f"\n  Top 10 genres principaux :")
    for genre, count in top_genres.items():
        print(f"    • {genre:20s} — {count:>5,}")
else:
    warn("Colonne 'genres' introuvable — feature ignorée")


# ============================================
# FEATURE 7 — RATIO ENGAGEMENT (favorites / members)
# ============================================
step("Feature 7 : Ratio d'engagement (favorites / members)")

info("Formule : engagement_ratio = favorites / members")
info("Un ratio élevé = communauté très engagée, pas juste des viewers passifs")

if "favorites" in df.columns and "members" in df.columns:
    df["favorites"] = pd.to_numeric(df["favorites"], errors="coerce")

    df["engagement_ratio"] = np.where(
        df["members"].fillna(0) > 0,
        (df["favorites"].fillna(0) / df["members"]).round(4),
        np.nan
    )

    valid = df["engagement_ratio"].dropna()
    ok(f"Colonne 'engagement_ratio' créée — Moyenne : {valid.mean():.4f}")

    # Top 5 les plus engageants (avec au moins 10K members)
    mask = df["members"].fillna(0) > 10000
    if mask.sum() > 0:
        name_col = "name" if "name" in df.columns else df.columns[1]
        top_engaged = df.loc[mask].nlargest(5, "engagement_ratio")
        print(f"\n  Top 5 animes les plus engageants (>10K members) :")
        for _, row in top_engaged.iterrows():
            print(f"    • {row.get(name_col, '?'):40s} — engagement : {row['engagement_ratio']:.3f}")
else:
    warn("Colonnes 'favorites' ou 'members' introuvables — feature ignorée")


# ============================================
# FEATURE 8 — DURÉE NORMALISÉE
# ============================================
step("Feature 8 : Durée normalisée (en minutes)")

duration_col = None
for candidate in ["duration", "duration_minutes"]:
    if candidate in df.columns:
        duration_col = candidate
        break

if duration_col:
    # La colonne "duration" contient souvent "24 min per ep" ou "1 hr 30 min"
    def parse_duration(val):
        if pd.isna(val):
            return np.nan
        val = str(val).lower()
        minutes = 0
        if "hr" in val:
            try:
                hours = int(val.split("hr")[0].strip().split()[-1])
                minutes += hours * 60
            except (ValueError, IndexError):
                pass
        if "min" in val:
            try:
                mins = int(val.split("min")[0].strip().split()[-1])
                minutes += mins
            except (ValueError, IndexError):
                pass
        if "sec" in val:
            return 1  # Très court
        return minutes if minutes > 0 else np.nan

    if df[duration_col].dtype == object:
        df["duration_minutes"] = df[duration_col].apply(parse_duration)
        ok(f"Colonne 'duration_minutes' créée à partir de '{duration_col}'")
    else:
        info(f"  '{duration_col}' est déjà numérique")
else:
    info("Pas de colonne 'duration' trouvée — feature ignorée")


# ============================================
# RAPPORT D'ENRICHISSEMENT
# ============================================
titre("RAPPORT D'ENRICHISSEMENT")

n_cols_after = df.shape[1]
new_features = n_cols_after - n_cols_before

print(f"""
{C.BOLD}  Colonnes avant  : {n_cols_before}
  Colonnes après  : {n_cols_after}
  Features créées : {new_features}{C.END}
""")

print("  Nouvelles colonnes :")
new_cols = [c for c in df.columns if c not in pd.read_csv(INPUT_FILE, nrows=0).columns]
for col in new_cols:
    dtype = df[col].dtype
    non_null = df[col].notna().sum()
    pct = non_null / len(df) * 100
    print(f"    • {col:25s} ({str(dtype):15s}) — {non_null:,} valeurs ({pct:.0f}%)")


# ============================================
# EXPORT DATASET GOLD
# ============================================
step("Export du dataset GOLD")

df.to_csv(GOLD_FILE, index=False, encoding="utf-8")
taille = os.path.getsize(GOLD_FILE) / (1024 * 1024)
ok(f"Fichier exporté : {GOLD_FILE} ({taille:.1f} MB)")
ok(f"{df.shape[0]:,} lignes × {df.shape[1]} colonnes")

print(f"\n{C.BOLD}{C.G}✅ Feature engineering terminé !{C.END}")
print(f"{C.B}→ Prochaine étape : python 05_validation.py{C.END}\n")
