"""
fetcher.py — RSS feed reader with SQLite deduplication.
Fetches tech/AI news from multiple sources and filters by keywords.
"""

import sqlite3
import hashlib
import logging
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Optional

import feedparser
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

DB_PATH = "chip.db"

RSS_FEEDS = {
    # English — general tech
    "The Verge":          "https://www.theverge.com/rss/index.xml",
    "TechCrunch":         "https://techcrunch.com/feed/",
    "Wired":              "https://www.wired.com/feed/rss",
    "Reuters Tech":       "https://feeds.reuters.com/reuters/technologyNews",
    "MIT Tech Review":    "https://www.technologyreview.com/feed/",
    "Ars Technica":       "https://feeds.arstechnica.com/arstechnica/technology-lab",
    "VentureBeat":        "https://venturebeat.com/feed/",
    "Bloomberg Tech":     "https://feeds.bloomberg.com/technology/news.rss",
    "The Information":    "https://www.theinformation.com/feed",
    "WSJ Tech":           "https://feeds.a.dj.com/rss/RSSWSJD.xml",
    # English — developer / open source
    "GitHub Blog":        "https://github.blog/feed/",
    "Stack Overflow Blog":"https://stackoverflow.blog/feed/",
    # AI labs
    "OpenAI Blog":        "https://openai.com/blog/rss/",
    "Anthropic Blog":     "https://www.anthropic.com/rss.xml",
    "Google AI Blog":     "https://blog.google/technology/ai/rss/",
    "DeepMind Blog":      "https://deepmind.google/blog/rss.xml",
    "Meta AI Blog":       "https://ai.meta.com/blog/rss/",
    "Mistral Blog":       "https://mistral.ai/news/rss",
    # Spanish
    "Xataka":             "https://www.xataka.com/feed.xml",
    "Hipertextual":       "https://hipertextual.com/feed",
    "El País Tecnología": "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/tecnologia/portada",
}

AI_KEYWORDS = [
    # English
    "artificial intelligence", "machine learning", "deep learning", "neural network",
    "large language model", "llm", "gpt", "claude", "gemini", "chatgpt", "openai",
    "anthropic", "google ai", "robotics", "automation", "generative ai", "diffusion",
    "transformer", "computer vision", "nlp", "natural language", "reinforcement learning",
    "agi", "autonomous", "ai model", "foundation model",
    # Spanish
    "inteligencia artificial", "aprendizaje automático", "aprendizaje profundo",
    "red neuronal", "modelo de lenguaje", "ia generativa", "robótica", "automatización",
    # Tech / Programming
    "programming", "software", "developer", "open source", "github", "kubernetes",
    "cloud computing", "cybersecurity", "semiconductor", "chip", "gpu", "quantum",
    "python", "javascript", "rust", "algorithm", "api", "startup", "silicon valley",
    "programación", "código abierto", "computación", "seguridad informática",
]


@dataclass
class Article:
    title: str
    url: str
    summary: str
    source: str
    published: str
    uid: str = field(init=False)

    def __post_init__(self):
        self.uid = hashlib.sha256(self.url.encode()).hexdigest()[:16]


def _init_db(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS seen_articles (
            uid       TEXT PRIMARY KEY,
            url       TEXT NOT NULL,
            title     TEXT,
            fetched_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS carousel_counter (
            id    INTEGER PRIMARY KEY CHECK (id = 1),
            count INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.execute("INSERT OR IGNORE INTO carousel_counter (id, count) VALUES (1, 0)")
    conn.commit()


def get_hook_color_idx() -> int:
    """Return the current hook color index (0=white, 1=green, 2=blue) without incrementing."""
    conn = sqlite3.connect(DB_PATH)
    _init_db(conn)
    row = conn.execute("SELECT count FROM carousel_counter WHERE id = 1").fetchone()
    conn.close()
    return row[0] % 3


def increment_carousel_counter() -> None:
    """Increment the publication counter after a carousel is published."""
    conn = sqlite3.connect(DB_PATH)
    _init_db(conn)
    conn.execute("UPDATE carousel_counter SET count = count + 1 WHERE id = 1")
    conn.commit()
    conn.close()


def _is_relevant(article: Article) -> bool:
    text = f"{article.title} {article.summary}".lower()
    return any(kw in text for kw in AI_KEYWORDS)


def _already_seen(conn: sqlite3.Connection, uid: str) -> bool:
    row = conn.execute("SELECT 1 FROM seen_articles WHERE uid = ?", (uid,)).fetchone()
    return row is not None


def _mark_seen(conn: sqlite3.Connection, article: Article) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO seen_articles (uid, url, title) VALUES (?, ?, ?)",
        (article.uid, article.url, article.title),
    )
    conn.commit()


def _parse_feed(source: str, url: str) -> list[Article]:
    articles: list[Article] = []
    try:
        # feedparser handles redirects; add a timeout via requests first
        response = requests.get(url, timeout=15, headers={"User-Agent": "CHIP-Bot/1.0"})
        response.raise_for_status()
        feed = feedparser.parse(response.content)
    except Exception as exc:
        log.warning("Could not fetch %s (%s): %s", source, url, exc)
        return articles

    for entry in feed.entries[:20]:  # cap per feed
        title   = getattr(entry, "title",   "").strip()
        link    = getattr(entry, "link",    "").strip()
        summary = getattr(entry, "summary", getattr(entry, "description", "")).strip()
        published = getattr(entry, "published", datetime.now(timezone.utc).isoformat())

        if not title or not link:
            continue

        articles.append(Article(
            title=title,
            url=link,
            summary=summary[:800],  # truncate for DB / prompt efficiency
            source=source,
            published=published,
        ))

    log.info("  %s → %d entries parsed", source, len(articles))
    return articles


def fetch_articles(limit: int = 5) -> list[Article]:
    """
    Fetch fresh, relevant, unseen articles from all RSS feeds.
    Returns up to `limit` articles ready for slide generation.
    """
    conn = sqlite3.connect(DB_PATH)
    _init_db(conn)

    results: list[Article] = []

    for source, url in RSS_FEEDS.items():
        log.info("Fetching: %s", source)
        for article in _parse_feed(source, url):
            if _already_seen(conn, article.uid):
                continue
            if not _is_relevant(article):
                continue
            _mark_seen(conn, article)
            results.append(article)
            if len(results) >= limit:
                break
        if len(results) >= limit:
            break

    conn.close()
    log.info("Fetched %d new relevant articles", len(results))
    return results
