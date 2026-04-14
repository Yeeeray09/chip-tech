"""
main.py — CHIP orchestrator.

Usage:
  python main.py            # fetch → generate → render → publish
  python main.py --test     # fetch → generate → render (saves PNGs, no publish)
  python main.py --test --article-limit 1
"""

import argparse
import logging
import sys
import uuid
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level   = logging.INFO,
    format  = "%(asctime)s [%(levelname)s] %(message)s",
    handlers = [
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("chip.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CHIP — Instagram AI/Tech carousel bot")
    parser.add_argument(
        "--test",
        action="store_true",
        help="Generate and render slides locally without publishing to Instagram",
    )
    parser.add_argument(
        "--article-limit",
        type=int,
        default=3,
        metavar="N",
        help="Max number of articles to process per run (default: 3)",
    )
    return parser.parse_args()


def run(test_mode: bool, article_limit: int) -> None:
    # Late imports so env is loaded before modules that read it at import time
    from fetcher   import fetch_articles
    from generator import generate_carousel
    from renderer  import render_carousel

    log.info("=" * 60)
    log.info("CHIP starting — mode: %s", "TEST" if test_mode else "PUBLISH")
    log.info("=" * 60)

    # ── 1. Fetch articles ────────────────────────────────────────
    articles = fetch_articles(limit=article_limit)
    if not articles:
        log.info("No new articles found. Exiting.")
        return

    published_count = 0

    for article in articles:
        run_id = f"{article.uid}_{uuid.uuid4().hex[:6]}"
        log.info("\n── Processing: %s [%s]", article.title[:70], article.source)

        try:
            # ── 2. Generate slide content via Claude ─────────────
            carousel = generate_carousel(article)

            # ── 3. Render slides to PNG ──────────────────────────
            image_paths = render_carousel(carousel, run_id)

            if test_mode:
                log.info("TEST MODE — Images saved:")
                for p in image_paths:
                    log.info("  %s", p)
                log.info("Caption:\n%s", carousel.caption)

            else:
                # ── 4. Publish to Instagram ──────────────────────
                from publisher import publish_carousel
                from fetcher import increment_carousel_counter
                media_id = publish_carousel(image_paths, carousel.caption)
                increment_carousel_counter()
                log.info("Published carousel → media_id: %s", media_id)
                published_count += 1

        except Exception as exc:
            log.error("Failed to process article '%s': %s", article.title[:50], exc, exc_info=True)
            continue  # skip to next article

    log.info("\n── Run complete. %d carousel(s) published.", published_count)


def main() -> None:
    args = parse_args()
    run(test_mode=args.test, article_limit=args.article_limit)


if __name__ == "__main__":
    main()
