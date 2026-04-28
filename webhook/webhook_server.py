"""
Webhook server — GitHub CI → Scraper trigger
=============================================
Reçoit les events GitHub check_run, vérifie la signature HMAC.
Quand les 3 checks sont success sur la branche surveillée,
lance le scraper anidata en subprocess.

Lancement : python webhook/webhook_server.py
"""

import hashlib
import hmac
import logging
import os
import subprocess
import sys
import threading
from pathlib import Path

import requests as http_requests
from dotenv import load_dotenv
from flask import Flask, abort, jsonify, request

# Charge le .env depuis la racine du projet (dossier parent)
load_dotenv(Path(__file__).parent.parent / ".env")

# ── Configuration ─────────────────────────────────────────────────
WEBHOOK_SECRET = os.environ.get("GITHUB_WEBHOOK_SECRET", "")
WATCHED_BRANCH = os.environ.get("WATCHED_BRANCH", "main")
MOCK_SITE_URL    = os.environ.get("MOCK_SITE_URL",    "http://localhost:8088")
AIRFLOW_URL      = os.environ.get("AIRFLOW_URL",      "http://localhost:8080")
AIRFLOW_USER     = os.environ.get("AIRFLOW_USER",     "admin")
AIRFLOW_PASSWORD = os.environ.get("AIRFLOW_PASSWORD", "admin")
DAG_ID           = "00_ingestion_conversion"
PORT             = int(os.environ.get("PORT", 5050))

# Chemins
ROOT_DIR    = Path(__file__).parent.parent
SCRAPER_DIR = ROOT_DIR / "anidata-scraper"
OUTPUT_DIR  = ROOT_DIR / "data" / "input"

# Les 3 checks qui doivent tous passer
REQUIRED_CHECKS = {
    "Tests (Python 3.10)",
    "Tests (Python 3.11)",
    "Lint (ruff)",
}

# ── App ───────────────────────────────────────────────────────────
app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# État en mémoire : { commit_sha: set(checks passés) }
ci_results: dict[str, set] = {}


def verify_signature(payload_bytes: bytes, signature_header: str) -> bool:
    """Vérifie la signature HMAC-SHA256 envoyée par GitHub."""
    if not WEBHOOK_SECRET:
        log.warning("GITHUB_WEBHOOK_SECRET non défini — signature ignorée (dangereux en prod !)")
        return True
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(
        WEBHOOK_SECRET.encode(), payload_bytes, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature_header)


def trigger_dag() -> None:
    """Appelle l'API REST Airflow pour déclencher le DAG 00_ingestion_conversion."""
    url = f"{AIRFLOW_URL}/api/v1/dags/{DAG_ID}/dagRuns"
    try:
        resp = http_requests.post(
            url,
            auth=(AIRFLOW_USER, AIRFLOW_PASSWORD),
            json={"conf": {"source": "github_webhook"}},
            timeout=10,
        )
        if resp.status_code in (200, 201):
            log.info(f"HOUSTON C'EST PARTIIII DAG {DAG_ID} déclenché (HTTP {resp.status_code})")
        else:
            log.error(f"❌ Airflow a répondu {resp.status_code} : {resp.text}")
    except http_requests.exceptions.RequestException as e:
        log.error(f"❌ Impossible de contacter Airflow : {e}")


def _run_scraper() -> None:
    """Exécute le scraper et déclenche le DAG si succès."""
    cmd = [
        sys.executable, "-m", "anidata_scraper.scraper",
        "--base-url", MOCK_SITE_URL,
        "--output-dir", str(OUTPUT_DIR),
    ]
    log.info(f"Scraper démarré — sortie vers {OUTPUT_DIR}")
    proc = subprocess.run(
        cmd,
        cwd=str(SCRAPER_DIR),
        capture_output=True,
        text=True,
    )
    if proc.returncode == 0:
        log.info(f"✅ Scraper terminé avec succès\n{proc.stdout.strip()}")
        trigger_dag()
    else:
        log.error(f"❌ Scraper échoué (code {proc.returncode})\n{proc.stderr.strip()}")


def launch_scraper() -> None:
    """Lance le scraper dans un thread séparé pour ne pas bloquer le serveur."""
    thread = threading.Thread(target=_run_scraper, daemon=True)
    thread.start()
    log.info("Thread scraper lancé")


@app.route("/webhook", methods=["POST"])
def github_webhook():
    payload_bytes = request.get_data()

    # 1. Vérification signature
    sig = request.headers.get("X-Hub-Signature-256", "")
    if not verify_signature(payload_bytes, sig):
        log.warning("Signature invalide — requête rejetée")
        abort(403)

    # 2. Lecture de l'event
    event = request.headers.get("X-GitHub-Event", "")
    payload = request.get_json(force=True) or {}

    if event != "check_run":
        log.info(f"Event ignoré : {event}")
        return jsonify({"status": "ignored", "reason": f"event={event}"}), 200

    # 3. Extraction des infos
    check_run  = payload.get("check_run", {})
    conclusion = check_run.get("conclusion")
    branch     = check_run.get("check_suite", {}).get("head_branch")
    name       = check_run.get("name")
    commit_sha = check_run.get("head_sha")

    log.info(f"check_run reçu — name={name}, conclusion={conclusion}, branch={branch}")

    # 4. Filtres
    if branch != WATCHED_BRANCH:
        return jsonify({"status": "ignored", "reason": f"branch={branch}"}), 200

    if conclusion != "success":
        return jsonify({"status": "ignored", "reason": f"conclusion={conclusion}"}), 200

    if name not in REQUIRED_CHECKS:
        return jsonify({"status": "ignored", "reason": f"check inconnu: {name}"}), 200

    # 5. Accumulation des checks réussis pour ce commit
    if commit_sha not in ci_results:
        ci_results[commit_sha] = set()
    ci_results[commit_sha].add(name)

    passed = ci_results[commit_sha]
    remaining = REQUIRED_CHECKS - passed
    log.info(f"✅ {name} — {len(passed)}/{len(REQUIRED_CHECKS)} checks OK pour {commit_sha[:8]}")

    # 6. Tous les checks sont passés → lancement scraper
    if not remaining:
        log.info(f"YES YES YES - Tous les checks sont success — lancement du scraper")
        del ci_results[commit_sha]  # nettoyage mémoire
        launch_scraper()
        return jsonify({
            "status":     "triggered",
            "commit_sha": commit_sha,
            "message":    "Tous les checks sont success, scraper lancé",
        }), 200

    return jsonify({
        "status":    "partial",
        "passed":    list(passed),
        "remaining": list(remaining),
    }), 200


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    log.info(f"Webhook server démarré sur le port {PORT}")
    log.info(f"Branche surveillée : {WATCHED_BRANCH}")
    log.info(f"Checks attendus : {REQUIRED_CHECKS}")
    app.run(host="0.0.0.0", port=PORT)
