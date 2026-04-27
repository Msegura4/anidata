"""
🎌 AniData Lab — DAG 3 : Rapport HTML de run
=============================================
Rôle : générer un rapport de synthèse après chaque run complet (DAG 1 + DAG 2).

  1. Lire les métriques de pipeline_metadata.json (écrit par DAG 1 et DAG 2)
  2. Générer un rapport HTML complet (statuts, stats, erreurs détectées)
  3. Sauvegarder dans data/output/rapports/rapport_YYYY-MM-DD_HH-MM.html
  4. Si SMTP configuré dans Airflow → envoyer par email
     Sinon → log du chemin du rapport (accessible via le volume data/)

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
# CHEMINS
# ══════════════════════════════════════════════════════════════════════════════

OUTPUT_DIR   = "/opt/airflow/data/output"
RAPPORT_DIR  = "/opt/airflow/data/output/rapports"
METADATA     = "/opt/airflow/data/output/pipeline_metadata.json"
PIPELINE_LOG = "/opt/airflow/logs/pipeline/echecs_pipeline.log"
LOG_DIR      = "/opt/airflow/logs/pipeline"

# Email destinataire (modifiable sans toucher au code via Airflow Variables)
EMAIL_DESTINATAIRE = "admin@anidata.lab"


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
    "retries": 0,
    "on_failure_callback": on_failure_callback,
}


# ══════════════════════════════════════════════════════════════════════════════
# TÂCHE 1 — LIRE LES MÉTRIQUES
# ══════════════════════════════════════════════════════════════════════════════

def lire_metriques(**kwargs) -> str:
    """
    Lit pipeline_metadata.json produit par DAG 1 et DAG 2.
    Pousse les métriques via XCom pour la tâche suivante.
    """
    log = logging.getLogger(__name__)

    if not os.path.exists(METADATA):
        raise FileNotFoundError(
            f"❌ Fichier de métriques introuvable : {METADATA}\n"
            f"   Assurez-vous que DAG 1 et DAG 2 ont bien tourné."
        )

    with open(METADATA, "r", encoding="utf-8") as f:
        meta = json.load(f)

    dag1 = meta.get("dag1", {})
    dag2 = meta.get("dag2", {})

    log.info(f"📊 Métriques DAG 1 :")
    log.info(f"   Fichier source : {dag1.get('fichier_source', '?')}")
    log.info(f"   Format         : {dag1.get('format_source', '?')}")
    log.info(f"   Lignes         : {dag1.get('nb_lignes', '?')}")
    log.info(f"   Statut         : {dag1.get('statut', '?')}")

    log.info(f"📊 Métriques DAG 2 :")
    log.info(f"   Lignes validées : {dag2.get('nb_lignes', '?')}")
    log.info(f"   Taux Score      : {dag2.get('taux_score', '?')}")
    log.info(f"   Warnings        : {dag2.get('nb_warnings', '?')}")
    log.info(f"   Statut          : {dag2.get('statut', '?')}")

    # Lire le log des échecs s'il existe
    echecs = []
    if os.path.exists(PIPELINE_LOG):
        with open(PIPELINE_LOG, "r", encoding="utf-8") as f:
            contenu = f.read()
        # Ne garder que les blocs du run récent (dernier timestamp)
        blocs = [b.strip() for b in contenu.split("═" * 60) if "ÉCHEC" in b]
        echecs = blocs[-5:]  # max 5 derniers échecs

    kwargs["ti"].xcom_push(key="meta", value=meta)
    kwargs["ti"].xcom_push(key="echecs", value=echecs)

    nb_echecs = len(echecs)
    statut_global = "✅ succès" if nb_echecs == 0 else f"⚠️  {nb_echecs} échec(s)"
    return f"metriques_ok | statut={statut_global}"


# ══════════════════════════════════════════════════════════════════════════════
# TÂCHE 2 — GÉNÉRER LE RAPPORT HTML
# ══════════════════════════════════════════════════════════════════════════════

def generer_rapport_html(**kwargs) -> str:
    """
    Génère un rapport HTML complet avec :
      - Résumé du run (statut global)
      - Métriques DAG 1 (ingestion)
      - Métriques DAG 2 (pipeline)
      - Erreurs détectées (si présentes)
    Sauvegarde dans data/output/rapports/rapport_YYYY-MM-DD_HH-MM.html
    """
    log = logging.getLogger(__name__)
    ti  = kwargs["ti"]

    meta   = ti.xcom_pull(task_ids="lire_metriques", key="meta") or {}
    echecs = ti.xcom_pull(task_ids="lire_metriques", key="echecs") or []

    dag1 = meta.get("dag1", {})
    dag2 = meta.get("dag2", {})

    ts_run      = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ts_fichier  = datetime.now().strftime("%Y-%m-%d_%H-%M")
    statut_ok   = len(echecs) == 0
    statut_txt  = "✅ RUN COMPLET — SUCCÈS" if statut_ok else f"⚠️  RUN AVEC {len(echecs)} ÉCHEC(S)"
    statut_color = "#2e7d32" if statut_ok else "#c62828"
    statut_bg    = "#e8f5e9" if statut_ok else "#ffebee"

    def ligne(label, valeur, highlight=False):
        bg = " style=\"background:#fff9c4\"" if highlight else ""
        return f"<tr{bg}><td><strong>{label}</strong></td><td>{valeur}</td></tr>"

    def pct(val):
        try:
            return f"{float(val)*100:.1f}%"
        except (TypeError, ValueError):
            return str(val)

    # ── Bloc erreurs ──────────────────────────────────────────────────────────
    bloc_erreurs = ""
    if echecs:
        items = "".join(f"<pre style='background:#ffebee;padding:10px;border-left:4px solid #c62828;margin:8px 0;font-size:12px'>{e}</pre>" for e in echecs)
        bloc_erreurs = f"""
        <div class="section">
          <h2 style="color:#c62828">⚠️ Erreurs détectées ({len(echecs)})</h2>
          {items}
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Rapport AniData — {ts_run}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f5f5f5; color: #333; }}
    .header {{ background: #1a237e; color: white; padding: 28px 40px; }}
    .header h1 {{ font-size: 24px; font-weight: 700; }}
    .header p  {{ font-size: 13px; opacity: .8; margin-top: 6px; }}
    .statut-banner {{
      background: {statut_bg}; border-left: 6px solid {statut_color};
      padding: 16px 40px; font-size: 17px; font-weight: 600; color: {statut_color};
    }}
    .container {{ max-width: 900px; margin: 30px auto; padding: 0 20px; }}
    .section {{ background: white; border-radius: 8px; padding: 24px; margin-bottom: 20px;
                box-shadow: 0 1px 4px rgba(0,0,0,.08); }}
    .section h2 {{ font-size: 16px; font-weight: 700; margin-bottom: 16px;
                   padding-bottom: 8px; border-bottom: 2px solid #e0e0e0; color: #1a237e; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    td {{ padding: 8px 12px; border-bottom: 1px solid #f0f0f0; }}
    td:first-child {{ color: #555; width: 220px; }}
    .badge {{ display:inline-block; padding:3px 10px; border-radius:12px;
              font-size:12px; font-weight:600; }}
    .badge-ok  {{ background:#e8f5e9; color:#2e7d32; }}
    .badge-warn {{ background:#fff8e1; color:#f57f17; }}
    .badge-err {{ background:#ffebee; color:#c62828; }}
    .footer {{ text-align:center; color:#aaa; font-size:12px; padding:20px; }}
  </style>
</head>
<body>

<div class="header">
  <h1>🎌 AniData Lab — Rapport de Run</h1>
  <p>Généré le {ts_run} | Pipeline : DAG 1 → DAG 2 → DAG 3</p>
</div>

<div class="statut-banner">{statut_txt}</div>

<div class="container">

  <!-- RÉSUMÉ GLOBAL -->
  <div class="section">
    <h2>📋 Résumé global</h2>
    <table>
      {ligne("Date du run", ts_run)}
      {ligne("Statut global", f'<span class="badge {"badge-ok" if statut_ok else "badge-err"}">{statut_txt}</span>')}
      {ligne("Fichier source", dag1.get('fichier_source', 'N/A'))}
      {ligne("Format détecté", dag1.get('format_source', 'N/A'))}
      {ligne("Lignes en entrée", f"{dag1.get('nb_lignes', 'N/A'):,}" if isinstance(dag1.get('nb_lignes'), int) else "N/A")}
      {ligne("Lignes validées (sortie)", f"{dag2.get('nb_lignes', 'N/A'):,}" if isinstance(dag2.get('nb_lignes'), int) else "N/A")}
      {ligne("Erreurs détectées", f'<span class="badge {"badge-ok" if len(echecs)==0 else "badge-err"}">{len(echecs)}</span>')}
    </table>
  </div>

  <!-- DAG 1 — INGESTION -->
  <div class="section">
    <h2>🔄 DAG 1 — Ingestion & Conversion</h2>
    <table>
      {ligne("Timestamp", dag1.get('timestamp', 'N/A'))}
      {ligne("Fichier source", dag1.get('fichier_source', 'N/A'))}
      {ligne("Format source", dag1.get('format_source', 'N/A'))}
      {ligne("Lignes converties", f"{dag1.get('nb_lignes', 'N/A'):,}" if isinstance(dag1.get('nb_lignes'), int) else "N/A")}
      {ligne("Colonnes produites", dag1.get('nb_colonnes', 'N/A'))}
      {ligne("NaN total", dag1.get('nb_nan', 'N/A'))}
      {ligne("Taux NaN", pct(dag1.get('taux_nan')))}
      {ligne("Statut", f'<span class="badge badge-ok">{dag1.get("statut", "?")}</span>' if "succès" in str(dag1.get("statut","")) else f'<span class="badge badge-err">{dag1.get("statut","?")}</span>')}
    </table>
  </div>

  <!-- DAG 2 — PIPELINE -->
  <div class="section">
    <h2>⚙️ DAG 2 — Audit, Nettoyage, Feature Engineering, Validation</h2>
    <table>
      {ligne("Timestamp", dag2.get('timestamp', 'N/A'))}
      {ligne("Lignes validées", f"{dag2.get('nb_lignes', 'N/A'):,}" if isinstance(dag2.get('nb_lignes'), int) else "N/A")}
      {ligne("Colonnes gold", dag2.get('nb_colonnes', 'N/A'))}
      {ligne("Taux remplissage Score", pct(dag2.get('taux_score')))}
      {ligne("Warnings non bloquants", dag2.get('nb_warnings', 'N/A'))}
      {ligne("Fichiers exportés", ", ".join(dag2.get('fichiers_export', [])))}
      {ligne("Statut", f'<span class="badge badge-ok">{dag2.get("statut", "?")}</span>' if "succès" in str(dag2.get("statut","")) else f'<span class="badge badge-warn">{dag2.get("statut","N/A")}</span>')}
    </table>
  </div>

  {bloc_erreurs}

</div>

<div class="footer">
  AniData Lab · Rapport auto-généré par DAG 3 (02_rapport_email.py) · {ts_run}
</div>

</body>
</html>"""

    # ── Sauvegarde ────────────────────────────────────────────────────────────
    os.makedirs(RAPPORT_DIR, exist_ok=True)
    nom_fichier   = f"rapport_{ts_fichier}.html"
    chemin_rapport = os.path.join(RAPPORT_DIR, nom_fichier)

    with open(chemin_rapport, "w", encoding="utf-8") as f:
        f.write(html)

    taille_kb = os.path.getsize(chemin_rapport) / 1024
    log.info(f"✅ Rapport HTML généré : {chemin_rapport} ({taille_kb:.1f} KB)")

    kwargs["ti"].xcom_push(key="chemin_rapport", value=chemin_rapport)
    kwargs["ti"].xcom_push(key="statut_ok",      value=statut_ok)

    return f"rapport_ok | {nom_fichier} | {taille_kb:.1f} KB | erreurs={len(echecs)}"


# ══════════════════════════════════════════════════════════════════════════════
# TÂCHE 3 — ENVOI EMAIL (avec fallback log si SMTP absent)
# ══════════════════════════════════════════════════════════════════════════════

def envoyer_rapport(**kwargs) -> str:
    """
    Tente d'envoyer le rapport HTML par email via la config SMTP d'Airflow.
    Si SMTP n'est pas configuré → log du chemin uniquement (pas d'erreur).

    Pour activer l'envoi, configurez dans Airflow UI :
      Admin → Connections → smtp_default
        Host     : smtp.gmail.com
        Login    : votre@email.com
        Password : mot de passe d'application Google
        Port     : 587
    """
    from airflow.utils.email import send_email

    log            = logging.getLogger(__name__)
    ti             = kwargs["ti"]
    chemin_rapport = ti.xcom_pull(task_ids="generer_rapport_html", key="chemin_rapport")
    statut_ok      = ti.xcom_pull(task_ids="generer_rapport_html", key="statut_ok")

    if not chemin_rapport or not os.path.exists(chemin_rapport):
        raise FileNotFoundError(f"❌ Rapport HTML introuvable : {chemin_rapport}")

    with open(chemin_rapport, "r", encoding="utf-8") as f:
        html_content = f.read()

    sujet_emoji = "✅" if statut_ok else "⚠️"
    sujet = f"{sujet_emoji} [AniData Lab] Rapport de run — {datetime.now().strftime('%Y-%m-%d %H:%M')}"

    # ── Tentative d'envoi SMTP ────────────────────────────────────────────────
    try:
        send_email(
            to=[EMAIL_DESTINATAIRE],
            subject=sujet,
            html_content=html_content,
        )
        log.info(f"✅ Email envoyé à {EMAIL_DESTINATAIRE} : {sujet}")
        return f"email_envoye | to={EMAIL_DESTINATAIRE}"

    except Exception as smtp_err:
        # Pas d'erreur bloquante si SMTP non configuré — le rapport HTML existe déjà
        log.warning(f"⚠️  SMTP non configuré ou erreur d'envoi : {smtp_err}")
        log.info(f"📄 Rapport disponible localement : {chemin_rapport}")
        log.info(f"   → Accessible dans : ./data/output/rapports/")
        log.info(f"   Pour activer l'envoi email : Admin → Connections → smtp_default")
        return f"rapport_sauvegarde_local | {os.path.basename(chemin_rapport)}"


# ══════════════════════════════════════════════════════════════════════════════
# DAG
# ══════════════════════════════════════════════════════════════════════════════

with DAG(
    dag_id="02_rapport_email",
    description="🎌 DAG 3 — Génère un rapport HTML de run et l'envoie par email",
    default_args=default_args,
    schedule_interval=None,   # déclenché par DAG 2 uniquement
    start_date=datetime(2026, 3, 25),
    catchup=False,
    tags=["anidata", "rapport", "email"],
) as dag:

    t_lire = PythonOperator(
        task_id="lire_metriques",
        python_callable=lire_metriques,
        doc_md="**Tâche 1** — Lit pipeline_metadata.json (DAG 1 + DAG 2)",
    )

    t_html = PythonOperator(
        task_id="generer_rapport_html",
        python_callable=generer_rapport_html,
        doc_md="**Tâche 2** — Génère le rapport HTML de synthèse",
    )

    t_email = PythonOperator(
        task_id="envoyer_rapport",
        python_callable=envoyer_rapport,
        doc_md="**Tâche 3** — Envoie le rapport par email (fallback log si SMTP absent)",
    )

    # ── Flux ─────────────────────────────────────────────────────────────────
    t_lire >> t_html >> t_email
