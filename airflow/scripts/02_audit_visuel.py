"""
🎌 AniData Lab — Audit visuel (génération de graphiques)
=========================================================
Séance 1 — Lundi 23 mars 2026 — Après-midi

Ce script génère des graphiques d'audit dans le dossier output/audit_charts/
Lancez-le APRÈS 01_audit_complet.py

Usage : python 02_audit_visuel.py
Prérequis : pip install pandas matplotlib seaborn
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use("Agg")  # Pas besoin d'affichage graphique
import seaborn as sns
import os

# ============================================
# CONFIG
# ============================================
DATA_DIR = "data"
OUTPUT_DIR = "output/audit_charts"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Style des graphiques
plt.rcParams.update({
    "figure.facecolor": "#1B2545",
    "axes.facecolor": "#232E4A",
    "axes.edgecolor": "#5B8DEF",
    "axes.labelcolor": "#C8D6E5",
    "text.color": "#C8D6E5",
    "xtick.color": "#C8D6E5",
    "ytick.color": "#C8D6E5",
    "grid.color": "#2A3558",
    "font.family": "sans-serif",
    "font.size": 11,
})
PALETTE = ["#5B8DEF", "#4ECDC4", "#E94560", "#F39C12", "#2ECC71", "#9B59B6"]

print("🎌 AniData Lab — Génération des graphiques d'audit\n")

# ============================================
# CHARGEMENT
# ============================================
print("  Chargement de anime.csv...")
anime = pd.read_csv(os.path.join(DATA_DIR, "anime.csv"))
print(f"  ✅ {anime.shape[0]:,} lignes chargées\n")

chart_num = 0

def save_chart(name):
    global chart_num
    chart_num += 1
    filepath = os.path.join(OUTPUT_DIR, f"{chart_num:02d}_{name}.png")
    plt.savefig(filepath, dpi=150, bbox_inches="tight", facecolor="#1B2545")
    plt.close()
    print(f"  📊 Graphique {chart_num} sauvegardé : {filepath}")


# ============================================
# GRAPHIQUE 1 — Valeurs manquantes par colonne
# ============================================
print("\n--- Graphique 1 : Valeurs manquantes ---")
missing = anime.isnull().sum().sort_values(ascending=True)
missing = missing[missing > 0]

if len(missing) > 0:
    fig, ax = plt.subplots(figsize=(10, max(4, len(missing) * 0.4)))
    bars = ax.barh(missing.index, missing.values, color=PALETTE[2], alpha=0.85)
    ax.set_xlabel("Nombre de valeurs manquantes")
    ax.set_title("Valeurs manquantes par colonne — anime.csv", fontsize=14, fontweight="bold", color="white")
    for bar, val in zip(bars, missing.values):
        ax.text(bar.get_width() + 50, bar.get_y() + bar.get_height()/2,
                f"{val:,}", va="center", fontsize=9, color="#C8D6E5")
    ax.grid(axis="x", alpha=0.3)
    save_chart("missing_values")
else:
    print("  ℹ️  Pas de NaN classiques — on vérifie les NaN déguisés...")


# ============================================
# GRAPHIQUE 2 — NaN déguisés (score = 0, Unknown, etc.)
# ============================================
print("\n--- Graphique 2 : NaN déguisés ---")
disguised = {}
for col in anime.columns:
    if anime[col].dtype == object:
        count = anime[col].isin(["Unknown", "unknown", "N/A", "-", "None", ""]).sum()
        if count > 0:
            disguised[col] = count

# Vérifier score = 0
for col in anime.columns:
    if col.lower() == "score":
        score_data = pd.to_numeric(anime[col], errors="coerce")
        zeros = (score_data == 0).sum()
        if zeros > 0:
            disguised[f"{col} (= 0)"] = zeros

if disguised:
    fig, ax = plt.subplots(figsize=(10, max(4, len(disguised) * 0.5)))
    bars = ax.barh(list(disguised.keys()), list(disguised.values()), color=PALETTE[3], alpha=0.85)
    ax.set_xlabel("Nombre de valeurs suspectes")
    ax.set_title("NaN déguisés (Unknown, 0, N/A...) — anime.csv", fontsize=14, fontweight="bold", color="white")
    for bar, val in zip(bars, disguised.values()):
        ax.text(bar.get_width() + 20, bar.get_y() + bar.get_height()/2,
                f"{val:,}", va="center", fontsize=9, color="#C8D6E5")
    ax.grid(axis="x", alpha=0.3)
    save_chart("disguised_nan")


# ============================================
# GRAPHIQUE 3 — Distribution des scores
# ============================================
print("\n--- Graphique 3 : Distribution des scores ---")
score_col = None
for col in anime.columns:
    if col.lower() == "score":
        score_col = col
        break

if score_col:
    scores = pd.to_numeric(anime[score_col], errors="coerce").dropna()
    scores_nonzero = scores[scores > 0]

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # Avec les 0
    axes[0].hist(scores, bins=50, color=PALETTE[0], alpha=0.85, edgecolor="#1B2545")
    axes[0].set_title("Scores AVEC les zéros", fontsize=12, fontweight="bold", color="white")
    axes[0].set_xlabel("Score")
    axes[0].set_ylabel("Nombre d'animes")
    axes[0].axvline(x=0.5, color=PALETTE[2], linestyle="--", linewidth=2, label="Score ≈ 0 = NaN ?")
    axes[0].legend(facecolor="#232E4A", edgecolor="#5B8DEF")
    axes[0].grid(alpha=0.3)

    # Sans les 0
    axes[1].hist(scores_nonzero, bins=50, color=PALETTE[4], alpha=0.85, edgecolor="#1B2545")
    axes[1].set_title("Scores SANS les zéros (nettoyé)", fontsize=12, fontweight="bold", color="white")
    axes[1].set_xlabel("Score")
    axes[1].set_ylabel("Nombre d'animes")
    axes[1].axvline(x=scores_nonzero.mean(), color=PALETTE[3], linestyle="--", linewidth=2,
                    label=f"Moyenne = {scores_nonzero.mean():.2f}")
    axes[1].legend(facecolor="#232E4A", edgecolor="#5B8DEF")
    axes[1].grid(alpha=0.3)

    plt.suptitle("Impact des NaN déguisés sur la distribution des scores", fontsize=14, fontweight="bold", color="white")
    plt.tight_layout()
    save_chart("score_distribution")


# ============================================
# GRAPHIQUE 4 — Types de données (pie chart)
# ============================================
print("\n--- Graphique 4 : Types de données ---")
type_counts = anime.dtypes.value_counts()
fig, ax = plt.subplots(figsize=(8, 5))
wedges, texts, autotexts = ax.pie(
    type_counts.values,
    labels=[str(t) for t in type_counts.index],
    autopct="%1.0f%%",
    colors=PALETTE[:len(type_counts)],
    textprops={"color": "#C8D6E5", "fontsize": 12},
    startangle=90
)
for at in autotexts:
    at.set_color("white")
    at.set_fontweight("bold")
ax.set_title("Répartition des types de colonnes — anime.csv", fontsize=14, fontweight="bold", color="white")
save_chart("data_types")


# ============================================
# GRAPHIQUE 5 — Top 15 genres
# ============================================
print("\n--- Graphique 5 : Top genres ---")
genre_col = None
for col in anime.columns:
    if col.lower() in ["genres", "genre"]:
        genre_col = col
        break

if genre_col:
    all_genres = anime[genre_col].dropna().str.split(", ").explode()
    all_genres = all_genres[~all_genres.isin(["Unknown", ""])]
    top_genres = all_genres.value_counts().head(15)

    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.barh(top_genres.index[::-1], top_genres.values[::-1], color=PALETTE[1], alpha=0.85)
    ax.set_xlabel("Nombre d'animes")
    ax.set_title("Top 15 genres — anime.csv", fontsize=14, fontweight="bold", color="white")
    for bar, val in zip(bars, top_genres.values[::-1]):
        ax.text(bar.get_width() + 30, bar.get_y() + bar.get_height()/2,
                f"{val:,}", va="center", fontsize=9, color="#C8D6E5")
    ax.grid(axis="x", alpha=0.3)
    save_chart("top_genres")


# ============================================
# GRAPHIQUE 6 — Top 15 studios
# ============================================
print("\n--- Graphique 6 : Top studios ---")
studio_col = None
for col in anime.columns:
    if col.lower() in ["studios", "studio"]:
        studio_col = col
        break

if studio_col:
    all_studios = anime[studio_col].dropna().str.split(", ").explode()
    all_studios = all_studios[~all_studios.isin(["Unknown", ""])]
    top_studios = all_studios.value_counts().head(15)

    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.barh(top_studios.index[::-1], top_studios.values[::-1], color=PALETTE[0], alpha=0.85)
    ax.set_xlabel("Nombre d'animes")
    ax.set_title("Top 15 studios — anime.csv", fontsize=14, fontweight="bold", color="white")
    for bar, val in zip(bars, top_studios.values[::-1]):
        ax.text(bar.get_width() + 10, bar.get_y() + bar.get_height()/2,
                f"{val:,}", va="center", fontsize=9, color="#C8D6E5")
    ax.grid(axis="x", alpha=0.3)
    save_chart("top_studios")


# ============================================
# GRAPHIQUE 7 — Répartition par type (TV, OVA, Movie...)
# ============================================
print("\n--- Graphique 7 : Répartition par type ---")
type_col = None
for col in anime.columns:
    if col.lower() == "type":
        type_col = col
        break

if type_col:
    type_dist = anime[type_col].value_counts()

    fig, ax = plt.subplots(figsize=(8, 5))
    wedges, texts, autotexts = ax.pie(
        type_dist.values,
        labels=type_dist.index,
        autopct="%1.1f%%",
        colors=PALETTE[:len(type_dist)],
        textprops={"color": "#C8D6E5", "fontsize": 11},
        startangle=90
    )
    for at in autotexts:
        at.set_color("white")
        at.set_fontweight("bold")
        at.set_fontsize(10)
    ax.set_title("Répartition par type — anime.csv", fontsize=14, fontweight="bold", color="white")
    save_chart("type_distribution")


# ============================================
# GRAPHIQUE 8 — Boxplots des colonnes numériques clés
# ============================================
print("\n--- Graphique 8 : Boxplots ---")
num_candidates = []
for col in anime.columns:
    if col.lower() in ["score", "members", "favorites", "episodes", "popularity", "ranked"]:
        data = pd.to_numeric(anime[col], errors="coerce").dropna()
        if len(data) > 100:
            num_candidates.append(col)

if num_candidates:
    fig, axes = plt.subplots(1, len(num_candidates), figsize=(4 * len(num_candidates), 5))
    if len(num_candidates) == 1:
        axes = [axes]

    for i, col in enumerate(num_candidates):
        data = pd.to_numeric(anime[col], errors="coerce").dropna()
        data = data[data > 0]  # Retirer les 0 suspects
        bp = axes[i].boxplot(data, patch_artist=True, vert=True,
                            boxprops=dict(facecolor=PALETTE[i % len(PALETTE)], alpha=0.7),
                            medianprops=dict(color="white", linewidth=2),
                            whiskerprops=dict(color="#C8D6E5"),
                            capprops=dict(color="#C8D6E5"),
                            flierprops=dict(marker="o", markersize=3, alpha=0.3, markerfacecolor=PALETTE[2]))
        axes[i].set_title(col, fontsize=12, fontweight="bold", color="white")
        axes[i].grid(alpha=0.3)

    plt.suptitle("Boxplots des colonnes numériques (sans les 0)", fontsize=14, fontweight="bold", color="white")
    plt.tight_layout()
    save_chart("boxplots")


# ============================================
# GRAPHIQUE 9 — Heatmap des corrélations
# ============================================
print("\n--- Graphique 9 : Corrélations ---")
num_df = anime.copy()
for col in num_df.columns:
    num_df[col] = pd.to_numeric(num_df[col], errors="coerce")
num_df = num_df.select_dtypes(include=["int64", "float64"]).dropna(axis=1, how="all")
# Garder uniquement les colonnes avec des données
num_df = num_df.loc[:, num_df.notna().sum() > len(num_df) * 0.3]

if num_df.shape[1] >= 2:
    corr = num_df.corr()
    fig, ax = plt.subplots(figsize=(max(8, num_df.shape[1] * 0.8), max(6, num_df.shape[1] * 0.6)))
    sns.heatmap(corr, annot=True, fmt=".2f", cmap="coolwarm", center=0,
                ax=ax, square=True, linewidths=0.5,
                annot_kws={"size": 8, "color": "white"},
                cbar_kws={"shrink": 0.8})
    ax.set_title("Matrice de corrélation — anime.csv", fontsize=14, fontweight="bold", color="white")
    plt.tight_layout()
    save_chart("correlation_matrix")


# ============================================
# FIN
# ============================================
print(f"\n{'='*60}")
print(f"  ✅ {chart_num} graphiques générés dans {OUTPUT_DIR}/")
print(f"  📂 Ouvrez le dossier pour examiner les résultats.")
print(f"{'='*60}\n")
