#!/usr/bin/env python3
"""
Scraper de référence AniDex — À USAGE FORMATEUR UNIQUEMENT.

Ce fichier ne doit PAS être distribué tel quel aux apprenants.
Il sert à :
- vérifier que le site reste scrapable après modification,
- debug rapide pendant le cours,
- servir de base pour la correction des TP.

Exécution :
    # Site servi localement via docker compose
    python3 example_scraper.py --base-url http://localhost:8088

    # Depuis un conteneur Airflow sur le même réseau docker
    python3 example_scraper.py --base-url http://mock-site

Le scraper produit un fichier JSON structuré contenant tous les animes
du catalogue, enrichis avec leurs pages de détail.
"""

import argparse
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class AniDexScraper:
    """Scraper du mock-site AniDex."""

    def __init__(self, base_url: str, delay: float = 0.1, timeout: int = 10):
        self.base_url = base_url.rstrip("/")
        self.delay = delay  # politesse même en local
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "AniData-Lab-Scraper/1.0 (pedagogical use)"
        })

    def _fetch(self, path: str) -> BeautifulSoup:
        url = urljoin(self.base_url + "/", path.lstrip("/"))
        logger.debug(f"GET {url}")
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        time.sleep(self.delay)
        # On passe les bytes (response.content) plutôt que le texte décodé,
        # pour que BeautifulSoup lise le charset dans le <meta> HTML et évite
        # les problèmes d'encodage quand le serveur ne renvoie pas de charset
        # dans le Content-Type (cas de certains setups nginx/http.server).
        return BeautifulSoup(response.content, "html.parser")

    # ---------- Catalogue paginé ----------

    def scrape_catalog_page(self, page_num: int) -> list[dict]:
        """Extrait la liste des animes d'une page de catalogue."""
        soup = self._fetch(f"/animes/page-{page_num}.html")
        animes = []

        for card in soup.select(".anime-card"):
            anime_id = card.get("data-anime-id")
            title_link = card.select_one("h3 a")
            if not title_link:
                continue

            jp_title_el = card.select_one(".jp-title")
            score_el = card.select_one(".score")
            year_el = card.select_one(".year")
            studio_el = card.select_one(".studio")

            # Gestion du score : peut être "N/A"
            score = None
            if score_el:
                score_attr = score_el.get("data-score")
                if score_attr and score_attr != "N/A":
                    try:
                        score = float(score_attr)
                    except ValueError:
                        score = None

            # Gestion du studio : peut être vide
            studio = ""
            if studio_el:
                studio_attr = studio_el.get("data-studio")
                studio = studio_attr if studio_attr else ""

            # Year : attribut data-year sur .year, sinon parser le texte
            year = None
            if year_el:
                year_attr = year_el.get("data-year")
                if year_attr:
                    try:
                        year = int(year_attr)
                    except ValueError:
                        pass
                if year is None:
                    # Cas de structure alternative (sans data-year) : on parse le texte
                    txt = year_el.get_text(strip=True)
                    digits = "".join(c for c in txt if c.isdigit())
                    if digits:
                        year = int(digits[:4])

            genres = [t.get_text(strip=True) for t in card.select(".genre-tag")]

            animes.append({
                "id": int(anime_id) if anime_id else None,
                "title_en": title_link.get_text(strip=True),
                "title_jp": jp_title_el.get_text(strip=True) if jp_title_el else None,
                "detail_url": title_link.get("href"),
                "year": year,
                "studio": studio,
                "score": score,
                "genres": genres,
            })

        return animes

    def scrape_all_catalog(self) -> list[dict]:
        """Parcourt toutes les pages du catalogue."""
        soup = self._fetch("/animes/page-1.html")
        all_animes = []

        # Détecte le nombre total de pages via les liens de pagination
        page_links = soup.select(".pagination a, .pagination span.current")
        page_numbers = []
        for link in page_links:
            text = link.get_text(strip=True)
            if text.isdigit():
                page_numbers.append(int(text))
        total_pages = max(page_numbers) if page_numbers else 1

        logger.info(f"Détecté {total_pages} pages de catalogue")

        for page_num in range(1, total_pages + 1):
            logger.info(f"Scraping page {page_num}/{total_pages}...")
            animes = self.scrape_catalog_page(page_num)
            all_animes.extend(animes)

        return all_animes

    # ---------- Fiche détail ----------

    def scrape_detail(self, detail_path: str) -> dict:
        """Enrichit une fiche anime avec les infos de sa page détail."""
        soup = self._fetch(detail_path)

        # Synopsis
        synopsis_el = soup.select_one(".synopsis p")
        synopsis = synopsis_el.get_text(strip=True) if synopsis_el else ""

        # Specs : gérer le double format (table OU dl)
        specs = {}
        for row in soup.select(".specs tr"):
            th = row.select_one("th")
            td = row.select_one("td")
            if th and td:
                specs[th.get_text(strip=True)] = td.get_text(strip=True)
        for dt in soup.select(".specs-list dt"):
            dd = dt.find_next_sibling("dd")
            if dd:
                specs[dt.get_text(strip=True)] = dd.get_text(strip=True)

        # Extraction typée des champs
        episodes = None
        if "Épisodes" in specs:
            raw = specs["Épisodes"]
            if raw.isdigit():
                episodes = int(raw)

        return {
            "synopsis": synopsis,
            "type": specs.get("Type"),
            "episodes": episodes,
            "status": specs.get("Statut"),
        }

    # ---------- News ----------

    def scrape_news(self) -> list[dict]:
        """Extrait la liste des actualités."""
        soup = self._fetch("/news/")
        articles = []

        for article in soup.select(".news-list article"):
            title_link = article.select_one("h3 a")
            category = article.get("data-news-category")
            time_el = article.select_one("time")

            articles.append({
                "title": title_link.get_text(strip=True) if title_link else "",
                "url": title_link.get("href") if title_link else "",
                "category": category,
                "published_at": time_el.get("datetime") if time_el else None,
            })

        return articles


# ---------- MAIN ----------

def main():
    parser = argparse.ArgumentParser(description="Scraper de référence AniDex")
    parser.add_argument("--base-url", default="http://localhost:8088",
                        help="URL de base du mock-site")
    parser.add_argument("--output", default="anidex_scrape.json",
                        help="Fichier JSON de sortie")
    parser.add_argument("--enrich", action="store_true",
                        help="Enrichir chaque anime avec sa page détail (plus lent)")
    args = parser.parse_args()

    scraper = AniDexScraper(args.base_url)

    logger.info(f"Scraping du catalogue sur {args.base_url}")
    animes = scraper.scrape_all_catalog()
    logger.info(f"✓ {len(animes)} animes récupérés depuis le catalogue")

    if args.enrich:
        logger.info("Enrichissement via les pages détail...")
        for i, anime in enumerate(animes, 1):
            if anime["detail_url"]:
                try:
                    detail = scraper.scrape_detail(anime["detail_url"])
                    anime.update(detail)
                except Exception as exc:
                    logger.warning(f"Erreur sur {anime['title_en']}: {exc}")
            if i % 10 == 0:
                logger.info(f"  Enrichis : {i}/{len(animes)}")

    logger.info("Scraping des actualités...")
    news = scraper.scrape_news()
    logger.info(f"✓ {len(news)} articles récupérés")

    output = {
        "scraped_at": datetime.utcnow().isoformat() + "Z",
        "source": args.base_url,
        "animes_count": len(animes),
        "news_count": len(news),
        "animes": animes,
        "news": news,
    }

    Path(args.output).write_text(json.dumps(output, ensure_ascii=False, indent=2),
                                  encoding="utf-8")
    logger.info(f"✓ Écrit dans {args.output}")

    # Mini rapport
    missing_scores = sum(1 for a in animes if a["score"] is None)
    missing_studios = sum(1 for a in animes if not a["studio"])
    logger.info(f"\n--- Rapport qualité ---")
    logger.info(f"Animes avec score manquant : {missing_scores}")
    logger.info(f"Animes avec studio manquant : {missing_studios}")


if __name__ == "__main__":
    main()
