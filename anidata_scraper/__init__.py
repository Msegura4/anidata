"""AniData Lab scraper package."""
from anidata_scraper.scraper import (
    AniDexScraper,
    Anime,
    NewsArticle,
    scrape_to_file,
)

__all__ = ["AniDexScraper", "Anime", "NewsArticle", "scrape_to_file"]
__version__ = "1.0.0"
