#!/usr/bin/env python3
"""
Générateur du mock-site AniData Lab.

Produit un site HTML statique reproduisant une encyclopédie d'anime,
conçu pour être scrapé avec requests + BeautifulSoup dans un contexte
pédagogique (cours DevOps & CI/CD, semaine 2 AniData Lab).

Exécution :
    python3 generate_site.py

Le site est produit dans ../site/ et est ensuite servi par nginx.
"""

import re
import shutil
from pathlib import Path
from html import escape
from datetime import datetime

from seed_data import ANIMES, ANOMALIES, NEWS


SITE_DIR = Path(__file__).parent.parent / "site"
ANIMES_PER_PAGE = 30
CURRENT_YEAR = 2026


# ------------------ UTILS ------------------

def slugify(text: str) -> str:
    """Transforme un titre en slug URL-friendly."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"\s+", "-", text.strip())
    text = re.sub(r"-+", "-", text)
    return text or "anime"


def build_anime_records():
    """Construit la liste normalisée des animes avec ID et slug."""
    records = []
    for i, (title_en, title_jp, year, studio, anime_type, episodes,
            status, genres, score, synopsis) in enumerate(ANIMES):
        anomaly = ANOMALIES.get(i, {})
        score_val = None if anomaly.get("score_na") else score
        studio_val = "" if anomaly.get("studio_empty") else studio

        records.append({
            "id": i + 1,
            "slug": slugify(title_en),
            "title_en": title_en,
            "title_jp": title_jp,
            "year": year,
            "studio": studio_val,
            "type": anime_type,
            "episodes": episodes,
            "status": status,
            "genres": genres,
            "score": score_val,
            "synopsis": synopsis,
            "anomaly": anomaly,
        })
    return records


# ------------------ TEMPLATES ------------------

BASE_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Helvetica Neue', Arial, sans-serif; background: #f4f4f8;
       color: #222; line-height: 1.6; }
header { background: #2a4f7c; color: white; padding: 20px 40px; }
header h1 { font-size: 1.8em; }
header nav { margin-top: 10px; }
header nav a { color: #bcd; text-decoration: none; margin-right: 20px; }
header nav a:hover { color: white; }
main { max-width: 1100px; margin: 30px auto; padding: 0 20px; }
h2 { color: #2a4f7c; margin-bottom: 15px; border-bottom: 2px solid #e0e0e8; padding-bottom: 8px; }
.anime-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
              gap: 20px; margin-top: 20px; }
.anime-card { background: white; border-radius: 6px; padding: 18px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
.anime-card h3 { margin-bottom: 6px; }
.anime-card h3 a { color: #2a4f7c; text-decoration: none; }
.anime-card h3 a:hover { text-decoration: underline; }
.anime-card .jp-title { color: #888; font-size: 0.9em; font-style: italic; }
.anime-card .meta { margin-top: 10px; font-size: 0.88em; color: #555; }
.anime-card .meta span { display: inline-block; margin-right: 12px; }
.anime-card .score { font-weight: bold; color: #d9822b; }
.anime-card .genres { margin-top: 8px; }
.anime-card .genre-tag { display: inline-block; background: #e8eef5; color: #2a4f7c;
                        padding: 2px 8px; border-radius: 3px; font-size: 0.78em;
                        margin-right: 4px; margin-bottom: 3px; }
.pagination { margin: 30px 0; text-align: center; }
.pagination a, .pagination span { display: inline-block; padding: 8px 14px; margin: 0 3px;
                                   background: white; border: 1px solid #ccd; border-radius: 4px;
                                   text-decoration: none; color: #2a4f7c; }
.pagination a:hover { background: #e8eef5; }
.pagination .current { background: #2a4f7c; color: white; border-color: #2a4f7c; }
.anime-detail { background: white; padding: 30px; border-radius: 6px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
.anime-detail h2 { border-bottom: none; font-size: 2em; margin-bottom: 0; }
.anime-detail .jp-title-big { color: #888; font-size: 1.2em; font-style: italic; margin-bottom: 20px; }
.specs { width: 100%; border-collapse: collapse; margin: 20px 0; }
.specs th { background: #e8eef5; text-align: left; padding: 10px; color: #2a4f7c;
            width: 30%; border-bottom: 1px solid #ddd; }
.specs td { padding: 10px; border-bottom: 1px solid #eee; }
.synopsis { margin-top: 20px; padding: 20px; background: #fafbfd;
            border-left: 4px solid #2a4f7c; }
.synopsis h3 { margin-bottom: 10px; color: #2a4f7c; }
.news-list article { background: white; padding: 20px; border-radius: 6px;
                     margin-bottom: 15px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
.news-list article h3 a { color: #2a4f7c; text-decoration: none; }
.news-list .news-meta { color: #888; font-size: 0.88em; margin: 5px 0 10px 0; }
.news-list .news-category { display: inline-block; background: #d9822b; color: white;
                            padding: 2px 8px; border-radius: 3px; font-size: 0.8em; }
footer { text-align: center; color: #888; padding: 30px; font-size: 0.88em; margin-top: 50px; }
.breadcrumb { margin-bottom: 15px; color: #888; font-size: 0.9em; }
.breadcrumb a { color: #2a4f7c; }
"""


def html_wrapper(title: str, body: str, extra_head: str = "") -> str:
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{escape(title)} — AniDex</title>
<link rel="stylesheet" href="/assets/style.css">
{extra_head}
</head>
<body>
<header>
  <h1><a href="/" style="color:white;text-decoration:none;">AniDex</a></h1>
  <nav>
    <a href="/">Accueil</a>
    <a href="/animes/page-1.html">Catalogue</a>
    <a href="/news/">Actualités</a>
    <a href="/about.html">À propos</a>
  </nav>
</header>
<main>
{body}
</main>
<footer>
  <p>AniDex — Mock site pédagogique pour AniData Lab · Données fictives à usage éducatif uniquement</p>
</footer>
</body>
</html>"""


def render_anime_card(anime: dict) -> str:
    """Rend une carte anime pour la liste paginée.

    Note : certaines cartes ont une structure légèrement différente pour simuler
    la variabilité HTML rencontrée en vrai scraping (pièges pédagogiques).
    """
    score_html = (f'<span class="score" data-score="{anime["score"]}">★ {anime["score"]}</span>'
                  if anime["score"] is not None
                  else '<span class="score score-na" data-score="N/A">★ N/A</span>')

    studio_html = (f'<span class="studio" data-studio="{escape(anime["studio"])}">🎬 {escape(anime["studio"])}</span>'
                   if anime["studio"]
                   else '<span class="studio studio-unknown"></span>')

    genres_html = " ".join(
        f'<span class="genre-tag">{escape(g)}</span>' for g in anime["genres"]
    )

    jp_title_html = (f'<div class="jp-title">{escape(anime["title_jp"])}</div>'
                     if anime["title_jp"] else "")

    # Variante de structure pour quelques cartes (pour tester la robustesse du parser)
    if anime["id"] % 17 == 0:
        # Format légèrement différent : pas de classe .meta wrapper
        return f"""
<article class="anime-card" data-anime-id="{anime['id']}">
  <h3><a href="/anime/{anime['slug']}.html">{escape(anime['title_en'])}</a></h3>
  {jp_title_html}
  <p class="year">Année : {anime['year']}</p>
  {studio_html}
  {score_html}
  <div class="genres">{genres_html}</div>
</article>"""

    return f"""
<article class="anime-card" data-anime-id="{anime['id']}">
  <h3><a href="/anime/{anime['slug']}.html">{escape(anime['title_en'])}</a></h3>
  {jp_title_html}
  <div class="meta">
    <span class="year" data-year="{anime['year']}">📅 {anime['year']}</span>
    {studio_html}
    {score_html}
  </div>
  <div class="genres">{genres_html}</div>
</article>"""


# ------------------ PAGES ------------------

def write_page(path: Path, html: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")


def generate_index(animes):
    top = sorted(
        [a for a in animes if a["score"] is not None],
        key=lambda a: a["score"], reverse=True
    )[:6]
    recent = sorted(animes, key=lambda a: a["year"], reverse=True)[:6]

    top_html = '<div class="anime-grid">' + "".join(render_anime_card(a) for a in top) + '</div>'
    recent_html = '<div class="anime-grid">' + "".join(render_anime_card(a) for a in recent) + '</div>'

    body = f"""
<h2>Top des animes les mieux notés</h2>
{top_html}

<h2>Dernières sorties</h2>
{recent_html}

<div style="margin-top: 30px; text-align: center;">
  <a href="/animes/page-1.html" style="display:inline-block; padding:12px 30px; background:#2a4f7c; color:white; text-decoration:none; border-radius:4px;">Voir tout le catalogue ({len(animes)} animes) →</a>
</div>
"""
    write_page(SITE_DIR / "index.html", html_wrapper("Accueil", body))


def generate_catalog_pages(animes):
    total_pages = (len(animes) + ANIMES_PER_PAGE - 1) // ANIMES_PER_PAGE

    for page_num in range(1, total_pages + 1):
        start = (page_num - 1) * ANIMES_PER_PAGE
        end = start + ANIMES_PER_PAGE
        page_animes = animes[start:end]

        cards = "".join(render_anime_card(a) for a in page_animes)

        # Pagination
        pag_items = []
        if page_num > 1:
            pag_items.append(f'<a href="/animes/page-{page_num - 1}.html" class="prev">← Précédent</a>')
        for p in range(1, total_pages + 1):
            if p == page_num:
                pag_items.append(f'<span class="current">{p}</span>')
            else:
                pag_items.append(f'<a href="/animes/page-{p}.html">{p}</a>')
        if page_num < total_pages:
            pag_items.append(f'<a href="/animes/page-{page_num + 1}.html" class="next">Suivant →</a>')
        pagination = '<div class="pagination">' + "".join(pag_items) + '</div>'

        body = f"""
<div class="breadcrumb">
  <a href="/">Accueil</a> › Catalogue › Page {page_num}
</div>
<h2>Catalogue — Page {page_num} sur {total_pages}</h2>
<p style="color:#666; margin-bottom:15px;">
  Animes {start + 1} à {min(end, len(animes))} sur {len(animes)}
</p>
<div class="anime-grid">{cards}</div>
{pagination}
"""
        write_page(
            SITE_DIR / "animes" / f"page-{page_num}.html",
            html_wrapper(f"Catalogue — Page {page_num}", body)
        )


def generate_anime_detail(anime):
    studio_html = escape(anime["studio"]) if anime["studio"] else "<em>Non renseigné</em>"
    score_html = str(anime["score"]) if anime["score"] is not None else "N/A"
    episodes_html = str(anime["episodes"]) if anime["episodes"] else "En cours"
    genres_html = ", ".join(escape(g) for g in anime["genres"])
    jp_title_html = (f'<div class="jp-title-big">{escape(anime["title_jp"])}</div>'
                     if anime["title_jp"] else "")

    # Certaines pages utilisent une structure spec légèrement différente
    variant = anime["id"] % 13 == 0

    if variant:
        specs_html = f"""
<dl class="specs-list">
  <dt>Année</dt><dd data-year="{anime['year']}">{anime['year']}</dd>
  <dt>Studio</dt><dd>{studio_html}</dd>
  <dt>Type</dt><dd>{escape(anime['type'])}</dd>
  <dt>Épisodes</dt><dd>{episodes_html}</dd>
  <dt>Statut</dt><dd>{escape(anime['status'])}</dd>
  <dt>Genres</dt><dd>{genres_html}</dd>
  <dt>Score</dt><dd class="score">{score_html}</dd>
</dl>
"""
    else:
        specs_html = f"""
<table class="specs">
  <tr><th>Année</th><td data-year="{anime['year']}">{anime['year']}</td></tr>
  <tr><th>Studio</th><td class="studio-cell">{studio_html}</td></tr>
  <tr><th>Type</th><td>{escape(anime['type'])}</td></tr>
  <tr><th>Épisodes</th><td>{episodes_html}</td></tr>
  <tr><th>Statut</th><td>{escape(anime['status'])}</td></tr>
  <tr><th>Genres</th><td>{genres_html}</td></tr>
  <tr><th>Score</th><td class="score">{score_html}</td></tr>
</table>
"""

    body = f"""
<div class="breadcrumb">
  <a href="/">Accueil</a> › <a href="/animes/page-1.html">Catalogue</a> › {escape(anime['title_en'])}
</div>
<article class="anime-detail" data-anime-id="{anime['id']}">
  <h2>{escape(anime['title_en'])}</h2>
  {jp_title_html}
  {specs_html}
  <div class="synopsis">
    <h3>Synopsis</h3>
    <p>{escape(anime['synopsis'])}</p>
  </div>
</article>
"""
    write_page(
        SITE_DIR / "anime" / f"{anime['slug']}.html",
        html_wrapper(anime["title_en"], body)
    )


def generate_news_pages():
    # Index actualités
    items_html = []
    for title, date, category, body in NEWS:
        slug = slugify(title)
        items_html.append(f"""
<article data-news-category="{escape(category)}">
  <span class="news-category">{escape(category)}</span>
  <h3><a href="/news/{slug}.html">{escape(title)}</a></h3>
  <p class="news-meta">Publié le <time datetime="{date}">{date}</time></p>
  <p>{escape(body[:150])}...</p>
</article>""")

    body = f"""
<div class="breadcrumb">
  <a href="/">Accueil</a> › Actualités
</div>
<h2>Actualités</h2>
<div class="news-list">
  {"".join(items_html)}
</div>
"""
    write_page(SITE_DIR / "news" / "index.html", html_wrapper("Actualités", body))

    # Pages individuelles (utile si les étudiants veulent scraper les articles)
    for title, date, category, content in NEWS:
        slug = slugify(title)
        article_body = f"""
<div class="breadcrumb">
  <a href="/">Accueil</a> › <a href="/news/">Actualités</a> › {escape(title)}
</div>
<article class="anime-detail" data-news-category="{escape(category)}">
  <span class="news-category">{escape(category)}</span>
  <h2>{escape(title)}</h2>
  <p class="news-meta">Publié le <time datetime="{date}">{date}</time></p>
  <div style="margin-top:20px;"><p>{escape(content)}</p></div>
</article>
"""
        write_page(SITE_DIR / "news" / f"{slug}.html", html_wrapper(title, article_body))


def generate_about():
    body = """
<h2>À propos d'AniDex</h2>
<p>AniDex est une plateforme fictive créée dans le cadre du projet pédagogique
<strong>AniData Lab</strong>. Toutes les données présentées sont utilisées à des fins
éducatives uniquement, dans le contexte d'un cours sur le DevOps & CI/CD.</p>
<p>Ce site est volontairement statique et auto-hébergé pour permettre aux apprenants
de s'exercer au scraping HTML sans contraintes légales, de rate limiting, ou de
changement de structure imprévu.</p>
"""
    write_page(SITE_DIR / "about.html", html_wrapper("À propos", body))


def generate_assets():
    write_page(SITE_DIR / "assets" / "style.css", BASE_CSS)


def generate_robots_txt():
    # robots.txt autorisant tout - puisque c'est un site pédago
    content = "User-agent: *\nAllow: /\n"
    write_page(SITE_DIR / "robots.txt", content)


# ------------------ MAIN ------------------

def main():
    print(f"🏗️  Génération du mock-site AniData Lab...")
    print(f"   Répertoire cible : {SITE_DIR}")

    if SITE_DIR.exists():
        shutil.rmtree(SITE_DIR)

    animes = build_anime_records()

    generate_assets()
    generate_index(animes)
    generate_catalog_pages(animes)
    for anime in animes:
        generate_anime_detail(anime)
    generate_news_pages()
    generate_about()
    generate_robots_txt()

    # Stats
    total_pages = sum(1 for _ in SITE_DIR.rglob("*.html"))
    print(f"✅ Site généré avec succès !")
    print(f"   {len(animes)} animes, {len(NEWS)} actualités")
    print(f"   {total_pages} pages HTML au total")
    print(f"   Généré le : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
