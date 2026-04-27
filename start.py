#!/usr/bin/env python3
"""
🎌 AniData Lab — Script de démarrage
=====================================
Lance l'ensemble de la stack Docker et vérifie que tous les services
sont opérationnels avant de rendre la main.

Usage :
    python start.py           # Démarre tous les services
    python start.py --stop    # Arrête tous les services
    python start.py --status  # Affiche l'état des services
"""

import subprocess
import sys
import time
import argparse
import urllib.request
import urllib.error


# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

SERVICES = [
    {
        "name":      "PostgreSQL",
        "container": "anidata-postgres",
        "check":     None,  # vérifié via healthcheck Docker
    },
    {
        "name":      "Elasticsearch",
        "container": "anidata-elasticsearch",
        "check":     "http://localhost:9200/_cluster/health",
    },
    {
        "name":      "Airflow Webserver",
        "container": "anidata-airflow-webserver",
        "check":     "http://localhost:8080/health",
    },
    {
        "name":      "Grafana",
        "container": "anidata-grafana",
        "check":     "http://localhost:3000/api/health",
    },
]

URLS = {
    "Airflow":        "http://localhost:8080",
    "Grafana":        "http://localhost:3000",
    "Elasticsearch":  "http://localhost:9200",
}

TIMEOUT = 120   # secondes max d'attente par service
POLL    = 3     # intervalle de polling en secondes


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def run(cmd: list[str], check=True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=check, capture_output=False)


def http_ok(url: str) -> bool:
    """Retourne True si l'URL répond avec un code < 500."""
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            return r.status < 500
    except Exception:
        return False


def container_running(name: str) -> bool:
    """Retourne True si le container Docker est en état 'running'."""
    result = subprocess.run(
        ["docker", "inspect", "-f", "{{.State.Running}}", name],
        capture_output=True, text=True
    )
    return result.stdout.strip() == "true"


def attendre_service(service: dict) -> bool:
    """Attend qu'un service soit prêt. Retourne True si OK, False si timeout."""
    nom     = service["name"]
    check   = service["check"]
    debut   = time.time()

    print(f"  ⏳ {nom}...", end="", flush=True)

    while time.time() - debut < TIMEOUT:
        ok = http_ok(check) if check else container_running(service["container"])
        if ok:
            elapsed = int(time.time() - debut)
            print(f" ✅ ({elapsed}s)")
            return True
        print(".", end="", flush=True)
        time.sleep(POLL)

    print(f" ❌ timeout ({TIMEOUT}s)")
    return False


def unpause_dags():
    """Dépause les 4 DAGs du projet."""
    dags = [
        "00_ingestion_conversion",
        "01_pipeline_anidata",
        "02_rapport_email",
        "03_elasticsearch_grafana",
    ]
    container = "anidata-airflow-webserver"
    for dag in dags:
        result = subprocess.run(
            ["docker", "exec", container, "airflow", "dags", "unpause", dag],
            capture_output=True, text=True
        )
        statut = "✅" if result.returncode == 0 else "⚠️ "
        print(f"  {statut} DAG dépausé : {dag}")


# ══════════════════════════════════════════════════════════════════════════════
# COMMANDES
# ══════════════════════════════════════════════════════════════════════════════

def cmd_start():
    print("\n🎌 AniData Lab — Démarrage de la stack\n")

    # 1. Lancement Docker Compose
    print("▶  Lancement des containers Docker...")
    run(["docker", "compose", "up", "-d"])
    print()

    # 2. Attente que chaque service soit prêt
    print("▶  Vérification des services :")
    tous_ok = True
    for service in SERVICES:
        ok = attendre_service(service)
        if not ok:
            tous_ok = False

    print()

    if not tous_ok:
        print("❌ Certains services n'ont pas démarré correctement.")
        print("   → Lance : docker compose logs pour diagnostiquer.\n")
        sys.exit(1)

    # 3. Dépause des DAGs
    print("▶  Activation des DAGs Airflow :")
    unpause_dags()
    print()

    # 4. Récap des URLs
    print("─" * 48)
    print("✅ Stack prête ! Accès aux interfaces :\n")
    for nom, url in URLS.items():
        print(f"   {nom:<16} → {url}")
    print()
    print("   Airflow login  : admin / admin")
    print("   Grafana login  : admin / anidata")
    print("─" * 48)
    print()


def cmd_stop():
    print("\n🎌 AniData Lab — Arrêt de la stack\n")
    run(["docker", "compose", "down"])
    print("\n✅ Stack arrêtée.\n")


def cmd_status():
    print("\n🎌 AniData Lab — État des services\n")
    for service in SERVICES:
        running = container_running(service["container"])
        check   = service["check"]
        http    = http_ok(check) if check and running else None

        if not running:
            statut = "🔴 arrêté"
        elif http is False:
            statut = "🟡 démarrage..."
        else:
            statut = "🟢 opérationnel"

        print(f"  {statut:<22} {service['name']}")
    print()


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AniData Lab — Gestion de la stack")
    group  = parser.add_mutually_exclusive_group()
    group.add_argument("--stop",   action="store_true", help="Arrête tous les services")
    group.add_argument("--status", action="store_true", help="Affiche l'état des services")
    args = parser.parse_args()

    if args.stop:
        cmd_stop()
    elif args.status:
        cmd_status()
    else:
        cmd_start()
