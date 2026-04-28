"""
Webhook server — GitHub CI listener
=====================================
Reçoit les events GitHub check_run, vérifie la signature HMAC,
et retourne les infos du CI quand les tests sont validés.

Lancement : python webhook_server.py
"""

import hashlib
import hmac
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, abort, jsonify, request

# Charge le .env depuis la racine du projet (dossier parent)
load_dotenv(Path(__file__).parent.parent / ".env")

# ── Configuration ─────────────────────────────────────────────────
WEBHOOK_SECRET = os.environ.get("GITHUB_WEBHOOK_SECRET", "")
WATCHED_BRANCH = os.environ.get("WATCHED_BRANCH", "main")
PORT           = int(os.environ.get("PORT", 5050))

# ── App ───────────────────────────────────────────────────────────
app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


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

    log.info(f"check_run reçu — name={name}, conclusion={conclusion}, branch={branch}, sha={commit_sha}")

    # 4. Filtrage branche
    if branch != WATCHED_BRANCH:
        return jsonify({"status": "ignored", "reason": f"branch={branch}"}), 200

    # 5. Retour selon conclusion
    if conclusion == "success":
        log.info(f"✅ CI success sur {branch} ({commit_sha})")
        return jsonify({
            "status":     "success",
            "branch":     branch,
            "commit_sha": commit_sha,
            "check_name": name,
        }), 200

    log.info(f"CI {conclusion} — rien à faire")
    return jsonify({
        "status":     conclusion,
        "branch":     branch,
        "commit_sha": commit_sha,
        "check_name": name,
    }), 200


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    log.info(f"Webhook server démarré sur le port {PORT}")
    app.run(host="0.0.0.0", port=PORT)
