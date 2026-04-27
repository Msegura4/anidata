"""
Scraper AniDex — extrait les données du mock-site AniData Lab.

Peut être utilisé :
- en CLI :       `python -m anidata_scraper.scraper --output-dir ./data/raw`
- depuis Airflow : import `scrape_to_file` dans un PythonOperator

Produit un fichier JSON par run, nommé `anime_YYYYMMDD_HHMMSS.json`, contenant
la totalité du catalogue et des actualités scrapées.
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)


# ============== MODÈLE DE DONNÉES ==============

@dataclass
class Anime:
    """Représente un anime scrapé depuis le mock-site."""
    id: int
    title_en: str
    title_jp: str | None
    detail_url: str
    year: int | None
    studio: str | None          # None si non renseigné (piège)
    score: float | None         # None si "N/A" (piège)
    genres: list[str] = field(default_factory=list)
    # Champs enrichis via la page détail :
    type: str | None = None
    episodes: int | None = None
    status: str | None = None
    synopsis: str | None = None


@dataclass
class NewsArticle:
    """Représente un article d'actualité."""
    title: str
    url: str
    category: str | None
    published_at: str | None
    body: str | None = None


# ============== SCRAPER ==============

class AniDexScraper:
    """Client de scraping pour le mock-site AniDex."""

    DEFAULT_TIMEOUT = 10
    DEFAULT_MAX_RETRIES = 3
    DEFAULT_BACKOFF = 1.0  # secondes entre retries (exponentiel)
    DEFAULT_DELAY = 0.05   # politesse entre requêtes (secondes)

    def __init__(
        self,
        base_url: str,
        timeout: int = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        delay: float = DEFAULT_DELAY,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "AniData-Lab-Scraper/1.0 (educational)",
            "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
        })

    # ---------- HTTP avec retry ----------

    def _fetch(self, path: str) -> BeautifulSoup:
        """Télécharge une URL et renvoie le HTML parsé.

        Implémente un retry exponentiel sur les erreurs réseau ou 5xx.
        """
        url = urljoin(self.base_url + "/", path.lstrip("/"))
        last_exc: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.session.get(url, timeout=self.timeout)
                response.raise_for_status()
                time.sleep(self.delay)
                # On passe les bytes pour que BeautifulSoup utilise le
                # <meta charset> du HTML et ne bute pas sur l'encodage
                # quand le serveur ne renvoie pas de charset.
                return BeautifulSoup(response.content, "html.parser")
            except (requests.ConnectionError, requests.Timeout) as exc:
                last_exc = exc
                wait = self.DEFAULT_BACKOFF * (2 ** (attempt - 1))
                logger.warning(
                    "Erreur réseau sur %s (tentative %d/%d) : %s — retry dans %.1fs",
                    url, attempt, self.max_retries, exc, wait,
                )
                time.sleep(wait)
            except requests.HTTPError as exc:
                status = exc.response.status_code if exc.response else None
                if status and 500 <= status < 600 and attempt < self.max_retries:
                    wait = self.DEFAULT_BACKOFF * (2 ** (attempt - 1))
                    logger.warning(
                        "Erreur %s sur %s (tentative %d/%d) — retry dans %.1fs",
                        status, url, attempt, self.max_retries, wait,
                    )
                    time.sleep(wait)
                    last_exc = exc
                    continue
                # 4xx ou dernier 5xx : on ne retry pas
                raise

        raise RuntimeError(f"Échec après {self.max_retries} tentatives sur {url}") from last_exc

    # ---------- Parsing ----------

    @staticmethod
    def _parse_score(card: Tag) -> float | None:
        """Extrait le score, gère le cas 'N/A'."""
        score_el = card.select_one(".score")
        if not score_el:
            return None
        raw = score_el.get("data-score")
        if not raw or raw == "N/A":
            return None
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _parse_studio(card: Tag) -> str | None:
        """Extrait le studio, retourne None si absent ou vide."""
        studio_el = card.select_one(".studio")
        if not studio_el:
            return None
        # Le champ peut avoir la classe .studio-unknown et un contenu vide
        studio = studio_el.get("data-studio") or studio_el.get_text(strip=True)
        studio = studio.replace("🎬", "").strip()
        return studio or None

    @staticmethod
    def _parse_year(card: Tag) -> int | None:
        """Extrait l'année depuis data-year ou le texte."""
        year_el = card.select_one(".year")
        if not year_el:
            return None
        raw = year_el.get("data-year")
        if raw:
            try:
                return int(raw)
            except ValueError:
                pass
        # Fallback : on parse les 4 premiers chiffres du texte
        digits = "".join(c for c in year_el.get_text() if c.isdigit())
        return int(digits[:4]) if len(digits) >= 4 else None

    def parse_catalog_card(self, card: Tag) -> Anime | None:
        """Parse une carte anime depuis la page catalogue."""
        anime_id_raw = card.get("data-anime-id")
        title_link = card.select_one("h3 a")
        if not title_link or not anime_id_raw:
            return None

        try:
            anime_id = int(anime_id_raw)
        except ValueError:
            return None

        jp_title_el = card.select_one(".jp-title")
        jp_title = jp_title_el.get_text(strip=True) if jp_title_el else None

        genres = [t.get_text(strip=True) for t in card.select(".genre-tag")]

        return Anime(
            id=anime_id,
            title_en=title_link.get_text(strip=True),
            title_jp=jp_title,
            detail_url=title_link.get("href", ""),
            year=self._parse_year(card),
            studio=self._parse_studio(card),
            score=self._parse_score(card),
            genres=genres,
        )

    # ---------- Pages ----------

    def get_total_pages(self) -> int:
        """Détecte dynamiquement le nombre de pages du catalogue."""
        soup = self._fetch("/animes/page-1.html")
        numbers = [
            int(el.get_text(strip=True))
            for el in soup.select(".pagination a, .pagination span.current")
            if el.get_text(strip=True).isdigit()
        ]
        return max(numbers) if numbers else 1

    def scrape_catalog_page(self, page_num: int) -> list[Anime]:
        """Scrape une page du catalogue."""
        soup = self._fetch(f"/animes/page-{page_num}.html")
        animes: list[Anime] = []
        for card in soup.select(".anime-card"):
            anime = self.parse_catalog_card(card)
            if anime is not None:
                animes.append(anime)
        logger.info("Page %d : %d animes extraits", page_num, len(animes))
        return animes

    def enrich_from_detail(self, anime: Anime) -> Anime:
        """Enrichit un anime avec les infos de sa page détail."""
        if not anime.detail_url:
            return anime
        try:
            soup = self._fetch(anime.detail_url)
        except Exception as exc:
            logger.warning("Impossible d'enrichir %s : %s", anime.title_en, exc)
            return anime

        # Synopsis
        synopsis_el = soup.select_one(".synopsis p")
        if synopsis_el:
            anime.synopsis = synopsis_el.get_text(strip=True)

        # Specs : on gère les deux structures (table ET dl)
        specs: dict[str, str] = {}
        for row in soup.select(".specs tr"):
            th = row.select_one("th")
            td = row.select_one("td")
            if th and td:
                specs[th.get_text(strip=True)] = td.get_text(strip=True)
        for dt in soup.select(".specs-list dt"):
            dd = dt.find_next_sibling("dd")
            if dd:
                specs[dt.get_text(strip=True)] = dd.get_text(strip=True)

        anime.type = specs.get("Type")
        anime.status = specs.get("Statut")

        raw_episodes = specs.get("Épisodes", "")
        if raw_episodes.isdigit():
            anime.episodes = int(raw_episodes)

        return anime

    def scrape_news(self) -> list[NewsArticle]:
        """Scrape la liste des actualités."""
        soup = self._fetch("/news/")
        articles: list[NewsArticle] = []
        for article_el in soup.select(".news-list article"):
            title_link = article_el.select_one("h3 a")
            time_el = article_el.select_one("time")
            if not title_link:
                continue
            articles.append(NewsArticle(
                title=title_link.get_text(strip=True),
                url=title_link.get("href", ""),
                category=article_el.get("data-news-category"),
                published_at=time_el.get("datetime") if time_el else None,
            ))
        logger.info("%d actualités récupérées", len(articles))
        return articles

    # ---------- Pipeline complet ----------

    def scrape_all(self, enrich: bool = True) -> dict:
        """Scrape tout le catalogue + actualités et renvoie un dict sérialisable."""
        total_pages = self.get_total_pages()
        logger.info("Début du scraping — %d pages de catalogue à parcourir", total_pages)

        all_animes: list[Anime] = []
        for page_num in range(1, total_pages + 1):
            all_animes.extend(self.scrape_catalog_page(page_num))

        if enrich:
            logger.info("Enrichissement via les pages détail (%d animes)...", len(all_animes))
            for i, anime in enumerate(all_animes, 1):
                self.enrich_from_detail(anime)
                if i % 20 == 0:
                    logger.info("  Enrichis : %d/%d", i, len(all_animes))

        news = self.scrape_news()

        return {
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "source": self.base_url,
            "stats": {
                "animes_count": len(all_animes),
                "news_count": len(news),
                "missing_scores": sum(1 for a in all_animes if a.score is None),
                "missing_studios": sum(1 for a in all_animes if not a.studio),
            },
            "animes": [asdict(a) for a in all_animes],
            "news": [asdict(n) for n in news],
        }


# ============== API POUR AIRFLOW ==============

def scrape_to_file(
    output_dir: str | Path,
    base_url: str = "http://mock-site",
    enrich: bool = True,
) -> str:
    """Fonction d'entrée pour un PythonOperator Airflow.

    Args:
        output_dir: répertoire où écrire le fichier JSON (sera créé si absent).
        base_url: URL de base du mock-site (par défaut, nom de service Docker).
        enrich: si True, enrichit chaque anime avec sa page détail (plus lent).

    Returns:
        Chemin absolu du fichier JSON produit (à pousser via XCom).
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    scraper = AniDexScraper(base_url=base_url)
    data = scraper.scrape_all(enrich=enrich)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"anime_{timestamp}.json"
    filepath = output_path / filename

    filepath.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    logger.info(
        "Scraping terminé : %d animes, %d news → %s",
        data["stats"]["animes_count"],
        data["stats"]["news_count"],
        filepath,
    )
    return str(filepath)


# ============== CLI ==============

def _configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scraper AniDex — extrait les données du mock-site.",
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8088",
        help="URL de base du mock-site (default: %(default)s)",
    )
    parser.add_argument(
        "--output-dir",
        default="./data/raw",
        help="Répertoire de sortie (default: %(default)s)",
    )
    parser.add_argument(
        "--no-enrich",
        action="store_true",
        help="Ne pas enrichir via les pages détail (plus rapide)",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    _configure_logging(args.verbose)

    filepath = scrape_to_file(
        output_dir=args.output_dir,
        base_url=args.base_url,
        enrich=not args.no_enrich,
    )
    print(f"\n✓ Fichier produit : {filepath}")


if __name__ == "__main__":
    main()
