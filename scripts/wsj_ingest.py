#!/usr/bin/env python3
"""
WSJ RSS Feed Ingestion Pipeline.

Fetches all 6 WSJ RSS feeds, saves to Supabase with deduplication,
and exports unprocessed items to JSONL for the ML pipeline.

Usage:
    # Ingest all feeds to Supabase
    python scripts/wsj_ingest.py

    # Export unprocessed items to JSONL
    python scripts/wsj_ingest.py --export

    # Mark items as processed
    python scripts/wsj_ingest.py --mark-processed output/wsj_items.jsonl

Environment:
    SUPABASE_URL - Supabase project URL
    SUPABASE_SERVICE_ROLE_KEY - Service role key for DB access
"""
import hashlib
import json
import math
import os
import sys
from collections import Counter
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Optional

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


@dataclass
class IngestResult:
    total_fetched: int = 0
    total_inserted: int = 0
    total_skipped: int = 0
    by_feed: dict = None
    errors: list = None

    def __post_init__(self):
        if self.by_feed is None:
            self.by_feed = {}
        if self.errors is None:
            self.errors = []


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
    from urllib.parse import urlparse, urlunparse
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
        from urllib.parse import urlparse
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
        SKIP_CATEGORIES = ['/lifestyle/', '/real-estate/', '/arts/', '/health/', '/style/', '/livecoverage/', '/arts-culture/', '/buyside/', '/sports/', '/opinion/']
        if any(cat in link for cat in SKIP_CATEGORIES):
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
    import time

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

def insert_wsj_item(supabase: Client, item: WsjItem) -> bool:
    """Insert WSJ item into Supabase. Returns True if inserted, False if duplicate."""
    slug = generate_slug(item.title)

    try:
        supabase.table('wsj_items').insert({
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
        }).execute()
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
                    supabase.table('wsj_items').insert({
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
                    }).execute()
                    return True
                except Exception:
                    pass
            return False
        raise


def get_unprocessed_items(supabase: Client, limit: int = 500) -> list[dict]:
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


def mark_items_searched(supabase: Client, ids: list[str]) -> int:
    """Mark items as searched. Returns count of updated items."""
    if not ids:
        return 0

    response = supabase.table('wsj_items') \
        .update({
            'searched': True,
            'searched_at': datetime.utcnow().isoformat(),
        }) \
        .in_('id', ids) \
        .execute()

    return len(response.data) if response.data else 0


def mark_items_processed(supabase: Client, ids: list[str], batch_size: int = 100) -> int:
    """Mark items as processed in batches to avoid PostgREST URL length limits."""
    if not ids:
        return 0

    total_updated = 0
    for i in range(0, len(ids), batch_size):
        batch = ids[i:i + batch_size]
        response = supabase.table('wsj_items') \
            .update({
                'processed': True,
                'processed_at': datetime.utcnow().isoformat(),
            }) \
            .in_('id', batch) \
            .execute()
        total_updated += len(response.data) if response.data else 0

    return total_updated


def get_stats(supabase: Client) -> dict:
    """Get WSJ items statistics."""
    # Total count
    total_response = supabase.table('wsj_items').select('id', count='exact').execute()
    total = total_response.count or 0

    # Unprocessed count
    unprocessed_response = supabase.table('wsj_items') \
        .select('id', count='exact') \
        .eq('processed', False) \
        .execute()
    unprocessed = unprocessed_response.count or 0

    # By feed
    by_feed_response = supabase.table('wsj_items').select('feed_name').execute()
    by_feed = {}
    for item in (by_feed_response.data or []):
        feed = item['feed_name']
        by_feed[feed] = by_feed.get(feed, 0) + 1

    return {
        'total': total,
        'unprocessed': unprocessed,
        'processed': total - unprocessed,
        'by_feed': by_feed,
    }


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


def load_ids_from_file(file_path: Path) -> list[str]:
    """Load item IDs from JSONL or JSON file."""
    ids = []

    with open(file_path) as f:
        content = f.read().strip()

    # Try JSON format first (wsj_processed_ids.json style)
    if content.startswith('{'):
        data = json.loads(content)
        if 'ids' in data:
            return data['ids']
        if 'id' in data:
            return [data['id']]
        return []

    # JSONL format
    for line in content.split('\n'):
        if line.strip():
            item = json.loads(line)
            if 'id' in item:
                ids.append(item['id'])

    return ids


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
    CATEGORY_MERGE = {'BUSINESS': 'BUSINESS_MARKETS', 'MARKETS': 'BUSINESS_MARKETS'}
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

    result = IngestResult()
    result.total_fetched = len(items)
    result.errors = fetch_errors

    for item in items:
        feed = item.feed_name
        if feed not in result.by_feed:
            result.by_feed[feed] = {'fetched': 0, 'inserted': 0}
        result.by_feed[feed]['fetched'] += 1

        try:
            if insert_wsj_item(supabase, item):
                result.total_inserted += 1
                result.by_feed[feed]['inserted'] += 1
            else:
                result.total_skipped += 1
        except Exception as e:
            result.errors.append(f"Insert error: {e}")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total fetched:  {result.total_fetched}")
    print(f"Total inserted: {result.total_inserted}")
    print(f"Total skipped:  {result.total_skipped} (duplicates)")

    print("\nBy feed:")
    for feed, stats in sorted(result.by_feed.items()):
        print(f"  {feed}: {stats['inserted']}/{stats['fetched']} inserted")

    if result.errors:
        print(f"\nErrors ({len(result.errors)}):")
        for err in result.errors[:5]:
            print(f"  - {err}")

    # Show current stats
    stats = get_stats(supabase)
    print("\nDatabase stats:")
    print(f"  Total items: {stats['total']}")
    print(f"  Unprocessed: {stats['unprocessed']}")
    print(f"  Processed:   {stats['processed']}")


def cmd_export(output_path: Optional[Path] = None) -> None:
    """Export unsearched items to JSONL for Google News search."""
    print("=" * 60)
    print("Export Unsearched WSJ Items")
    print("=" * 60)

    supabase = get_supabase_client()
    items = get_unprocessed_items(supabase)

    if not items:
        print("No unsearched items to export.")
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


def cmd_mark_processed(file_path: Path) -> None:
    """Mark items from JSONL or JSON file as processed."""
    print("=" * 60)
    print("Mark Items as Processed")
    print("=" * 60)

    if not file_path.exists():
        print(f"Error: File not found: {file_path}")
        sys.exit(1)

    ids = load_ids_from_file(file_path)
    if not ids:
        print("No item IDs found in file.")
        return

    print(f"Found {len(ids)} item IDs in: {file_path}")

    supabase = get_supabase_client()
    updated = mark_items_processed(supabase, ids)

    print(f"Marked {updated} items as processed.")


def cmd_mark_processed_from_db() -> None:
    """Mark WSJ items as processed by querying wsj_crawl_results table.

    Finds all wsj_item_id values where crawl_status = 'success' AND relevance_flag = 'ok',
    then marks those items as processed in wsj_items table.

    NOTE: Only marks items with good quality content. Items with low_relevance or
    garbage status are NOT marked as processed so backups can be retried.
    """
    print("=" * 60)
    print("Mark Processed from DB (wsj_crawl_results)")
    print("=" * 60)

    supabase = get_supabase_client()

    # Query wsj_crawl_results for successful crawls with good relevance
    print("Querying wsj_crawl_results for quality crawls (success + ok relevance)...")
    response = supabase.table('wsj_crawl_results') \
        .select('wsj_item_id') \
        .eq('crawl_status', 'success') \
        .eq('relevance_flag', 'ok') \
        .not_.is_('wsj_item_id', 'null') \
        .execute()

    if not response.data:
        print("No quality crawls found in wsj_crawl_results.")
        return

    # Get unique wsj_item_ids
    wsj_ids = list(set(
        row['wsj_item_id'] for row in response.data
        if row.get('wsj_item_id')
    ))
    print(f"Found {len(wsj_ids)} unique WSJ items with quality crawls")

    if not wsj_ids:
        print("No valid wsj_item_id values found.")
        return

    # Mark as processed
    updated = mark_items_processed(supabase, wsj_ids)
    print(f"Marked {updated} items as processed in wsj_items.")


def cmd_mark_searched(jsonl_path: Path) -> None:
    """Mark WSJ items as searched based on exported JSONL file.

    After Google News search completes, this marks all items from the
    original export as 'searched' so they won't be searched again.
    """
    print("=" * 60)
    print("Mark Items as Searched")
    print("=" * 60)

    if not jsonl_path.exists():
        print(f"Error: File not found: {jsonl_path}")
        sys.exit(1)

    # Load IDs from JSONL
    ids = []
    with open(jsonl_path) as f:
        for line in f:
            if not line.strip():
                continue
            item = json.loads(line)
            if item.get('id'):
                ids.append(item['id'])

    if not ids:
        print("No item IDs found in file.")
        return

    print(f"Found {len(ids)} items in: {jsonl_path}")

    supabase = get_supabase_client()
    updated = mark_items_searched(supabase, ids)

    print(f"Marked {updated} items as searched.")


def wilson_lower_bound(success: int, total: int, z: float = 1.96) -> float:
    """Wilson score 95% CI lower bound."""
    if total == 0:
        return 0.0
    p = success / total
    denom = 1 + z * z / total
    center = p + z * z / (2 * total)
    spread = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total)
    return (center - spread) / denom


def cmd_update_domain_status() -> None:
    """Update wsj_domain_status table from wsj_crawl_results.

    Aggregates crawl results by domain and upserts to wsj_domain_status.
    Auto-blocks domains with:
    - fail_count > 5 AND success_rate < 20%, OR
    - llm_fail_count >= 3 (LLM detected wrong content)

    NOTE: 'garbage' and 'low_relevance' crawl statuses count as failures
    for domain quality assessment, since they indicate the domain
    consistently returns unusable content.
    """
    print("=" * 60)
    print("Update Domain Status from Crawl Results")
    print("=" * 60)

    supabase = get_supabase_client()

    # Query all crawl results with domain info
    print("Querying wsj_crawl_results...")
    response = supabase.table('wsj_crawl_results') \
        .select('resolved_domain, crawl_status, crawl_error, relevance_flag, relevance_score') \
        .not_.is_('resolved_domain', 'null') \
        .execute()

    if not response.data:
        print("No crawl results found.")
        return

    # Aggregate by domain
    # NOTE: Only count as success if crawl_status='success' AND relevance_flag='ok'
    # Count 'garbage', 'low_relevance', 'failed', 'error', 'resolve_failed' as failures
    domain_stats: dict = {}
    for row in response.data:
        domain = row.get('resolved_domain')
        if not domain:
            continue

        if domain not in domain_stats:
            domain_stats[domain] = {
                'success_count': 0,
                'fail_count': 0,
                'last_error': None,
                'relevance_scores': [],  # Track scores for avg calculation
            }

        crawl_status = row.get('crawl_status')
        relevance_flag = row.get('relevance_flag')
        relevance_score = row.get('relevance_score')

        # Only count as success if status='success' AND relevance='ok'
        if crawl_status == 'success' and relevance_flag == 'ok':
            domain_stats[domain]['success_count'] += 1
            # Track relevance score for weighted_score calculation
            if relevance_score is not None:
                domain_stats[domain]['relevance_scores'].append(relevance_score)
        elif crawl_status in ('failed', 'error', 'resolve_failed', 'garbage', 'low_relevance'):
            domain_stats[domain]['fail_count'] += 1
            domain_stats[domain]['last_error'] = row.get('crawl_error') or crawl_status
        elif crawl_status == 'success' and relevance_flag == 'low':
            # Old data: success with low relevance also counts as failure
            domain_stats[domain]['fail_count'] += 1
            domain_stats[domain]['last_error'] = 'low_relevance'

    print(f"Found {len(domain_stats)} unique domains")

    # Fetch existing llm_fail_count values
    llm_fail_response = supabase.table('wsj_domain_status') \
        .select('domain, llm_fail_count') \
        .execute()
    llm_fail_counts = {
        row['domain']: row.get('llm_fail_count', 0) or 0
        for row in llm_fail_response.data
    } if llm_fail_response.data else {}

    # Wilson Score thresholds for auto-blocking
    WILSON_THRESHOLD = 0.15
    MIN_ATTEMPTS = 5

    # Upsert to wsj_domain_status
    now = datetime.utcnow().isoformat()
    updated = 0
    blocked = 0

    for domain, stats in domain_stats.items():
        success = stats['success_count']
        fail = stats['fail_count']
        total = success + fail
        llm_fail = llm_fail_counts.get(domain, 0)

        # Calculate success rate
        success_rate = success / total if total > 0 else 0

        # Wilson Score: lower bound of 95% CI for true success rate
        wilson = wilson_lower_bound(success, total)

        # Auto-block if:
        # - Wilson lower bound < threshold with enough data, OR
        # - llm_fail >= 10 AND success_count < llm_fail * 3 (LLM failure rate > 25%)
        crawl_block = total >= MIN_ATTEMPTS and wilson < WILSON_THRESHOLD
        llm_block = llm_fail >= 10 and success < llm_fail * 3
        should_block = crawl_block or llm_block
        status = 'blocked' if should_block else 'active'

        if crawl_block:
            block_reason = f"Auto-blocked: wilson={wilson:.3f} < {WILSON_THRESHOLD} ({success}/{total}, {success_rate:.0%})"
        elif llm_block:
            llm_rate = llm_fail / (success + llm_fail) if (success + llm_fail) > 0 else 1
            block_reason = f"Auto-blocked: {llm_fail} LLM failures vs {success} successes ({llm_rate:.0%} LLM fail rate)"
        else:
            block_reason = None

        # Calculate weighted_score = avg_relevance_score * success_rate
        relevance_scores = stats.get('relevance_scores', [])
        avg_relevance = sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0
        weighted_score = avg_relevance * success_rate

        record = {
            'domain': domain,
            'status': status,
            'success_count': success,
            'fail_count': fail,
            'failure_type': stats['last_error'][:100] if stats['last_error'] else None,
            'block_reason': block_reason,
            'success_rate': round(success_rate, 4),
            'weighted_score': round(weighted_score, 4),
            'wilson_score': round(wilson, 4),
            'updated_at': now,
        }

        # Add timestamps based on status
        if success > 0:
            record['last_success'] = now
        if fail > 0:
            record['last_failure'] = now

        try:
            supabase.table('wsj_domain_status').upsert(
                record,
                on_conflict='domain'
            ).execute()
            updated += 1
            if should_block:
                blocked += 1
        except Exception as e:
            print(f"Error updating {domain}: {e}")

    print(f"\nUpdated {updated} domains in wsj_domain_status")
    print(f"Auto-blocked {blocked} domains (wilson < {WILSON_THRESHOLD} OR llm_fail ratio)")

    # Show blocked domains
    if blocked > 0:
        print("\nNewly blocked domains:")
        for domain, stats in domain_stats.items():
            success = stats['success_count']
            fail = stats['fail_count']
            total = success + fail
            rate = success / total if total > 0 else 0
            wilson = wilson_lower_bound(success, total)
            llm_fail = llm_fail_counts.get(domain, 0)
            crawl_blocked = total >= MIN_ATTEMPTS and wilson < WILSON_THRESHOLD
            llm_blocked = llm_fail >= 10 and success < llm_fail * 3
            if crawl_blocked or llm_blocked:
                reason = "LLM failures" if llm_blocked else "wilson score"
                print(f"  {domain}: wilson={wilson:.3f}, {rate:.0%} success ({success}/{total}), {llm_fail} llm_fail ({reason})")


def cmd_retry_low_relevance() -> None:
    """Reactivate backup articles for WSJ items with only low-relevance crawls.

    This command:
    1. Finds WSJ items that ONLY have low-relevance crawls (no good quality crawl)
    2. Reactivates their skipped backup articles (skipped → pending)
    3. Unmarks WSJ items as processed (so crawler will retry them)

    Use this after updating crawl_ranked.py to continue trying backups on low relevance.
    """
    print("=" * 60)
    print("Retry Low Relevance Items")
    print("=" * 60)

    supabase = get_supabase_client()

    # Step 1: Find WSJ items with low-relevance success but NO good success
    print("\n[1/4] Finding WSJ items with only low-relevance crawls...")

    # Get all WSJ item IDs that have at least one 'success' + 'ok' relevance
    good_response = supabase.table('wsj_crawl_results') \
        .select('wsj_item_id') \
        .eq('crawl_status', 'success') \
        .eq('relevance_flag', 'ok') \
        .not_.is_('wsj_item_id', 'null') \
        .execute()

    good_item_ids = set(
        row['wsj_item_id'] for row in (good_response.data or [])
        if row.get('wsj_item_id')
    )
    print(f"  WSJ items with good crawls: {len(good_item_ids)}")

    # Get all WSJ item IDs that have low-relevance crawls (success + low, or old low_relevance status)
    low_response = supabase.table('wsj_crawl_results') \
        .select('wsj_item_id') \
        .eq('crawl_status', 'success') \
        .eq('relevance_flag', 'low') \
        .not_.is_('wsj_item_id', 'null') \
        .execute()

    # Also check for old 'low_relevance' status records
    old_low_response = supabase.table('wsj_crawl_results') \
        .select('wsj_item_id') \
        .eq('crawl_status', 'low_relevance') \
        .not_.is_('wsj_item_id', 'null') \
        .execute()

    low_item_ids = set(
        row['wsj_item_id'] for row in (low_response.data or [])
        if row.get('wsj_item_id')
    )
    low_item_ids.update(
        row['wsj_item_id'] for row in (old_low_response.data or [])
        if row.get('wsj_item_id')
    )
    print(f"  WSJ items with low-relevance crawls: {len(low_item_ids)}")

    # Items to retry = have low relevance but NOT good quality
    items_to_retry = low_item_ids - good_item_ids
    print(f"  WSJ items needing retry: {len(items_to_retry)}")

    if not items_to_retry:
        print("\nNo items need retry. All low-relevance items already have a good crawl.")
        return

    # Step 2: Reactivate skipped backup articles for these items
    print(f"\n[2/4] Reactivating skipped backups for {len(items_to_retry)} items...")

    # Process in batches to avoid query limits
    items_list = list(items_to_retry)
    batch_size = 100
    total_reactivated = 0

    for i in range(0, len(items_list), batch_size):
        batch = items_list[i:i + batch_size]
        try:
            response = supabase.table('wsj_crawl_results') \
                .update({'crawl_status': 'pending', 'crawl_error': None}) \
                .eq('crawl_status', 'skipped') \
                .in_('wsj_item_id', batch) \
                .execute()
            total_reactivated += len(response.data) if response.data else 0
        except Exception as e:
            print(f"  Error updating batch: {e}")

    print(f"  Reactivated {total_reactivated} backup articles")

    # Step 3: Unmark WSJ items as processed
    print(f"\n[3/4] Unmarking {len(items_to_retry)} WSJ items as processed...")

    total_unmarked = 0
    for i in range(0, len(items_list), batch_size):
        batch = items_list[i:i + batch_size]
        try:
            response = supabase.table('wsj_items') \
                .update({'processed': False, 'processed_at': None}) \
                .in_('id', batch) \
                .execute()
            total_unmarked += len(response.data) if response.data else 0
        except Exception as e:
            print(f"  Error updating batch: {e}")

    print(f"  Unmarked {total_unmarked} WSJ items")

    # Step 4: Summary
    print("\n[4/4] Summary")
    print("=" * 60)
    print(f"WSJ items to retry: {len(items_to_retry)}")
    print(f"Backup articles reactivated: {total_reactivated}")
    print(f"WSJ items unmarked: {total_unmarked}")
    print("\nNext steps:")
    print("  1. Run: python scripts/crawl_ranked.py --update-db")
    print("  2. Run: python scripts/wsj_ingest.py --update-domain-status")


def cmd_seed_blocked_from_json() -> None:
    """One-time migration: seed blocked domains from JSON file to wsj_domain_status."""
    print("=" * 60)
    print("Seed Blocked Domains from JSON → DB")
    print("=" * 60)

    json_path = Path(__file__).parent / "data" / "blocked_domains.json"
    if not json_path.exists():
        print(f"Error: JSON file not found: {json_path}")
        sys.exit(1)

    with open(json_path) as f:
        data = json.load(f)

    blocked = data.get("blocked", {})
    if not blocked:
        print("No blocked domains found in JSON.")
        return

    print(f"Found {len(blocked)} blocked domains in JSON")

    supabase = get_supabase_client()
    now = datetime.utcnow().isoformat()
    inserted = 0

    for domain, info in blocked.items():
        reason = info.get("reason", "Migrated from JSON")
        try:
            supabase.table('wsj_domain_status').upsert(
                {
                    'domain': domain,
                    'status': 'blocked',
                    'block_reason': f"JSON migration: {reason}",
                    'updated_at': now,
                },
                on_conflict='domain',
            ).execute()
            inserted += 1
        except Exception as e:
            print(f"  Error inserting {domain}: {e}")

    print(f"Upserted {inserted}/{len(blocked)} domains to wsj_domain_status")


def cmd_stats() -> None:
    """Show current database statistics."""
    print("=" * 60)
    print("WSJ Items Statistics")
    print("=" * 60)

    supabase = get_supabase_client()
    stats = get_stats(supabase)

    print(f"Total items:   {stats['total']}")
    print(f"Unprocessed:   {stats['unprocessed']}")
    print(f"Processed:     {stats['processed']}")

    print("\nBy feed:")
    for feed, count in sorted(stats['by_feed'].items()):
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
        print("  --mark-searched FILE     Mark items in JSONL as searched")
        print("  --mark-processed FILE    Mark items in JSONL as processed")
        print("  --mark-processed-from-db Query wsj_crawl_results and mark processed")
        print("  --update-domain-status   Aggregate crawl results to wsj_domain_status")
        print("  --retry-low-relevance    Reactivate backups for low-relevance items")
        print("  --seed-blocked-from-json  One-time: migrate JSON blocked domains to DB")
        print("  --stats                  Show database statistics")
        return

    if not args:
        cmd_ingest()
        return

    if args[0] == '--seed-blocked-from-json':
        cmd_seed_blocked_from_json()
    elif args[0] == '--export':
        output_path = Path(args[1]) if len(args) > 1 else None
        cmd_export(output_path)
    elif args[0] == '--mark-searched':
        if len(args) < 2:
            print("Error: --mark-searched requires a JSONL file path")
            sys.exit(1)
        cmd_mark_searched(Path(args[1]))
    elif args[0] == '--mark-processed':
        if len(args) < 2:
            print("Error: --mark-processed requires a JSONL file path")
            sys.exit(1)
        cmd_mark_processed(Path(args[1]))
    elif args[0] == '--mark-processed-from-db':
        cmd_mark_processed_from_db()
    elif args[0] == '--update-domain-status':
        cmd_update_domain_status()
    elif args[0] == '--retry-low-relevance':
        cmd_retry_low_relevance()
    elif args[0] == '--stats':
        cmd_stats()
    else:
        cmd_ingest()


if __name__ == "__main__":
    main()
