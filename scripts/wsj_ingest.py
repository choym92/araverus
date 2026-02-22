#!/usr/bin/env python3
"""
Phase 1 · Step 1 · RSS Ingest — WSJ RSS Feed Ingestion Pipeline.

Fetches all 6 WSJ RSS feeds, saves to Supabase with deduplication,
and exports unprocessed items to JSONL for the ML pipeline.

Usage:
    # Ingest all feeds to Supabase
    python scripts/wsj_ingest.py

    # Export unprocessed items to JSONL
    python scripts/wsj_ingest.py --export

Environment:
    SUPABASE_URL - Supabase project URL
    SUPABASE_SERVICE_ROLE_KEY - Service role key for DB access
"""
import hashlib
import json
import os
import sys
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse, urlunparse
import xml.etree.ElementTree as ET
from dataclasses import dataclass

import httpx
from dotenv import load_dotenv
from supabase import create_client, Client

from utils.slug import generate_slug

# Load environment variables from .env.local
load_dotenv(Path(__file__).parent.parent / '.env.local')

# ============================================================
# WSJ Feed Configuration
# ============================================================

WSJ_FEEDS = [
    {'name': 'WORLD', 'url': 'https://feeds.content.dowjones.io/public/rss/RSSWorldNews'},
    {'name': 'BUSINESS', 'url': 'https://feeds.content.dowjones.io/public/rss/WSJcomUSBusiness'},
    {'name': 'MARKETS', 'url': 'https://feeds.content.dowjones.io/public/rss/RSSMarketsMain'},
    {'name': 'TECH', 'url': 'https://feeds.content.dowjones.io/public/rss/RSSWSJD'},
    {'name': 'POLITICS', 'url': 'https://feeds.content.dowjones.io/public/rss/socialpoliticsfeed'},
    {'name': 'ECONOMY', 'url': 'https://feeds.content.dowjones.io/public/rss/socialeconomyfeed'},
]

# Rate limit: seconds between feed fetches
FETCH_DELAY = 0.5

# Merge separate BUSINESS and MARKETS feeds into a single category
CATEGORY_MERGE = {'BUSINESS': 'BUSINESS_MARKETS', 'MARKETS': 'BUSINESS_MARKETS'}

# URL paths skipped at parse time (poor crawl success rates or off-topic)
SKIP_URL_PATHS = frozenset([
    '/lifestyle/', '/real-estate/', '/arts/', '/health/', '/style/',
    '/livecoverage/', '/arts-culture/', '/buyside/', '/sports/', '/opinion/',
])

# ============================================================
# Data Types
# ============================================================

@dataclass
class WsjItem:
    feed_name: str
    feed_url: str
    title: str
    description: Optional[str]
    link: str
    creator: Optional[str]
    url_hash: str
    published_at: Optional[str]
    subcategory: Optional[str] = None



# ============================================================
# Supabase Client
# ============================================================

def get_supabase_client() -> Client:
    """Create Supabase client from environment variables."""
    url = os.getenv('NEXT_PUBLIC_SUPABASE_URL') or os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

    if not url or not key:
        raise ValueError(
            "Missing Supabase credentials. Set NEXT_PUBLIC_SUPABASE_URL and "
            "SUPABASE_SERVICE_ROLE_KEY in .env.local"
        )

    return create_client(url, key)


# ============================================================
# RSS Parsing
# ============================================================

def generate_url_hash(url: str) -> str:
    """Generate SHA-256 hash of URL for deduplication. Strips query params to avoid duplicates."""
    parsed = urlparse(url)
    clean = urlunparse((parsed.scheme, parsed.netloc, parsed.path, '', '', ''))
    return hashlib.sha256(clean.encode()).hexdigest()


def parse_rss_date(date_str: str) -> Optional[str]:
    """Parse RSS date format to ISO string."""
    if not date_str:
        return None
    try:
        dt = parsedate_to_datetime(date_str)
        return dt.isoformat()
    except Exception:
        return None


def safe_text(el) -> str:
    """Safely extract text from XML element."""
    return (el.text or "").strip() if el is not None else ""


# URL path → feed_name mapping (overrides RSS feed_name when URL is more specific)
URL_CATEGORY_MAP = {
    'tech': 'TECH',
    'finance': 'BUSINESS_MARKETS',
    'business': 'BUSINESS_MARKETS',
    'markets': 'BUSINESS_MARKETS',
    'personal-finance': 'BUSINESS_MARKETS',
    'science': 'TECH',
    'economy': 'ECONOMY',
    'politics': 'POLITICS',
    'world': 'WORLD',
}

# URL paths that are ambiguous — don't override RSS feed_name
AMBIGUOUS_PATHS = {'articles', 'buyside', 'us-news'}


def extract_category_from_url(link: str) -> tuple[Optional[str], Optional[str]]:
    """Extract (category, subcategory) from WSJ article URL path.

    Examples:
        wsj.com/tech/ai/article-slug → ('TECH', 'ai')
        wsj.com/economy/trade/slug   → ('ECONOMY', 'trade')
        wsj.com/articles/slug        → (None, None)  # ambiguous

    Returns:
        (mapped_category, subcategory) or (None, None) for ambiguous/unknown paths
    """
    try:
        path = urlparse(link).path.strip('/')
        parts = path.split('/')
        if not parts:
            return None, None

        top_path = parts[0].lower()

        if top_path in AMBIGUOUS_PATHS:
            return None, None

        category = URL_CATEGORY_MAP.get(top_path)
        if category is None:
            return None, None

        # Subcategory only exists when URL has 3+ segments: /category/subcategory/article-slug
        # With only 2 segments (/category/article-slug), parts[1] is the article itself
        subcategory = parts[1] if len(parts) >= 3 and parts[1] not in AMBIGUOUS_PATHS else None
        return category, subcategory
    except Exception:
        return None, None


def parse_wsj_rss(xml_text: str, feed_name: str, feed_url: str) -> list[WsjItem]:
    """Parse WSJ RSS XML into WsjItem objects."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        print(f"  [ERROR] XML parse error: {e}")
        return []

    # Dublin Core namespace for dc:creator
    namespaces = {'dc': 'http://purl.org/dc/elements/1.1/'}

    items = []
    for item in root.findall('.//item'):
        title = safe_text(item.find('title'))
        link = safe_text(item.find('link'))

        if not title or not link:
            continue

        # Skip opinion articles (cross-posted from Opinion feed)
        if title.startswith('Opinion |'):
            continue

        # Skip roundup/digest posts (no real article content)
        if 'Roundup: Market Talk' in title:
            continue

        # Skip low-value categories (poor crawl success rates)
        if any(cat in link for cat in SKIP_URL_PATHS):
            continue

        # Extract category/subcategory from URL (more accurate than RSS feed_name)
        url_category, subcategory = extract_category_from_url(link)
        item_feed_name = url_category if url_category else feed_name
        # Fallback: use feed_name as subcategory when URL doesn't provide one
        if subcategory is None:
            subcategory = item_feed_name.lower().replace('_', '-')

        # Extract dc:creator (author)
        creator_el = item.find('dc:creator', namespaces)
        creator = safe_text(creator_el) if creator_el is not None else None

        items.append(WsjItem(
            feed_name=item_feed_name,
            feed_url=feed_url,
            title=title,
            description=safe_text(item.find('description')),
            link=link,
            creator=creator,
            url_hash=generate_url_hash(link),
            published_at=parse_rss_date(safe_text(item.find('pubDate'))),
            subcategory=subcategory,
        ))

    return items


# ============================================================
# Feed Fetching
# ============================================================

def fetch_wsj_feed(client: httpx.Client, feed: dict) -> tuple[list[WsjItem], Optional[str]]:
    """Fetch a single WSJ RSS feed. Returns (items, error_message)."""
    try:
        response = client.get(feed['url'], timeout=10.0)
        response.raise_for_status()
        items = parse_wsj_rss(response.text, feed['name'], feed['url'])
        return items, None
    except httpx.HTTPStatusError as e:
        return [], f"HTTP {e.response.status_code}"
    except httpx.RequestError as e:
        return [], str(e)
    except Exception as e:
        return [], str(e)


def fetch_all_wsj_feeds() -> tuple[list[WsjItem], list[str]]:
    """Fetch all WSJ RSS feeds. Returns (all_items, errors)."""
    all_items = []
    errors = []

    with httpx.Client(
        headers={'User-Agent': 'FinanceBriefBot/1.0 (contact@araverus.com)'}
    ) as client:
        for i, feed in enumerate(WSJ_FEEDS):
            print(f"  [{i+1}/{len(WSJ_FEEDS)}] Fetching {feed['name']}...", end=' ')

            items, error = fetch_wsj_feed(client, feed)

            if error:
                print(f"ERROR: {error}")
                errors.append(f"[{feed['name']}] {error}")
            else:
                print(f"{len(items)} items")
                all_items.extend(items)

            # Rate limit
            if i < len(WSJ_FEEDS) - 1:
                time.sleep(FETCH_DELAY)

    return all_items, errors


# ============================================================
# Supabase Operations
# ============================================================

def _build_insert_row(item: WsjItem, slug: str) -> dict:
    """Build the DB row dict for a WsjItem."""
    return {
        'feed_name': item.feed_name,
        'feed_url': item.feed_url,
        'title': item.title,
        'description': item.description,
        'link': item.link,
        'creator': item.creator,
        'url_hash': item.url_hash,
        'published_at': item.published_at,
        'subcategory': item.subcategory,
        'slug': slug,
    }


def insert_wsj_item(supabase: Client, item: WsjItem) -> bool:
    """Insert WSJ item into Supabase. Returns True if inserted, False if duplicate."""
    slug = generate_slug(item.title)

    try:
        supabase.table('wsj_items').insert(_build_insert_row(item, slug)).execute()
        return True
    except Exception as e:
        error_str = str(e)
        # Check for unique constraint violation (duplicate url_hash or slug)
        if '23505' in error_str or 'duplicate' in error_str.lower():
            # If slug collision, retry with date suffix
            if 'slug' in error_str.lower() and item.published_at:
                from utils.slug import generate_unique_slug
                slug = generate_unique_slug(item.title, item.published_at, set())
                try:
                    supabase.table('wsj_items').insert(
                        _build_insert_row(item, slug)
                    ).execute()
                    return True
                except Exception:
                    pass
            return False
        raise


def get_unsearched_items(supabase: Client, limit: int = 500) -> list[dict]:
    """Get WSJ items that need Google search.

    Only returns items where:
    - searched = false (not yet searched/resolved)

    Items with searched=true are already in wsj_crawl_results
    and only need crawling (use --from-db for that).
    """
    response = supabase.table('wsj_items') \
        .select('*') \
        .eq('searched', False) \
        .order('published_at', desc=True) \
        .limit(limit) \
        .execute()
    return response.data or []


# ============================================================
# Export / Import
# ============================================================

def export_to_jsonl(items: list[dict], output_path: Path) -> None:
    """Export items to JSONL file."""
    with open(output_path, 'w') as f:
        for item in items:
            # Format for pipeline compatibility
            export_item = {
                'id': item['id'],
                'title': item['title'],
                'description': item['description'],
                'link': item['link'],
                'pubDate': item['published_at'],
                'feed_name': item['feed_name'],
                'creator': item['creator'],
                'subcategory': item.get('subcategory'),
                'extracted_entities': item.get('extracted_entities'),
                'extracted_keywords': item.get('extracted_keywords'),
                'extracted_tickers': item.get('extracted_tickers'),
                'llm_search_queries': item.get('llm_search_queries'),
            }
            f.write(json.dumps(export_item, ensure_ascii=False) + '\n')


# ============================================================
# Main Commands
# ============================================================

def dedup_by_title(items: list[WsjItem]) -> list[WsjItem]:
    """Deduplicate items by title with least-count category balancing.

    WSJ cross-posts the same article across multiple RSS feeds (e.g. MARKETS,
    BUSINESS, TECH). When a duplicate is found, the article is assigned to
    whichever category currently has fewer articles, naturally balancing
    the distribution across categories.
    """
    category_counts: dict[str, int] = Counter()
    seen_titles: dict[str, WsjItem] = {}

    for item in items:
        if item.title not in seen_titles:
            seen_titles[item.title] = item
            category_counts[item.feed_name] += 1
        else:
            existing = seen_titles[item.title]
            if category_counts[item.feed_name] < category_counts[existing.feed_name]:
                category_counts[existing.feed_name] -= 1
                seen_titles[item.title] = item
                category_counts[item.feed_name] += 1

    return list(seen_titles.values())


def cmd_ingest() -> None:
    """Ingest all WSJ feeds to Supabase."""
    print("=" * 60)
    print("WSJ RSS Feed Ingestion")
    print("=" * 60)

    # Fetch all feeds
    print("\n[1/4] Fetching RSS feeds...")
    items, fetch_errors = fetch_all_wsj_feeds()
    print(f"\nTotal items fetched: {len(items)}")

    if not items:
        print("No items to insert.")
        return

    # Merge BUSINESS + MARKETS into BUSINESS_MARKETS
    print("\n[2/4] Merging categories...")
    for item in items:
        if item.feed_name in CATEGORY_MERGE:
            item.feed_name = CATEGORY_MERGE[item.feed_name]
    merged_counts = Counter(item.feed_name for item in items)
    for cat, count in merged_counts.most_common():
        print(f"  {cat}: {count}")

    # Deduplicate by title (same article cross-posted to multiple feeds)
    print("\n[3/4] Deduplicating by title...")
    before = len(items)
    items = dedup_by_title(items)
    dupes = before - len(items)
    print(f"  Removed {dupes} cross-feed duplicates ({before} → {len(items)})")

    # Insert to Supabase
    print("\n[4/4] Inserting to Supabase...")
    supabase = get_supabase_client()

    inserted = 0
    skipped = 0
    errors = list(fetch_errors)
    by_feed: dict[str, dict] = {}

    for item in items:
        feed = item.feed_name
        if feed not in by_feed:
            by_feed[feed] = {'fetched': 0, 'inserted': 0}
        by_feed[feed]['fetched'] += 1

        try:
            if insert_wsj_item(supabase, item):
                inserted += 1
                by_feed[feed]['inserted'] += 1
            else:
                skipped += 1
        except Exception as e:
            errors.append(f"Insert error: {e}")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total fetched:  {len(items)}")
    print(f"Total inserted: {inserted}")
    print(f"Total skipped:  {skipped} (duplicates)")

    print("\nBy feed:")
    for feed, stats in sorted(by_feed.items()):
        print(f"  {feed}: {stats['inserted']}/{stats['fetched']} inserted")

    if errors:
        print(f"\nErrors ({len(errors)}):")
        for err in errors[:5]:
            print(f"  - {err}")



def cmd_export(output_path: Optional[Path] = None, export_all: bool = False) -> None:
    """Export WSJ items to JSONL for Google News search.

    Args:
        output_path: Custom output path (default: output/wsj_items.jsonl)
        export_all: If True, export all recent items regardless of searched status
    """
    print("=" * 60)
    print(f"Export WSJ Items {'(all recent)' if export_all else '(unsearched only)'}")
    print("=" * 60)

    supabase = get_supabase_client()

    if export_all:
        # Export all items from last 2 days, ignoring searched flag
        cutoff = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        response = supabase.table('wsj_items') \
            .select('*') \
            .gte('published_at', cutoff) \
            .order('published_at', desc=True) \
            .limit(500) \
            .execute()
        items = response.data or []
    else:
        items = get_unsearched_items(supabase)

    if not items:
        print("No items to export.")
        return

    # Default output path
    if output_path is None:
        output_path = Path(__file__).parent / 'output' / 'wsj_items.jsonl'

    output_path.parent.mkdir(exist_ok=True)
    export_to_jsonl(items, output_path)

    print(f"Exported {len(items)} items to: {output_path}")

    # Show feed breakdown
    by_feed = {}
    for item in items:
        feed = item['feed_name']
        by_feed[feed] = by_feed.get(feed, 0) + 1

    print("\nBy feed:")
    for feed, count in sorted(by_feed.items()):
        print(f"  {feed}: {count}")


# ============================================================
# CLI Entry Point
# ============================================================

def main():
    args = sys.argv[1:]

    if args and args[0] == '--help':
        print(__doc__)
        print("\nCommands:")
        print("  (default)                Ingest all WSJ feeds to Supabase")
        print("  --export [PATH]          Export unsearched items to JSONL")
        print("  --export --all [PATH]    Export all recent items (bypass searched flag)")
        return

    if not args:
        cmd_ingest()
        return

    if args[0] == '--export':
        export_all = '--all' in args
        remaining = [a for a in args[1:] if a != '--all']
        output_path = Path(remaining[0]) if remaining else None
        cmd_export(output_path, export_all=export_all)
    else:
        cmd_ingest()


if __name__ == "__main__":
    main()
