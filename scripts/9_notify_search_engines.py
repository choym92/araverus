#!/usr/bin/env python3
"""
Phase 6.5 · Notify Search Engines — IndexNow (Bing/Yandex) + WebSub (Google).

Fetches recently published articles (last N hours) and pings search engines
so they crawl new content faster.

Usage:
    python scripts/9_notify_search_engines.py                  # default 24h lookback
    python scripts/9_notify_search_engines.py --hours 6        # last 6 hours
    python scripts/9_notify_search_engines.py --dry-run        # print URLs, no HTTP calls
"""

import argparse
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv

log = logging.getLogger("notify")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SITE = "https://araverus.com"
INDEXNOW_ENDPOINT = "https://api.indexnow.org/indexnow"
WEBSUB_HUB = "https://pubsubhubbub.appspot.com/"
RSS_FEED_URL = f"{SITE}/rss.xml"
SITEMAP_NEWS_URL = f"{SITE}/sitemap-news.xml"
DEFAULT_LOOKBACK_HOURS = 24


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Notify search engines of new articles")
    p.add_argument("--hours", type=int, default=DEFAULT_LOOKBACK_HOURS,
                   help="Lookback window in hours (default: 24)")
    p.add_argument("--dry-run", action="store_true",
                   help="Print URLs without sending notifications")
    return p.parse_args()


def fetch_recent_slugs(sb, hours: int) -> list[str]:
    """Fetch slugs of articles published in the last N hours that have headlines."""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    resp = (
        sb.table("wsj_items")
        .select("slug")
        .gte("published_at", cutoff)
        .not_.is_("slug", "null")
        .execute()
    )
    return [r["slug"] for r in resp.data if r.get("slug")]


def ping_indexnow(urls: list[str], api_key: str, dry_run: bool = False) -> None:
    """Submit URLs to IndexNow (Bing, Yandex, Naver)."""
    if not urls:
        log.info("IndexNow: no URLs to submit")
        return

    if dry_run:
        log.info("IndexNow (dry-run): would submit %d URLs", len(urls))
        for u in urls[:5]:
            log.info("  %s", u)
        if len(urls) > 5:
            log.info("  ... and %d more", len(urls) - 5)
        return

    payload = {
        "host": "araverus.com",
        "key": api_key,
        "keyLocation": f"{SITE}/{api_key}.txt",
        "urlList": urls,
    }

    try:
        resp = httpx.post(INDEXNOW_ENDPOINT, json=payload, timeout=30)
        if resp.status_code in (200, 202):
            log.info("IndexNow: submitted %d URLs (HTTP %d)", len(urls), resp.status_code)
        else:
            log.warning("IndexNow: HTTP %d — %s", resp.status_code, resp.text[:200])
    except httpx.HTTPError as e:
        log.error("IndexNow request failed: %s", e)


def ping_websub(feed_url: str, dry_run: bool = False) -> None:
    """Ping Google's WebSub hub to notify of RSS feed update."""
    if dry_run:
        log.info("WebSub (dry-run): would ping hub for %s", feed_url)
        return

    try:
        resp = httpx.post(
            WEBSUB_HUB,
            data={
                "hub.mode": "publish",
                "hub.url": feed_url,
            },
            timeout=30,
        )
        if resp.status_code == 204:
            log.info("WebSub: hub notified for %s", feed_url)
        else:
            log.warning("WebSub: HTTP %d — %s", resp.status_code, resp.text[:200])
    except httpx.HTTPError as e:
        log.error("WebSub request failed: %s", e)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-5s %(message)s",
        datefmt="%H:%M:%S",
    )

    args = parse_args()

    # Load env — try scripts/.env.local first, then project root
    env_path = Path(".env.local")
    if not env_path.exists():
        env_path = Path(__file__).resolve().parent.parent / ".env.local"
    load_dotenv(env_path)

    # IndexNow API key
    indexnow_key = os.getenv("INDEXNOW_API_KEY", "")
    if not indexnow_key and not args.dry_run:
        log.warning("INDEXNOW_API_KEY not set — skipping IndexNow")

    # Supabase client
    from supabase import create_client
    sb = create_client(
        os.getenv("NEXT_PUBLIC_SUPABASE_URL"),
        os.getenv("SUPABASE_SERVICE_ROLE_KEY"),
    )

    # Fetch recent article URLs
    slugs = fetch_recent_slugs(sb, args.hours)
    urls = [f"{SITE}/news/{slug}" for slug in slugs]
    log.info("Found %d articles in last %dh", len(urls), args.hours)

    # Also include static pages that change daily
    urls.extend([
        f"{SITE}/news",
        f"{SITE}/sitemap.xml",
    ])

    # 1. IndexNow → Bing, Yandex, Naver
    if indexnow_key or args.dry_run:
        ping_indexnow(urls, indexnow_key, dry_run=args.dry_run)

    # 2. WebSub → Google
    ping_websub(RSS_FEED_URL, dry_run=args.dry_run)

    log.info("Done!")


if __name__ == "__main__":
    main()
