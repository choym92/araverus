#!/usr/bin/env python3
"""
WSJ RSS Feed Ingestion Pipeline.

Fetches all 7 WSJ RSS feeds, saves to Supabase with deduplication,
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
import os
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Optional

import httpx
from dotenv import load_dotenv
from supabase import create_client, Client

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
    """Generate SHA-256 hash of URL for deduplication."""
    return hashlib.sha256(url.encode()).hexdigest()


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

        # Extract dc:creator (author)
        creator_el = item.find('dc:creator', namespaces)
        creator = safe_text(creator_el) if creator_el is not None else None

        items.append(WsjItem(
            feed_name=feed_name,
            feed_url=feed_url,
            title=title,
            description=safe_text(item.find('description')),
            link=link,
            creator=creator,
            url_hash=generate_url_hash(link),
            published_at=parse_rss_date(safe_text(item.find('pubDate'))),
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
        }).execute()
        return True
    except Exception as e:
        # Check for unique constraint violation (duplicate url_hash)
        if '23505' in str(e) or 'duplicate' in str(e).lower():
            return False
        raise


def get_unsearched_items(supabase: Client, limit: int = 500) -> list[dict]:
    """Get WSJ items that haven't been searched on Google News yet."""
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


def mark_items_processed(supabase: Client, ids: list[str]) -> int:
    """Mark items as processed. Returns count of updated items."""
    if not ids:
        return 0

    response = supabase.table('wsj_items') \
        .update({
            'processed': True,
            'processed_at': datetime.utcnow().isoformat(),
        }) \
        .in_('id', ids) \
        .execute()

    return len(response.data) if response.data else 0


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

def cmd_ingest() -> None:
    """Ingest all WSJ feeds to Supabase."""
    print("=" * 60)
    print("WSJ RSS Feed Ingestion")
    print("=" * 60)

    # Fetch all feeds
    print("\n[1/2] Fetching RSS feeds...")
    items, fetch_errors = fetch_all_wsj_feeds()
    print(f"\nTotal items fetched: {len(items)}")

    if not items:
        print("No items to insert.")
        return

    # Insert to Supabase
    print("\n[2/2] Inserting to Supabase...")
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
    print(f"\nDatabase stats:")
    print(f"  Total items: {stats['total']}")
    print(f"  Unprocessed: {stats['unprocessed']}")
    print(f"  Processed:   {stats['processed']}")


def cmd_export(output_path: Optional[Path] = None) -> None:
    """Export unsearched items to JSONL for Google News search."""
    print("=" * 60)
    print("Export Unsearched WSJ Items")
    print("=" * 60)

    supabase = get_supabase_client()
    items = get_unsearched_items(supabase)

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

    Finds all wsj_item_id values where crawl_status = 'success',
    then marks those items as processed in wsj_items table.
    """
    print("=" * 60)
    print("Mark Processed from DB (wsj_crawl_results)")
    print("=" * 60)

    supabase = get_supabase_client()

    # Query wsj_crawl_results for successful crawls
    print("Querying wsj_crawl_results for successful crawls...")
    response = supabase.table('wsj_crawl_results') \
        .select('wsj_item_id') \
        .eq('crawl_status', 'success') \
        .not_.is_('wsj_item_id', 'null') \
        .execute()

    if not response.data:
        print("No successful crawls found in wsj_crawl_results.")
        return

    # Get unique wsj_item_ids
    wsj_ids = list(set(
        row['wsj_item_id'] for row in response.data
        if row.get('wsj_item_id')
    ))
    print(f"Found {len(wsj_ids)} unique WSJ items with successful crawls")

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


def cmd_update_domain_status() -> None:
    """Update wsj_domain_status table from wsj_crawl_results.

    Aggregates crawl results by domain and upserts to wsj_domain_status.
    Auto-blocks domains with: fail_count > 5 AND success_rate < 20%
    """
    print("=" * 60)
    print("Update Domain Status from Crawl Results")
    print("=" * 60)

    supabase = get_supabase_client()

    # Query all crawl results with domain info
    print("Querying wsj_crawl_results...")
    response = supabase.table('wsj_crawl_results') \
        .select('resolved_domain, crawl_status, crawl_error') \
        .not_.is_('resolved_domain', 'null') \
        .execute()

    if not response.data:
        print("No crawl results found.")
        return

    # Aggregate by domain
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
            }

        if row.get('crawl_status') == 'success':
            domain_stats[domain]['success_count'] += 1
        elif row.get('crawl_status') in ('failed', 'error'):
            domain_stats[domain]['fail_count'] += 1
            domain_stats[domain]['last_error'] = row.get('crawl_error')

    print(f"Found {len(domain_stats)} unique domains")

    # Upsert to wsj_domain_status
    now = datetime.utcnow().isoformat()
    updated = 0
    blocked = 0

    for domain, stats in domain_stats.items():
        success = stats['success_count']
        fail = stats['fail_count']
        total = success + fail

        # Calculate success rate
        success_rate = success / total if total > 0 else 0

        # Determine status: auto-block if fail > 5 AND success_rate < 20%
        should_block = fail > 5 and success_rate < 0.2
        status = 'blocked' if should_block else 'active'
        block_reason = f"Auto-blocked: {fail} failures, {success_rate:.0%} success rate" if should_block else None

        record = {
            'domain': domain,
            'status': status,
            'success_count': success,
            'fail_count': fail,
            'failure_type': stats['last_error'][:100] if stats['last_error'] else None,
            'block_reason': block_reason,
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
    print(f"Auto-blocked {blocked} domains (fail > 5 AND success < 20%)")

    # Show blocked domains
    if blocked > 0:
        print("\nNewly blocked domains:")
        for domain, stats in domain_stats.items():
            success = stats['success_count']
            fail = stats['fail_count']
            total = success + fail
            rate = success / total if total > 0 else 0
            if fail > 5 and rate < 0.2:
                print(f"  {domain}: {fail} fails, {rate:.0%} success")


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
        print("  --stats                  Show database statistics")
        return

    if not args:
        cmd_ingest()
        return

    if args[0] == '--export':
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
    elif args[0] == '--stats':
        cmd_stats()
    else:
        cmd_ingest()


if __name__ == "__main__":
    main()
