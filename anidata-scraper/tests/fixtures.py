"""Fixtures HTML minimales pour les tests unitaires.

On garde des extraits volontairement courts mais représentatifs des trois
cas que le scraper doit savoir gérer : carte "normale", carte "variante"
(structure légèrement différente), et carte avec valeurs manquantes.
"""

CARD_NORMAL = """
<article class="anime-card" data-anime-id="1">
  <h3><a href="/anime/attack-on-titan.html">Attack on Titan</a></h3>
  <div class="jp-title">進撃の巨人</div>
  <div class="meta">
    <span class="year" data-year="2013">📅 2013</span>
    <span class="studio" data-studio="Wit Studio">🎬 Wit Studio</span>
    <span class="score" data-score="9.0">★ 9.0</span>
  </div>
  <div class="genres">
    <span class="genre-tag">Action</span>
    <span class="genre-tag">Drama</span>
    <span class="genre-tag">Fantasy</span>
  </div>
</article>
"""

# Carte avec score "N/A" (piège pédagogique)
CARD_NO_SCORE = """
<article class="anime-card" data-anime-id="8">
  <h3><a href="/anime/demon-slayer.html">Demon Slayer</a></h3>
  <div class="jp-title">鬼滅の刃</div>
  <div class="meta">
    <span class="year" data-year="2019">📅 2019</span>
    <span class="studio" data-studio="Ufotable">🎬 Ufotable</span>
    <span class="score score-na" data-score="N/A">★ N/A</span>
  </div>
  <div class="genres">
    <span class="genre-tag">Action</span>
  </div>
</article>
"""

# Carte avec studio vide (piège pédagogique)
CARD_NO_STUDIO = """
<article class="anime-card" data-anime-id="16">
  <h3><a href="/anime/neon-genesis-evangelion.html">Neon Genesis Evangelion</a></h3>
  <div class="jp-title">新世紀エヴァンゲリオン</div>
  <div class="meta">
    <span class="year" data-year="1995">📅 1995</span>
    <span class="studio studio-unknown"></span>
    <span class="score" data-score="8.4">★ 8.4</span>
  </div>
  <div class="genres">
    <span class="genre-tag">Mecha</span>
  </div>
</article>
"""

# Carte à la structure variante (sans wrapper .meta, certains champs au niveau racine)
CARD_VARIANT = """
<article class="anime-card" data-anime-id="17">
  <h3><a href="/anime/hunter-x-hunter-2011.html">Hunter x Hunter (2011)</a></h3>
  <div class="jp-title">ハンター×ハンター</div>
  <p class="year">Année : 2011</p>
  <span class="studio" data-studio="Madhouse">🎬 Madhouse</span>
  <span class="score" data-score="9.0">★ 9.0</span>
  <div class="genres">
    <span class="genre-tag">Action</span>
    <span class="genre-tag">Adventure</span>
  </div>
</article>
"""

# Page détail classique avec table de specs
DETAIL_PAGE = """
<!DOCTYPE html><html><head><meta charset="UTF-8"></head><body>
<article class="anime-detail" data-anime-id="1">
  <h2>Attack on Titan</h2>
  <div class="jp-title-big">進撃の巨人</div>
  <table class="specs">
    <tr><th>Année</th><td data-year="2013">2013</td></tr>
    <tr><th>Studio</th><td class="studio-cell">Wit Studio</td></tr>
    <tr><th>Type</th><td>TV</td></tr>
    <tr><th>Épisodes</th><td>25</td></tr>
    <tr><th>Statut</th><td>Finished Airing</td></tr>
    <tr><th>Genres</th><td>Action, Drama, Fantasy</td></tr>
    <tr><th>Score</th><td class="score">9.0</td></tr>
  </table>
  <div class="synopsis">
    <h3>Synopsis</h3>
    <p>Dans un monde où l'humanité vit derrière d'immenses murs...</p>
  </div>
</article>
</body></html>
"""

# Page détail variante avec dl au lieu d'une table
DETAIL_PAGE_VARIANT = """
<!DOCTYPE html><html><head><meta charset="UTF-8"></head><body>
<article class="anime-detail" data-anime-id="13">
  <h2>Steins;Gate</h2>
  <div class="jp-title-big">シュタインズ・ゲート</div>
  <dl class="specs-list">
    <dt>Année</dt><dd data-year="2011">2011</dd>
    <dt>Studio</dt><dd>White Fox</dd>
    <dt>Type</dt><dd>TV</dd>
    <dt>Épisodes</dt><dd>24</dd>
    <dt>Statut</dt><dd>Finished Airing</dd>
    <dt>Genres</dt><dd>Sci-Fi, Thriller, Drama</dd>
    <dt>Score</dt><dd class="score">9.1</dd>
  </dl>
  <div class="synopsis">
    <h3>Synopsis</h3>
    <p>Un groupe d'étudiants découvre le voyage temporel...</p>
  </div>
</article>
</body></html>
"""

# Page catalogue complète (plusieurs cartes)
CATALOG_PAGE = f"""
<!DOCTYPE html><html><head><meta charset="UTF-8"></head><body>
<main>
  <div class="anime-grid">
    {CARD_NORMAL}
    {CARD_NO_SCORE}
    {CARD_NO_STUDIO}
  </div>
  <div class="pagination">
    <span class="current">1</span>
    <a href="/animes/page-2.html">2</a>
    <a href="/animes/page-3.html">3</a>
    <a href="/animes/page-2.html" class="next">Suivant →</a>
  </div>
</main>
</body></html>
"""

NEWS_PAGE = """
<!DOCTYPE html><html><head><meta charset="UTF-8"></head><body>
<main>
  <div class="news-list">
    <article data-news-category="Saisonnier">
      <span class="news-category">Saisonnier</span>
      <h3><a href="/news/printemps-2026.html">Les animes les plus attendus du printemps 2026</a></h3>
      <p class="news-meta">Publié le <time datetime="2026-04-01">2026-04-01</time></p>
      <p>La nouvelle saison démarre...</p>
    </article>
    <article data-news-category="Industrie">
      <span class="news-category">Industrie</span>
      <h3><a href="/news/ghibli-nouveau-film.html">Studio Ghibli annonce un nouveau long-métrage</a></h3>
      <p class="news-meta">Publié le <time datetime="2026-03-28">2026-03-28</time></p>
      <p>Le studio Ghibli a confirmé...</p>
    </article>
  </div>
</main>
</body></html>
"""
