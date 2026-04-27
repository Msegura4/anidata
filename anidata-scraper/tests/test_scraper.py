"""Tests unitaires du scraper AniDex.

On teste la logique de parsing sans appels HTTP réels, en mockant les
réponses réseau. Deux approches combinées :
1. Tests de parsing pur via des fragments HTML fixes (fixtures.py)
2. Tests d'intégration via monkeypatching de la méthode _fetch
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from anidata_scraper.scraper import (
    AniDexScraper,
    Anime,
    NewsArticle,
    scrape_to_file,
)
from tests import fixtures

# ============== PARSING UNITAIRE ==============

@pytest.fixture
def scraper() -> AniDexScraper:
    """Instance de scraper non connectée (on mockera _fetch dans les tests d'intégration)."""
    return AniDexScraper(base_url="http://mock-site", delay=0)


class TestParseCatalogCard:
    """Tests de la méthode parse_catalog_card."""

    def test_parse_normal_card(self, scraper):
        card = BeautifulSoup(fixtures.CARD_NORMAL, "html.parser").select_one(".anime-card")
        anime = scraper.parse_catalog_card(card)

        assert anime is not None
        assert anime.id == 1
        assert anime.title_en == "Attack on Titan"
        assert anime.title_jp == "進撃の巨人"
        assert anime.year == 2013
        assert anime.studio == "Wit Studio"
        assert anime.score == 9.0
        assert anime.genres == ["Action", "Drama", "Fantasy"]
        assert anime.detail_url == "/anime/attack-on-titan.html"

    def test_parse_card_with_na_score(self, scraper):
        """Une carte avec score 'N/A' doit produire score=None, pas une exception."""
        card = BeautifulSoup(fixtures.CARD_NO_SCORE, "html.parser").select_one(".anime-card")
        anime = scraper.parse_catalog_card(card)

        assert anime is not None
        assert anime.title_en == "Demon Slayer"
        assert anime.score is None
        # Le reste doit rester lisible
        assert anime.studio == "Ufotable"
        assert anime.year == 2019

    def test_parse_card_with_empty_studio(self, scraper):
        """Une carte avec studio vide doit produire studio=None."""
        card = BeautifulSoup(fixtures.CARD_NO_STUDIO, "html.parser").select_one(".anime-card")
        anime = scraper.parse_catalog_card(card)

        assert anime is not None
        assert anime.title_en == "Neon Genesis Evangelion"
        assert anime.studio is None
        assert anime.score == 8.4  # Les autres champs doivent rester OK

    def test_parse_variant_structure(self, scraper):
        """La structure alternative (sans wrapper .meta) doit être gérée."""
        card = BeautifulSoup(fixtures.CARD_VARIANT, "html.parser").select_one(".anime-card")
        anime = scraper.parse_catalog_card(card)

        assert anime is not None
        assert anime.id == 17
        assert anime.title_en == "Hunter x Hunter (2011)"
        assert anime.year == 2011  # Parsé depuis le texte, pas data-year
        assert anime.studio == "Madhouse"
        assert anime.score == 9.0

    def test_parse_invalid_card_returns_none(self, scraper):
        """Une carte sans id ou sans lien doit renvoyer None (pas crasher)."""
        card = BeautifulSoup(
            '<article class="anime-card"><p>broken</p></article>',
            "html.parser",
        ).select_one(".anime-card")
        assert scraper.parse_catalog_card(card) is None


# ============== SCRAPING AVEC MOCK HTTP ==============

class FakeResponse:
    """Fake requests.Response qui renvoie du HTML fixé."""

    def __init__(self, html: str, status_code: int = 200):
        self.content = html.encode("utf-8")
        self.text = html
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(f"{self.status_code} Error", response=self)


@pytest.fixture
def mock_site(scraper, monkeypatch):
    """Monkeypatch _fetch pour renvoyer le HTML de notre choix."""
    routes = {}

    def fake_fetch(path: str):
        if path not in routes:
            raise AssertionError(f"Chemin non mocké : {path}")
        return BeautifulSoup(routes[path].encode("utf-8"), "html.parser")

    monkeypatch.setattr(scraper, "_fetch", fake_fetch)
    return routes


class TestScrapeCatalogPage:
    def test_scrape_catalog_returns_all_cards(self, scraper, mock_site):
        mock_site["/animes/page-1.html"] = fixtures.CATALOG_PAGE
        animes = scraper.scrape_catalog_page(1)

        assert len(animes) == 3
        assert all(isinstance(a, Anime) for a in animes)
        titles = [a.title_en for a in animes]
        assert "Attack on Titan" in titles
        assert "Demon Slayer" in titles
        assert "Neon Genesis Evangelion" in titles

    def test_get_total_pages_detects_pagination(self, scraper, mock_site):
        mock_site["/animes/page-1.html"] = fixtures.CATALOG_PAGE
        assert scraper.get_total_pages() == 3


class TestEnrichFromDetail:
    def test_enrich_adds_synopsis_and_specs(self, scraper, mock_site):
        mock_site["/anime/attack-on-titan.html"] = fixtures.DETAIL_PAGE
        anime = Anime(
            id=1, title_en="Attack on Titan", title_jp="進撃の巨人",
            detail_url="/anime/attack-on-titan.html",
            year=2013, studio="Wit Studio", score=9.0,
            genres=["Action"],
        )
        enriched = scraper.enrich_from_detail(anime)

        assert enriched.type == "TV"
        assert enriched.episodes == 25
        assert enriched.status == "Finished Airing"
        assert enriched.synopsis is not None
        assert "humanité" in enriched.synopsis

    def test_enrich_handles_variant_structure(self, scraper, mock_site):
        """La structure <dl> doit aussi fonctionner."""
        mock_site["/anime/steins-gate.html"] = fixtures.DETAIL_PAGE_VARIANT
        anime = Anime(
            id=13, title_en="Steins;Gate", title_jp="シュタインズ・ゲート",
            detail_url="/anime/steins-gate.html",
            year=2011, studio="White Fox", score=9.1, genres=[],
        )
        enriched = scraper.enrich_from_detail(anime)

        assert enriched.type == "TV"
        assert enriched.episodes == 24

    def test_enrich_with_missing_page_does_not_crash(self, scraper, monkeypatch):
        """Une erreur sur la page détail ne doit pas casser le pipeline."""
        def broken_fetch(path):
            raise RuntimeError("Network down")
        monkeypatch.setattr(scraper, "_fetch", broken_fetch)

        anime = Anime(
            id=1, title_en="X", title_jp=None, detail_url="/anime/x.html",
            year=2020, studio="Y", score=8.0, genres=[],
        )
        result = scraper.enrich_from_detail(anime)
        # L'anime est renvoyé tel quel, sans enrichissement
        assert result.synopsis is None
        assert result.episodes is None


class TestScrapeNews:
    def test_scrape_news_extracts_articles(self, scraper, mock_site):
        mock_site["/news/"] = fixtures.NEWS_PAGE
        news = scraper.scrape_news()

        assert len(news) == 2
        assert all(isinstance(n, NewsArticle) for n in news)
        assert news[0].category == "Saisonnier"
        assert news[0].published_at == "2026-04-01"


# ============== RETRY HTTP ==============

class TestRetryLogic:
    def test_retry_on_timeout_then_success(self, scraper, monkeypatch):
        """Une Timeout doit déclencher un retry qui peut réussir."""
        import requests
        call_count = {"n": 0}

        def flaky_get(url, timeout):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise requests.Timeout("simulated")
            return FakeResponse("<html><body>ok</body></html>")

        monkeypatch.setattr(scraper.session, "get", flaky_get)
        monkeypatch.setattr("time.sleep", lambda s: None)  # accélère le test

        soup = scraper._fetch("/ping")
        assert "ok" in soup.get_text()
        assert call_count["n"] == 2  # 1 échec + 1 succès

    def test_no_retry_on_404(self, scraper, monkeypatch):
        """Une 404 ne doit pas être retriée (erreur client)."""
        call_count = {"n": 0}

        def always_404(url, timeout):
            call_count["n"] += 1
            return FakeResponse("not found", status_code=404)

        monkeypatch.setattr(scraper.session, "get", always_404)
        monkeypatch.setattr("time.sleep", lambda s: None)

        import requests
        with pytest.raises(requests.HTTPError):
            scraper._fetch("/missing")
        assert call_count["n"] == 1  # pas de retry


# ============== INTÉGRATION scrape_to_file ==============

class TestScrapeToFile:
    def test_writes_json_with_expected_structure(self, tmp_path, monkeypatch):
        """scrape_to_file doit produire un JSON avec la structure attendue."""
        # On mocke scrape_all pour éviter tout appel HTTP
        fake_data = {
            "scraped_at": "2026-04-27T12:00:00+00:00",
            "source": "http://mock-site",
            "stats": {"animes_count": 1, "news_count": 0,
                      "missing_scores": 0, "missing_studios": 0},
            "animes": [{"id": 1, "title_en": "Test"}],
            "news": [],
        }
        monkeypatch.setattr(
            AniDexScraper, "scrape_all", lambda self, enrich=True: fake_data
        )

        filepath = scrape_to_file(output_dir=tmp_path, base_url="http://mock-site")

        assert Path(filepath).exists()
        assert Path(filepath).name.startswith("anime_")
        assert Path(filepath).name.endswith(".json")

        data = json.loads(Path(filepath).read_text(encoding="utf-8"))
        assert data["stats"]["animes_count"] == 1
        assert data["animes"][0]["title_en"] == "Test"
