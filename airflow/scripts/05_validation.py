"""
🎌 AniData Lab — Validation & Export final
=============================================
Séance 2 — Mardi 24 mars 2026 — Matin (Partie 3/3)

Ce script valide le dataset gold avec des assertions
puis l'exporte en CSV et JSON (prêt pour Elasticsearch).

Usage : python 05_validation.py
Entrée : output/anime_gold.csv
Sortie : output/anime_gold_validated.csv + output/anime_gold.json
"""

import pandas as pd
import numpy as np
import json
import os
import sys

# ============================================
# CONFIG
# ============================================
OUTPUT_DIR = "output"
INPUT_FILE = os.path.join(OUTPUT_DIR, "anime_gold.csv")
VALIDATED_CSV = os.path.join(OUTPUT_DIR, "anime_gold_validated.csv")
VALIDATED_JSON = os.path.join(OUTPUT_DIR, "anime_gold.json")
REPORT_FILE = os.path.join(OUTPUT_DIR, "rapport_validation.txt")

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

def fail(t):
    print(f"  {C.F}❌ {t}{C.END}")


# ============================================
# CHARGEMENT
# ============================================
titre("VALIDATION — Dataset Gold")

if not os.path.exists(INPUT_FILE):
    print(f"{C.F}❌ Fichier introuvable : {INPUT_FILE}")
    print(f"   Lancez d'abord : python 04_feature_engineering.py{C.END}")
    sys.exit(1)

print("  Chargement du dataset gold...")
df = pd.read_csv(INPUT_FILE)
ok(f"Fichier chargé : {df.shape[0]:,} lignes × {df.shape[1]} colonnes")


# ============================================
# ASSERTIONS DE VALIDATION
# ============================================
titre("ASSERTIONS DE VALIDATION")

results = []
total_pass = 0
total_fail = 0

def assert_check(name, condition, detail=""):
    """Exécute une assertion et enregistre le résultat."""
    global total_pass, total_fail
    passed = bool(condition)
    if passed:
        ok(f"PASS — {name}")
        total_pass += 1
    else:
        fail(f"FAIL — {name}")
        if detail:
            print(f"         {detail}")
        total_fail += 1
    results.append({"assertion": name, "status": "PASS" if passed else "FAIL", "detail": detail})


# --- Assertions structurelles ---
step("1. Assertions structurelles")

assert_check(
    "Le dataset contient des données",
    len(df) > 0,
    f"Lignes : {len(df)}"
)

assert_check(
    "Au moins 10 000 animes",
    len(df) >= 10000,
    f"Lignes : {len(df):,}"
)

# --- Assertions d'unicité ---
step("2. Assertions d'unicité")

id_col = None
for candidate in ["mal_id", "anime_id", "uid", "id"]:
    if candidate in df.columns:
        id_col = candidate
        break

if id_col:
    n_duplicates = df[id_col].duplicated().sum()
    assert_check(
        f"Clé primaire '{id_col}' unique",
        n_duplicates == 0,
        f"{n_duplicates:,} doublons trouvés" if n_duplicates > 0 else ""
    )

doublons_exact = df.duplicated().sum()
assert_check(
    "Aucun doublon exact",
    doublons_exact == 0,
    f"{doublons_exact:,} doublons" if doublons_exact > 0 else ""
)

# --- Assertions de complétude ---
step("3. Assertions de complétude")

# Colonnes clés qui ne doivent pas avoir de NaN
key_cols = []
for candidate in ["mal_id", "anime_id", "name", "type"]:
    if candidate in df.columns:
        key_cols.append(candidate)

for col in key_cols:
    nan_count = df[col].isna().sum()
    assert_check(
        f"Colonne '{col}' sans NaN",
        nan_count == 0,
        f"{nan_count:,} NaN trouvés" if nan_count > 0 else ""
    )

# Taux global de NaN < 30%
total_cells = df.shape[0] * df.shape[1]
total_nan = df.isna().sum().sum()
nan_pct = total_nan / total_cells * 100
assert_check(
    f"Taux global de NaN < 30%",
    nan_pct < 30,
    f"Taux actuel : {nan_pct:.1f}%"
)

# --- Assertions de plage de valeurs ---
step("4. Assertions de plage de valeurs")

if "score" in df.columns:
    score_data = pd.to_numeric(df["score"], errors="coerce").dropna()
    assert_check(
        "Scores entre 1 et 10 (hors NaN)",
        (score_data >= 1).all() and (score_data <= 10).all(),
        f"Min: {score_data.min()}, Max: {score_data.max()}" if len(score_data) > 0 else "Pas de scores"
    )

    assert_check(
        "Aucun score = 0 (NaN déguisé nettoyé)",
        (score_data != 0).all(),
        f"{(score_data == 0).sum()} scores de 0 restants" if (score_data == 0).any() else ""
    )

if "episodes" in df.columns:
    ep_data = pd.to_numeric(df["episodes"], errors="coerce").dropna()
    assert_check(
        "Épisodes > 0 (hors NaN)",
        (ep_data > 0).all(),
        f"{(ep_data <= 0).sum()} valeurs ≤ 0" if (ep_data <= 0).any() else ""
    )

if "members" in df.columns:
    mem_data = pd.to_numeric(df["members"], errors="coerce").dropna()
    assert_check(
        "Members ≥ 0",
        (mem_data >= 0).all(),
        f"{(mem_data < 0).sum()} valeurs négatives" if (mem_data < 0).any() else ""
    )

# --- Assertions sur les features créées ---
step("5. Assertions sur les features enrichies")

if "weighted_score" in df.columns:
    ws = df["weighted_score"].dropna()
    assert_check(
        "weighted_score > 0 (hors NaN)",
        (ws > 0).all() if len(ws) > 0 else False,
        f"Min: {ws.min():.2f}" if len(ws) > 0 else "Aucune valeur"
    )

if "drop_ratio" in df.columns:
    dr = df["drop_ratio"].dropna()
    assert_check(
        "drop_ratio entre 0 et 1",
        (dr >= 0).all() and (dr <= 1).all() if len(dr) > 0 else False,
        f"Min: {dr.min():.4f}, Max: {dr.max():.4f}" if len(dr) > 0 else ""
    )

if "score_category" in df.columns:
    valid_cats = {"Mauvais", "Moyen", "Bon", "Excellent"}
    actual_cats = set(df["score_category"].dropna().unique())
    assert_check(
        "score_category dans les valeurs autorisées",
        actual_cats.issubset(valid_cats),
        f"Valeurs inattendues : {actual_cats - valid_cats}" if not actual_cats.issubset(valid_cats) else ""
    )

if "studio_tier" in df.columns:
    valid_tiers = {"Top", "Mid", "Indie"}
    actual_tiers = set(df["studio_tier"].dropna().unique())
    assert_check(
        "studio_tier dans {Top, Mid, Indie}",
        actual_tiers.issubset(valid_tiers),
        f"Valeurs inattendues : {actual_tiers - valid_tiers}" if not actual_tiers.issubset(valid_tiers) else ""
    )

if "decade" in df.columns:
    decades = pd.to_numeric(df["decade"], errors="coerce").dropna()
    assert_check(
        "Décennies cohérentes (1910-2030)",
        (decades >= 1910).all() and (decades <= 2030).all() if len(decades) > 0 else False,
        f"Min: {decades.min():.0f}, Max: {decades.max():.0f}" if len(decades) > 0 else ""
    )

# --- Assertions d'encodage ---
step("6. Assertions d'encodage")

text_cols = df.select_dtypes(include=["object"]).columns
encoding_ok = True
for col in text_cols:
    try:
        df[col].dropna().apply(lambda x: x.encode("utf-8"))
    except Exception:
        encoding_ok = False
        break

assert_check("Toutes les colonnes textuelles encodables en UTF-8", encoding_ok)


# ============================================
# RAPPORT DE SYNTHÈSE
# ============================================
titre("RAPPORT DE SYNTHÈSE")

print(f"""
{C.BOLD}  Assertions passées  : {C.G}{total_pass}{C.END}
{C.BOLD}  Assertions échouées : {C.F if total_fail > 0 else C.G}{total_fail}{C.END}
{C.BOLD}  Total               : {total_pass + total_fail}{C.END}
{C.BOLD}  Taux de réussite    : {total_pass / (total_pass + total_fail) * 100:.0f}%{C.END}
""")

# Récap du dataset final
step("Résumé du dataset gold")
print(f"""
  Lignes      : {df.shape[0]:,}
  Colonnes    : {df.shape[1]}
  NaN total   : {df.isna().sum().sum():,} ({nan_pct:.1f}%)
  Outliers    : {df['is_outlier'].sum():,} (marqués, non supprimés)
""" if "is_outlier" in df.columns else f"""
  Lignes      : {df.shape[0]:,}
  Colonnes    : {df.shape[1]}
  NaN total   : {df.isna().sum().sum():,} ({nan_pct:.1f}%)
""")


# ============================================
# EXPORT CSV VALIDÉ
# ============================================
step("Export CSV validé")

df.to_csv(VALIDATED_CSV, index=False, encoding="utf-8")
taille = os.path.getsize(VALIDATED_CSV) / (1024 * 1024)
ok(f"{VALIDATED_CSV} ({taille:.1f} MB)")


# ============================================
# EXPORT JSON POUR ELASTICSEARCH
# ============================================
step("Export JSON pour Elasticsearch")

print("  Préparation du JSON (format compatible bulk Elasticsearch)...")

# Sélectionner les colonnes les plus utiles pour Elasticsearch
json_cols = [c for c in df.columns if c not in ["is_outlier"]]
df_json = df[json_cols].copy()

# Convertir les types Int64 nullable en int standard (JSON ne supporte pas Int64)
for col in df_json.select_dtypes(include=["Int64"]).columns:
    df_json[col] = df_json[col].astype("float64")

# Export en JSON lines (un objet par ligne, format NDJSON)
records = df_json.where(df_json.notna(), None).to_dict(orient="records")

with open(VALIDATED_JSON, "w", encoding="utf-8") as f:
    for record in records:
        # Nettoyer les None
        clean = {k: v for k, v in record.items() if v is not None}
        f.write(json.dumps(clean, ensure_ascii=False) + "\n")

taille_json = os.path.getsize(VALIDATED_JSON) / (1024 * 1024)
ok(f"{VALIDATED_JSON} ({taille_json:.1f} MB) — {len(records):,} documents NDJSON")


# ============================================
# EXPORT DU RAPPORT DE VALIDATION
# ============================================
step("Export du rapport de validation")

with open(REPORT_FILE, "w", encoding="utf-8") as f:
    f.write("RAPPORT DE VALIDATION — AniData Lab\n")
    f.write(f"{'='*50}\n\n")
    f.write(f"Dataset : {INPUT_FILE}\n")
    f.write(f"Lignes  : {df.shape[0]:,}\n")
    f.write(f"Colonnes: {df.shape[1]}\n\n")
    f.write(f"Assertions passées  : {total_pass}\n")
    f.write(f"Assertions échouées : {total_fail}\n")
    f.write(f"Taux de réussite    : {total_pass / (total_pass + total_fail) * 100:.0f}%\n\n")
    f.write(f"{'─'*50}\n")
    for r in results:
        status = "✅ PASS" if r["status"] == "PASS" else "❌ FAIL"
        f.write(f"{status} — {r['assertion']}\n")
        if r["detail"]:
            f.write(f"         {r['detail']}\n")
    f.write(f"\n{'='*50}\n")
    f.write("Fichiers exportés :\n")
    f.write(f"  - {VALIDATED_CSV}\n")
    f.write(f"  - {VALIDATED_JSON}\n")

ok(f"{REPORT_FILE}")


# ============================================
# FIN
# ============================================
print(f"""
{C.BOLD}{C.H}{'='*60}
  RÉCAPITULATIF DES FICHIERS GÉNÉRÉS
{'='*60}{C.END}

  📄 {VALIDATED_CSV:45s} (dataset final CSV)
  📄 {VALIDATED_JSON:45s} (prêt pour Elasticsearch)
  📄 {REPORT_FILE:45s} (rapport de validation)

{C.BOLD}{C.G}✅ Pipeline Data Refinement terminé !{C.END}

{C.B}→ Cet après-midi : indexer anime_gold.json dans Elasticsearch
   et créer les dashboards Grafana !{C.END}
""")
