"""
🎌 AniData Lab - DAG de bienvenue
Premier DAG pour vérifier que Airflow fonctionne correctement.
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator


default_args = {
    "owner": "anidata-lab",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=1),
}


def hello_anidata():
    """Fonction de test : bienvenue dans AniData Lab !"""
    print("🎌 Bienvenue dans AniData Lab !")
    print("=" * 50)
    print("Votre environnement Airflow est opérationnel.")
    print("Prêt à construire votre pipeline anime/manga !")
    print("=" * 50)
    return "Hello AniData !"


def check_data_files():
    """Vérifie que les fichiers CSV sont accessibles."""
    import os

    data_dir = "/opt/airflow/data"
    expected_files = [
        "anime.csv",
        "rating_complete.csv",
        "anime_with_synopsis.csv",
    ]

    print(f"📂 Vérification du dossier : {data_dir}")
    print("-" * 50)

    found = []
    missing = []

    for filename in expected_files:
        filepath = os.path.join(data_dir, filename)
        if os.path.exists(filepath):
            size_mb = os.path.getsize(filepath) / (1024 * 1024)
            print(f"  ✅ {filename} ({size_mb:.1f} MB)")
            found.append(filename)
        else:
            print(f"  ❌ {filename} - MANQUANT")
            missing.append(filename)

    print("-" * 50)
    print(f"Trouvés : {len(found)} / {len(expected_files)}")

    if missing:
        print(f"⚠️  Fichiers manquants : {missing}")
        print("Téléchargez-les depuis Kaggle et placez-les dans ./data/")
    else:
        print("🎉 Tous les fichiers sont présents !")

    return {"found": found, "missing": missing}


with DAG(
    dag_id="00_hello_anidata",
    default_args=default_args,
    description="DAG de bienvenue - Vérifie l'environnement AniData Lab",
    schedule_interval=None,  # Déclenchement manuel uniquement
    start_date=datetime(2026, 3, 23),
    catchup=False,
    tags=["anidata", "setup"],
) as dag:

    task_hello = PythonOperator(
        task_id="hello_anidata",
        python_callable=hello_anidata,
    )

    task_check = PythonOperator(
        task_id="check_data_files",
        python_callable=check_data_files,
    )

    task_hello >> task_check
