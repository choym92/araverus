#!/usr/bin/env python3
"""
WSJ RSS to Google News search pipeline.

Takes WSJ RSS items and searches Google News for related free articles.
Uses multi-query strategy for better candidate generation.

Usage:
    # Read from Supabase export (default)
    python scripts/wsj_to_google_news.py [--limit N]

    # Read from local XML file (legacy)
    python scripts/wsj_to_google_news.py --xml [--limit N]

    # Specify custom JSONL input
    python scripts/wsj_to_google_news.py --input path/to/items.jsonl

Options:
    --limit N         Process only N items (default: all)
    --delay-item S    Delay between items in seconds (default: 2.0)
    --delay-query S   Delay between queries in seconds (default: 1.0)
    --xml             Use legacy XML file instead of JSONL
    --input PATH      Specify custom JSONL input file
"""
import asyncio
import hashlib
import json
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import timedelta
from email.utils import parsedate_to_datetime
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus, urlparse

import httpx
from dotenv import load_dotenv

# Load environment variables
load_dotenv(Path(__file__).parent.parent / '.env.local')

# Import shared domain utilities
sys.path.insert(0, str(Path(__file__).parent))
from domain_utils import load_blocked_domains as _load_blocked_domains_from_db

# Google News RSS search URL
GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"

# Source name to domain mapping (for blocklist matching)
SOURCE_NAME_TO_DOMAIN = {
    'the wall street journal': 'wsj.com',
    'wall street journal': 'wsj.com',
    'wsj': 'wsj.com',
    'reuters': 'reuters.com',
    'bloomberg': 'bloomberg.com',
    'bloomberg news': 'bloomberg.com',
    'financial times': 'ft.com',
    'ft': 'ft.com',
    'the new york times': 'nytimes.com',
    'new york times': 'nytimes.com',
    'nytimes': 'nytimes.com',
}

# Additional sources to always exclude (not crawlable or low quality)
EXCLUDED_SOURCES = {
    '富途牛牛',  # Futu - aggregator, not original content
}


def is_non_english_source(source_name: str) -> bool:
    """Check if source name contains non-Latin characters (likely non-English)."""
    if not source_name:
        return False
    # Check for non-ASCII characters that aren't common punctuation
    for char in source_name:
        # Allow ASCII (Latin letters, numbers, punctuation)
        if ord(char) > 127:
            # Allow common extended Latin characters (accents, etc.)
            # But block Arabic, Chinese, Japanese, Korean, Hebrew, etc.
            if ord(char) > 687:  # Beyond extended Latin
                return True
    return False


def safe_text(el) -> str:
    """Safely extract text from XML element."""
    return (el.text or "").strip() if el is not None else ""


def normalize_domain(url: str) -> str:
    """Extract domain from URL, removing www. prefix."""
    try:
        host = urlparse(url).netloc.lower()
        return host[4:] if host.startswith("www.") else host
    except Exception:
        return ""


def dedupe_key(article: dict) -> str:
    """Generate deduplication key from title + source."""
    text = f"{article.get('title', '')}|{article.get('source', '')}".lower()
    return hashlib.md5(text.encode()).hexdigest()


@lru_cache(maxsize=1)
def load_blocked_domains() -> frozenset[str]:
    """Load blocked domains from DB (cached)."""
    blocked = _load_blocked_domains_from_db()
    print(f"  Loaded {len(blocked)} blocked domains from DB")
    return frozenset(blocked)


def is_source_blocked(source_name: str, source_domain: str) -> bool:
    """Check if source is blocked by domain or known name mapping."""
    # Check non-English sources first (e.g., Arabic, Chinese, etc.)
    if is_non_english_source(source_name):
        return True

    # Check excluded sources
    if source_name in EXCLUDED_SOURCES:
        return True

    blocked_domains = load_blocked_domains()

    # Check domain directly
    if source_domain and source_domain in blocked_domains:
        return True

    # Check source name mapping
    source_lower = source_name.lower()
    if source_lower in SOURCE_NAME_TO_DOMAIN:
        mapped_domain = SOURCE_NAME_TO_DOMAIN[source_lower]
        if mapped_domain in blocked_domains:
            return True

    return False


def is_newsletter_title(title: str) -> bool:
    """Detect newsletter/roundup style titles that won't search well."""
    indicators = [
        r'^plus,',  # "Plus, hospitals embrace AI..."
        r'\bplus\b.*\band\b.*\band\b',  # Multiple "and" with "plus"
        r':\s*what to expect',  # Roundup style
        r'the best .* from',  # "The Best Stuff From..."
        r'\d+ things',  # "5 Things to Know"
    ]
    title_lower = title.lower()
    return any(re.search(p, title_lower) for p in indicators)


def build_queries(
    title: str,
    description: str,
    llm_queries: list[str] | None = None,
) -> list[str]:
    """
    Build search queries using LLM-generated queries when available,
    falling back to clean title.

    Args:
        title: WSJ article title
        description: WSJ article description
        llm_queries: Pre-generated search queries from wsj_preprocess.py
    """
    clean_title = re.sub(
        r'\s*[-|]\s*(WSJ|Wall Street Journal).*$', '', title, flags=re.IGNORECASE
    ).strip()

    # Newsletters rely entirely on LLM queries (titles are not searchable)
    if is_newsletter_title(title) and llm_queries:
        return llm_queries[:3]

    queries = [clean_title]

    if llm_queries:
        for q in llm_queries[:3]:
            if q not in queries:
                queries.append(q)

    return queries[:4]


def parse_rss_date(date_str: str):
    """Parse RSS date format (RFC 2822 or ISO). Returns datetime or None."""
    if not date_str:
        return None
    try:
        # Try RFC 2822 first (e.g., "Sun, 05 Jan 2025 10:30:00 GMT")
        return parsedate_to_datetime(date_str)
    except Exception:
        pass
    try:
        # Try ISO format (e.g., "2025-01-05T10:30:00+00:00")
        from datetime import datetime
        # Handle various ISO formats
        if date_str.endswith('Z'):
            date_str = date_str[:-1] + '+00:00'
        return datetime.fromisoformat(date_str)
    except Exception:
        return None


def load_wsj_jsonl(jsonl_path: str, today_only: bool = False) -> list[dict]:
    """Load WSJ items from JSONL file (exported from Supabase).

    Deduplicates by title using least-count category balancing: when a
    duplicate is found, it is assigned to whichever category currently has
    fewer articles.

    Args:
        jsonl_path: Path to JSONL file
        today_only: If True, only include items published today (default: False)

    Note: Date filtering for Google News results happens via add_date_filter(),
    which uses WSJ pubDate to create an appropriate date range for search results.
    """
    from collections import Counter
    from datetime import date

    today = date.today()

    category_counts: Counter = Counter()
    items_by_title: dict[str, dict] = {}

    with open(jsonl_path) as f:
        for line in f:
            if not line.strip():
                continue

            item = json.loads(line)
            title = item.get('title', '')
            title_lower = title.lower().strip()

            # Filter by publish date if today_only
            if today_only:
                pub_date = parse_rss_date(item.get('pubDate', ''))
                if pub_date is None or pub_date.date() != today:
                    continue

            feed_name = item.get('feed_name', '')

            if title_lower not in items_by_title:
                items_by_title[title_lower] = item
                category_counts[feed_name] += 1
            else:
                existing = items_by_title[title_lower]
                existing_feed = existing.get('feed_name', '')
                if category_counts[feed_name] < category_counts[existing_feed]:
                    category_counts[existing_feed] -= 1
                    items_by_title[title_lower] = item
                    category_counts[feed_name] += 1

    # Build result list
    items = []
    for item in items_by_title.values():
        items.append({
            'id': item.get('id'),
            'title': item.get('title', ''),
            'description': item.get('description', ''),
            'link': item.get('link', ''),
            'pubDate': item.get('pubDate', ''),
            'creator': item.get('creator'),
            'feed_name': item.get('feed_name'),
            'subcategory': item.get('subcategory'),
        })

    return items


def parse_wsj_rss(xml_path: str, skip_opinion: bool = True) -> list[dict]:
    """Parse WSJ RSS XML file with deduplication and optional opinion filtering."""
    tree = ET.parse(xml_path)
    root = tree.getroot()

    # Dublin Core namespace for dc:creator
    namespaces = {'dc': 'http://purl.org/dc/elements/1.1/'}

    items = []
    seen_titles = set()

    for item in root.findall('.//item'):
        title = safe_text(item.find('title'))

        # Skip duplicates (same title)
        title_lower = title.lower().strip()
        if title_lower in seen_titles:
            continue
        seen_titles.add(title_lower)

        # Skip opinion pieces if requested
        if skip_opinion and title.startswith('Opinion |'):
            continue

        # Extract dc:creator (author) - may be None
        creator_el = item.find('dc:creator', namespaces)
        creator = safe_text(creator_el) if creator_el is not None else None

        items.append({
            'title': title,
            'description': safe_text(item.find('description')),
            'link': safe_text(item.find('link')),
            'pubDate': safe_text(item.find('pubDate')),
            'creator': creator,
        })

    return items


async def search_google_news(query: str, client: httpx.AsyncClient) -> list[dict]:
    """Search Google News RSS, extracting source URL for domain matching."""
    url = GOOGLE_NEWS_RSS.format(query=quote_plus(query))

    try:
        response = await client.get(url, timeout=10.0)
        response.raise_for_status()

        root = ET.fromstring(response.text)

        articles = []
        for item in root.findall('.//item'):
            source_el = item.find('source')
            source_name = safe_text(source_el)
            source_url = source_el.attrib.get("url", "") if source_el is not None else ""
            source_domain = normalize_domain(source_url)

            articles.append({
                'title': safe_text(item.find('title')),
                'link': safe_text(item.find('link')),
                'source': source_name,
                'source_url': source_url,
                'source_domain': source_domain,
                'pubDate': safe_text(item.find('pubDate')),
            })

        return articles

    except ET.ParseError as e:
        print(f"    XML Parse Error for query '{query[:50]}': {e}")
        return []
    except Exception as e:
        print(f"    Error: {e}")
        return []


def add_date_filter(query: str, after_date=None, date_mode: str = "3d") -> str:
    """Add date filter to Google News query to reduce response size.

    Args:
        query: The search query
        after_date: WSJ publish date for date-range filtering
        date_mode: "3d", "7d", or "none" for fallback levels

    Google News RSS supports:
    - after:YYYY-MM-DD / before:YYYY-MM-DD for specific date ranges
    - when:7d / when:3d for relative time windows
    """
    if date_mode == "none":
        return query

    if after_date and date_mode == "3d":
        # WSJ pubDate -1 day to +3 days (5-day window)
        start = (after_date.date() - timedelta(days=1)).isoformat()
        end = (after_date.date() + timedelta(days=4)).isoformat()  # +3 days needs before:+4
        return f"{query} after:{start} before:{end}"
    elif after_date and date_mode == "7d":
        # Wider window: -3 day to +4 days (7-day window)
        start = (after_date.date() - timedelta(days=3)).isoformat()
        end = (after_date.date() + timedelta(days=4)).isoformat()
        return f"{query} after:{start} before:{end}"

    # Relative fallback
    if date_mode == "7d":
        return f"{query} when:7d"
    return f"{query} when:3d"


def format_query_with_exclusions(query: str) -> str:
    """Add -site:wsj.com to exclude paywalled WSJ results."""
    # Don't add if already has site: operator
    if 'site:' in query.lower():
        return query
    return f"{query} -site:wsj.com"


async def search_multi_query(
    queries: list[str],
    client: httpx.AsyncClient,
    after_date=None,
    delay_query: float = 1.0,
) -> tuple[list[dict], dict]:
    """
    Search with multiple queries, union results, dedupe, and filter.

    Args:
        queries: List of search queries to try
        client: HTTP client for requests
        after_date: WSJ publish date for date filtering
        delay_query: Delay between queries in seconds

    Returns:
        tuple of (articles, instrumentation_dict)
    """
    all_articles = []
    seen_keys = set()
    instrumentation = {
        'queries_executed': [],
    }

    # Helper to add article with deduplication and date filtering
    def add_article(article: dict) -> bool:
        if is_source_blocked(article.get('source', ''), article.get('source_domain', '')):
            return False
        key = dedupe_key(article)
        if key in seen_keys:
            return False

        if after_date:
            article_date = parse_rss_date(article['pubDate'])
            if article_date is None:
                return False
            wsj_date = after_date.date()
            article_dt = article_date.date()
            # Allow -1 to +3 days from WSJ pub date
            if article_dt < wsj_date - timedelta(days=1) or article_dt > wsj_date + timedelta(days=3):
                return False

        seen_keys.add(key)
        all_articles.append(article)
        return True

    for i, query in enumerate(queries):
        # Add exclusions
        query_with_excl = format_query_with_exclusions(query)

        # Date filter strategy:
        # Q1 (i=0): 7-day window - full title, broad but recent
        # Q2 (i=1): 7-day window - keywords, catches lexical mismatches
        # Q3+ (i>=2): 3-day window - description keywords, tighter filter
        if i >= 2:
            filtered_query = add_date_filter(query_with_excl, after_date, date_mode="3d")
        else:
            filtered_query = add_date_filter(query_with_excl, after_date, date_mode="7d")

        t0 = time.perf_counter()
        articles = await search_google_news(filtered_query, client)
        elapsed = time.perf_counter() - t0

        added_count = sum(1 for a in articles if add_article(a))

        instrumentation['queries_executed'].append({
            'query': filtered_query[:80],
            'results': len(articles),
            'added': added_count,
            'time': round(elapsed, 2),
        })
        print(f"      Q{i+1}: +{added_count} new articles ({len(articles)} total)")

        if i < len(queries) - 1:
            await asyncio.sleep(delay_query)

    return all_articles, instrumentation


async def main():
    limit = None  # Process all by default
    delay_item = 2.0
    delay_query = 1.0
    use_xml = False
    custom_input = None

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == '--limit' and i + 1 < len(args):
            limit = int(args[i + 1])
            i += 2
        elif arg == '--delay-item' and i + 1 < len(args):
            delay_item = float(args[i + 1])
            i += 2
        elif arg == '--delay-query' and i + 1 < len(args):
            delay_query = float(args[i + 1])
            i += 2
        elif arg == '--delay' and i + 1 < len(args):  # Legacy support
            delay_item = float(args[i + 1])
            i += 2
        elif arg == '--xml':
            use_xml = True
            i += 1
        elif arg == '--input' and i + 1 < len(args):
            custom_input = Path(args[i + 1])
            i += 2
        else:
            i += 1

    # Determine input source
    if custom_input:
        # Custom JSONL input
        if not custom_input.exists():
            print(f"Error: Input file not found: {custom_input}")
            sys.exit(1)
        wsj_items = load_wsj_jsonl(custom_input)
        print(f"Loaded {len(wsj_items)} WSJ items from: {custom_input}")
    elif use_xml:
        # Legacy XML input
        rss_path = Path(__file__).parent / 'data' / 'wsj-tech-rss.xml'
        if not rss_path.exists():
            print(f"Error: RSS file not found at {rss_path}")
            sys.exit(1)
        wsj_items = parse_wsj_rss(rss_path)
        print(f"Loaded {len(wsj_items)} WSJ items from XML: {rss_path}")
    else:
        # Default: JSONL from Supabase export
        jsonl_path = Path(__file__).parent / 'output' / 'wsj_items.jsonl'
        if not jsonl_path.exists():
            print(f"Error: JSONL export not found at {jsonl_path}")
            print("Run 'python scripts/wsj_ingest.py --export' first, or use --xml for legacy mode.")
            sys.exit(1)
        wsj_items = load_wsj_jsonl(jsonl_path)
        print(f"Loaded {len(wsj_items)} WSJ items from: {jsonl_path}")

    if not wsj_items:
        print("No WSJ items to process.")
        sys.exit(0)

    # Apply limit
    if limit:
        wsj_items = wsj_items[:limit]

    print(f"\nProcessing {len(wsj_items)} items | delay_item={delay_item}s | delay_query={delay_query}s\n")

    results = []
    all_instrumentation = []
    processed_ids = []  # Track IDs for marking processed later

    async with httpx.AsyncClient() as client:
        for i, wsj in enumerate(wsj_items):
            print("=" * 80)
            print(f"[{i+1}/{len(wsj_items)}] WSJ: {wsj['title']}")
            print(f"    {wsj['description'][:100]}...")

            # Date filter: only articles from same day as WSJ publish date
            wsj_date = parse_rss_date(wsj['pubDate'])

            # Build search queries (prefer LLM-generated, fall back to title)
            llm_queries = wsj.get('llm_search_queries') or None
            queries = build_queries(wsj['title'], wsj['description'], llm_queries=llm_queries)
            print(f"    Queries ({len(queries)}):")
            for j, q in enumerate(queries):
                print(f"      Q{j+1}: {q[:70]}{'...' if len(q) > 70 else ''}")

            # Search with all queries
            articles, instr = await search_multi_query(
                queries, client, wsj_date, delay_query
            )
            print(f"    Found: {len(articles)} articles")

            # Show top 5
            for j, art in enumerate(articles[:5]):
                print(f"      [{j+1}] {art['source']}: {art['title'][:50]}...")

            results.append({
                'wsj': wsj,
                'queries': queries,
                'google_news': articles,
            })
            all_instrumentation.append({
                'wsj_title': wsj['title'],
                'instrumentation': instr,
            })

            # Track ID for marking processed
            if wsj.get('id'):
                processed_ids.append(wsj['id'])

            if i < len(wsj_items) - 1:
                await asyncio.sleep(delay_item)

    # Filter results: keep only items with at least 1 article found
    results_with_articles = [r for r in results if len(r['google_news']) > 0]
    results_no_articles = [r for r in results if len(r['google_news']) == 0]

    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")

    total_articles = sum(len(r['google_news']) for r in results_with_articles)
    print(f"WSJ items processed: {len(results)}")
    print(f"  - With articles: {len(results_with_articles)}")
    print(f"  - No articles found: {len(results_no_articles)}")
    print(f"Total articles found: {total_articles}")

    if results_no_articles:
        print("\nSkipped (0 articles):")
        for r in results_no_articles:
            print(f"  - {r['wsj']['title'][:70]}...")

    # Save results
    output_dir = Path(__file__).parent / 'output'
    output_dir.mkdir(exist_ok=True)

    # JSONL for post-processing (only items with articles)
    jsonl_path = output_dir / 'wsj_google_news_results.jsonl'
    with open(jsonl_path, 'w') as f:
        for r in results_with_articles:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')

    # TXT for debugging/reading (only items with articles)
    txt_path = output_dir / 'wsj_google_news_results.txt'
    with open(txt_path, 'w') as f:
        for r in results_with_articles:
            f.write(f"WSJ: {r['wsj']['title']}\n")
            f.write(f"Queries: {r['queries']}\n")
            f.write(f"Found {len(r['google_news'])} articles:\n")
            for art in r['google_news']:
                f.write(f"  - [{art['source']}] {art['title']}\n")
                f.write(f"    {art['link']}\n")
            f.write("\n")

    # Save instrumentation
    instr_path = output_dir / 'wsj_instrumentation.jsonl'
    with open(instr_path, 'w') as f:
        for item in all_instrumentation:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')

    # Save processed IDs for marking in Supabase
    if processed_ids:
        ids_path = output_dir / 'wsj_processed_ids.json'
        with open(ids_path, 'w') as f:
            json.dump({'ids': processed_ids, 'count': len(processed_ids)}, f, indent=2)

    print("\nResults saved to:")
    print(f"  {jsonl_path}")
    print(f"  {txt_path}")
    print(f"  {instr_path}")
    if processed_ids:
        print(f"  {ids_path}")
        print("\nTo mark items as processed in Supabase:")
        print(f"  python scripts/wsj_ingest.py --mark-processed {jsonl_path}")


if __name__ == "__main__":
    asyncio.run(main())
