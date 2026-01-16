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
import html
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus, urlparse

import httpx
from dotenv import load_dotenv
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

# Load environment variables
load_dotenv(Path(__file__).parent.parent / '.env.local')

# Path to blocked domains file (auto-updated by crawler)
BLOCKED_DOMAINS_FILE = Path(__file__).parent / "data" / "blocked_domains.json"

# Google News RSS search URL
GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"

# Use sklearn's stopwords (318 words)
STOP_WORDS = set(ENGLISH_STOP_WORDS)

# Vague verbs to exclude from entity extraction
VAGUE_VERBS = {
    'says', 'said', 'warns', 'warning', 'seeking', 'looking', 'wants',
    'gets', 'got', 'makes', 'made', 'takes', 'took', 'gives', 'gave',
    'sees', 'saw', 'shows', 'shown', 'finds', 'found', 'reports',
    'announces', 'reveals', 'suggests', 'indicates', 'expects',
    'plans', 'aims', 'tries', 'attempts', 'considers', 'explores',
    'edged', 'ahead', 'enough', 'back', 'groove', 'three', 'reasons',
}

# Noise entities to skip
NOISE_ENTITIES = {
    'wsj', 'wall street journal', 'the wall street journal',
    'reuters', 'bloomberg', 'associated press', 'ap',
}

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

# Preferred domains - confirmed crawlable, will be ranked higher in results
# Add more domains here as we confirm they work
PREFERRED_DOMAINS = [
    'livemint.com',  # Often has WSJ syndicated content
    'marketwatch.com',
    'finance.yahoo.com',
    'cnbc.com',
    'finviz.com',
    'hindustantimes.com',
]

# Event keywords with priority (higher = more important)
EVENT_PRIORITY = {
    'lawsuit': 10, 'sued': 10, 'suing': 10, 'settle': 10, 'settlement': 10,
    'acquisition': 9, 'deal': 9, 'merger': 9, 'takeover': 9, 'buyout': 9,
    'ban': 8, 'banned': 8, 'block': 8, 'blocked': 8, 'restrict': 8,
    'ipo': 7, 'debut': 7, 'trading': 7,
    'raising': 6, 'raised': 6, 'funding': 6, 'valuation': 6,
    'launch': 5, 'launched': 5, 'unveil': 5, 'unveiled': 5, 'release': 5,
    'cut': 4, 'cuts': 4, 'cutting': 4, 'slash': 4, 'slashing': 4,
}


def safe_text(el) -> str:
    """Safely extract text from XML element."""
    return (el.text or "").strip() if el is not None else ""


def clean_html(s: str) -> str:
    """Remove HTML tags and unescape entities."""
    s = html.unescape(s or "")
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


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


def _load_blocked_domains_from_json() -> set[str]:
    """Load blocked domains from local JSON file."""
    blocked = set()
    if BLOCKED_DOMAINS_FILE.exists():
        with open(BLOCKED_DOMAINS_FILE) as f:
            data = json.load(f)
            for domain in data.get("blocked", {}).keys():
                blocked.add(domain.lower())
    return blocked


def _load_blocked_domains_from_db() -> set[str]:
    """Load blocked domains from wsj_domain_status table in Supabase."""
    blocked = set()

    # Check for Supabase credentials
    url = os.getenv('NEXT_PUBLIC_SUPABASE_URL') or os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

    if not url or not key:
        # No credentials, skip DB query
        return blocked

    try:
        from supabase import create_client
        supabase = create_client(url, key)

        # Query blocked domains
        response = supabase.table('wsj_domain_status') \
            .select('domain') \
            .eq('status', 'blocked') \
            .execute()

        if response.data:
            for row in response.data:
                if row.get('domain'):
                    blocked.add(row['domain'].lower())

        print(f"  Loaded {len(blocked)} blocked domains from DB")
    except Exception as e:
        print(f"  Warning: Could not load blocked domains from DB: {e}")

    return blocked


@lru_cache(maxsize=1)
def load_blocked_domains() -> frozenset[str]:
    """Load blocked domains from JSON file + Supabase DB (cached)."""
    # Load from both sources
    blocked_json = _load_blocked_domains_from_json()
    blocked_db = _load_blocked_domains_from_db()

    # Combine (union)
    all_blocked = blocked_json | blocked_db

    print(f"  Total blocked domains: {len(all_blocked)} (JSON: {len(blocked_json)}, DB: {len(blocked_db)})")

    return frozenset(all_blocked)


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


def get_domain_priority(source_domain: str) -> int:
    """Get priority score for domain (lower = higher priority)."""
    if not source_domain:
        return 999

    # Check if domain matches any preferred domain
    for i, preferred in enumerate(PREFERRED_DOMAINS):
        if preferred in source_domain or source_domain in preferred:
            return i  # Lower index = higher priority

    return 100  # Non-preferred domains get low priority


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


def extract_core_entities(text: str) -> list[str]:
    """
    Extract high-quality named entities from text.
    Prioritizes: Company names, Person names, Product names, Acronyms
    """
    entities = []
    seen = set()

    # Known tech/finance companies (common in WSJ tech)
    known_companies = {
        'openai', 'google', 'meta', 'microsoft', 'apple', 'amazon', 'nvidia',
        'tesla', 'softbank', 'anthropic', 'xai', 'bytedance', 'tiktok',
        'alibaba', 'tencent', 'samsung', 'intel', 'amd', 'qualcomm',
        'oracle', 'ibm', 'salesforce', 'adobe', 'netflix', 'uber', 'lyft',
        'spacex', 'palantir', 'snowflake', 'databricks', 'stripe', 'coinbase',
    }

    # Find known companies in text (case-insensitive)
    text_lower = text.lower()
    for company in known_companies:
        if company in text_lower and company not in seen:
            # Get original casing from text
            match = re.search(rf'\b{company}\b', text, re.IGNORECASE)
            if match:
                entities.append(match.group(0))
                seen.add(company)

    # Multi-word proper nouns (e.g., "Jensen Huang", "Silicon Valley")
    multi_word = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b', text)
    for entity in multi_word:
        lower = entity.lower()
        if lower not in seen and lower not in NOISE_ENTITIES:
            entities.append(entity)
            seen.add(lower)

    # Acronyms (AI, CES, IPO, etc.) - but not common ones
    common_acronyms = {'US', 'UK', 'EU', 'CEO', 'CFO', 'CTO', 'GMT', 'EST', 'PST', 'AI'}
    acronyms = re.findall(r'\b([A-Z]{2,5})\b', text)
    for acr in acronyms:
        if acr not in seen and acr not in common_acronyms:
            entities.append(acr)
            seen.add(acr)

    # Single capitalized words (but be more selective)
    single_caps = re.findall(r'\b([A-Z][a-z]{2,})\b', text)
    for word in single_caps:
        lower = word.lower()
        if (lower not in seen and
            lower not in STOP_WORDS and
            lower not in VAGUE_VERBS and
            len(word) >= 4):  # Skip short words like "The", "New"
            entities.append(word)
            seen.add(lower)

    return entities


def extract_core_keywords(text: str, max_tokens: int = 6) -> list[str]:
    """
    Extract meaningful keywords (nouns/noun-phrases) for lexical-mismatch resilience.
    Returns list of significant words, prioritizing domain-relevant nouns.
    """
    # Domain-relevant noun patterns (tech/finance/business)
    domain_nouns = {
        'shopping', 'commerce', 'retail', 'retailers', 'platform', 'protocol',
        'agents', 'agent', 'chip', 'chips', 'memory', 'data', 'cloud', 'energy',
        'investment', 'funding', 'valuation', 'startup', 'acquisition', 'merger',
        'lawsuit', 'settlement', 'probe', 'ban', 'restriction', 'safety',
        'nuclear', 'solar', 'battery', 'electric', 'autonomous', 'robotics',
        'chatbot', 'model', 'training', 'inference', 'search', 'advertising',
    }

    words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
    keywords = []
    seen = set()

    # First pass: domain-relevant nouns
    for w in words:
        if w in domain_nouns and w not in seen:
            keywords.append(w)
            seen.add(w)

    # Second pass: other significant words (not stopwords, not vague verbs)
    for w in words:
        if (w not in seen and
            w not in STOP_WORDS and
            w not in VAGUE_VERBS and
            w not in NOISE_ENTITIES and
            len(w) >= 4):
            keywords.append(w)
            seen.add(w)

    return keywords[:max_tokens]


def build_queries(title: str, description: str) -> list[str]:
    """
    Build multiple search queries for better candidate generation.

    Strategy:
        Q1: Clean title (most reliable - news titles are search-optimized)
        Q2: Core keywords from title (4-6 tokens, lexical-mismatch resilient)
        Q3: Core keywords from description (if different from title)
        Q4: Entity + event/number (structured)
    """
    queries = []

    # Clean title (remove WSJ branding)
    clean_title = re.sub(r'\s*[-|]\s*(WSJ|Wall Street Journal).*$', '', title, flags=re.IGNORECASE)
    clean_title = clean_title.strip()

    # Check if this is a newsletter/roundup (harder to search)
    is_newsletter = is_newsletter_title(title)

    # Q1: Title as-is (most reliable for non-newsletters)
    if not is_newsletter:
        queries.append(clean_title)

    # Combine title + description for entity extraction
    title_clean = clean_html(title)
    desc_clean = clean_html(description)
    text = f"{title_clean} {desc_clean}"

    # Extract core entities (company names, proper nouns)
    entities = extract_core_entities(text)

    # Q2: Core keywords from TITLE (lexical-mismatch resilient)
    # e.g., "Google AI shopping agents retailers" instead of full title
    title_keywords = extract_core_keywords(title_clean, max_tokens=6)
    if len(title_keywords) >= 3:
        # Add primary entity if we have one
        if entities:
            q2_parts = [entities[0]] + [k for k in title_keywords if k.lower() != entities[0].lower()][:5]
        else:
            q2_parts = title_keywords
        q2 = ' '.join(q2_parts)
        if q2 not in queries and q2.lower() != clean_title.lower():
            queries.append(q2)

    # Q3: Core keywords from DESCRIPTION (often has synonyms/related terms)
    # e.g., "commerce platform protocol" when title says "shopping retailers"
    desc_keywords = extract_core_keywords(desc_clean, max_tokens=6)
    # Only add if description has different keywords than title
    desc_unique = [k for k in desc_keywords if k not in title_keywords]
    if len(desc_unique) >= 2:
        if entities:
            q3_parts = [entities[0]] + desc_unique[:4]
        else:
            q3_parts = desc_keywords[:5]
        q3 = ' '.join(q3_parts)
        if q3 not in queries:
            queries.append(q3)

    # Q4: Entity + event/number (structured, for specific matches)
    numbers = re.findall(
        r'\$?\d+(?:\.\d+)?\s*(?:billion|million|trillion|percent|%)',
        text, re.IGNORECASE
    )
    best_event = None
    best_priority = -1
    for word in re.findall(r'\b\w+\b', text.lower()):
        if word in EVENT_PRIORITY and EVENT_PRIORITY[word] > best_priority:
            best_event = word
            best_priority = EVENT_PRIORITY[word]

    if len(entities) >= 1 and (best_event or numbers):
        q4_parts = entities[:2].copy()
        if best_event:
            q4_parts.append(best_event)
        if numbers:
            q4_parts.append(numbers[0])
        q4 = ' '.join(q4_parts)
        if q4 not in queries:
            queries.append(q4)

    # For newsletters, add a simpler entity-only query
    if is_newsletter and entities:
        simple_q = ' '.join(entities[:3])
        if simple_q not in queries:
            queries.append(simple_q)

    # Ensure we have at least one query
    if not queries:
        queries.append(clean_title)

    return queries[:4]  # Limit to 4 queries max


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


# Feed priority for deduplication (higher = keep)
FEED_PRIORITY = {
    'MARKETS': 7,
    'ECONOMY': 6,
    'TECH': 5,
    'BUSINESS': 4,
    'WORLD': 3,
    'POLITICS': 2,
    'OPINION': 1,
}


def load_wsj_jsonl(jsonl_path: str, today_only: bool = True) -> list[dict]:
    """Load WSJ items from JSONL file (exported from Supabase).

    Deduplicates by title, keeping the item from the highest priority feed.
    Priority: MARKETS > ECONOMY > TECH > BUSINESS > WORLD > POLITICS > OPINION

    Args:
        jsonl_path: Path to JSONL file
        today_only: If True, only include items published today (default: True)
    """
    from datetime import date

    today = date.today()

    # First pass: collect all items, grouped by title
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
            priority = FEED_PRIORITY.get(feed_name, 0)

            # Keep item with highest priority feed
            if title_lower not in items_by_title:
                items_by_title[title_lower] = (priority, item)
            else:
                existing_priority, _ = items_by_title[title_lower]
                if priority > existing_priority:
                    items_by_title[title_lower] = (priority, item)

    # Second pass: build result list
    items = []
    for _, (_, item) in items_by_title.items():
        items.append({
            'id': item.get('id'),
            'title': item.get('title', ''),
            'description': item.get('description', ''),
            'link': item.get('link', ''),
            'pubDate': item.get('pubDate', ''),
            'creator': item.get('creator'),
            'feed_name': item.get('feed_name'),
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
        # WSJ pubDate -1 day to +2 days (4-day window)
        start = (after_date.date() - timedelta(days=1)).isoformat()
        end = (after_date.date() + timedelta(days=2)).isoformat()
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


def count_preferred_domain_hits(articles: list[dict]) -> dict:
    """Count hits per preferred domain."""
    hits = {d: 0 for d in PREFERRED_DOMAINS}
    for art in articles:
        domain = art.get('source_domain', '')
        for pref in PREFERRED_DOMAINS:
            if pref in domain or domain in pref:
                hits[pref] += 1
                break
    return hits


async def search_multi_query(
    queries: list[str],
    client: httpx.AsyncClient,
    after_date=None,
    delay_query: float = 1.0,
    core_keywords: list[str] = None,
) -> tuple[list[dict], dict]:
    """
    Search with multiple queries, union results, dedupe, and filter.

    Returns:
        tuple of (articles, instrumentation_dict)

    Features:
    - Adds -site:wsj.com to exclude paywalled results
    - Adds date filter (with fallback: 3d → 7d → none)
    - Filters blocked sources by domain
    - Preferred-domain site: fallback when recall is low
    """
    all_articles = []
    seen_keys = set()
    instrumentation = {
        'queries_executed': [],
        'preferred_domain_hits': {},
        'fallback_queries': [],
    }

    # Phase 1: Run global queries with -site:wsj.com
    for i, query in enumerate(queries):
        # Add exclusions
        query_with_excl = format_query_with_exclusions(query)

        # Date filter strategy:
        # Q1 (i=0): No date filter - full title, broadest recall
        # Q2 (i=1): No date filter - keywords, catches lexical mismatches
        # Q3+ (i>=2): Date filter - description keywords, more noise
        if i >= 2:
            filtered_query = add_date_filter(query_with_excl, after_date, date_mode="3d")
        else:
            filtered_query = query_with_excl

        t0 = time.perf_counter()
        articles = await search_google_news(filtered_query, client)
        elapsed = time.perf_counter() - t0

        # Track instrumentation
        instrumentation['queries_executed'].append({
            'query': filtered_query[:80],
            'results': len(articles),
            'time': round(elapsed, 2),
            'type': 'global',
        })
        print(f"    Q{i+1}: {elapsed:.2f}s, {len(articles)} results")

        for article in articles:
            if is_source_blocked(article.get('source', ''), article.get('source_domain', '')):
                continue
            key = dedupe_key(article)
            if key in seen_keys:
                continue
            seen_keys.add(key)

            if after_date:
                article_date = parse_rss_date(article['pubDate'])
                if article_date is None or article_date.date() != after_date.date():
                    continue

            all_articles.append(article)

        if i < len(queries) - 1:
            await asyncio.sleep(delay_query)

    # Check preferred domain coverage
    pref_hits = count_preferred_domain_hits(all_articles)
    instrumentation['preferred_domain_hits'] = pref_hits
    total_pref_hits = sum(pref_hits.values())

    # Phase 2: Preferred-domain fallback if recall is low
    # Trigger if: no preferred domain hits OR total results < 5
    if (total_pref_hits == 0 or len(all_articles) < 5) and core_keywords:
        print(f"    → Low recall ({len(all_articles)} articles, {total_pref_hits} preferred). Running targeted queries...")

        # Build core keyword query for site: searches
        kw_query = ' '.join(core_keywords[:5])

        # Try top 3 preferred domains
        for pref_domain in PREFERRED_DOMAINS[:3]:
            site_query = f"site:{pref_domain} {kw_query}"
            # Use wider date window for fallback
            filtered_query = add_date_filter(site_query, after_date, date_mode="7d")

            t0 = time.perf_counter()
            articles = await search_google_news(filtered_query, client)
            elapsed = time.perf_counter() - t0

            instrumentation['fallback_queries'].append({
                'query': filtered_query[:80],
                'domain': pref_domain,
                'results': len(articles),
                'time': round(elapsed, 2),
            })
            print(f"    site:{pref_domain}: {elapsed:.2f}s, {len(articles)} results")

            for article in articles:
                if is_source_blocked(article.get('source', ''), article.get('source_domain', '')):
                    continue
                key = dedupe_key(article)
                if key in seen_keys:
                    continue
                seen_keys.add(key)

                # Looser date filter for fallback
                if after_date:
                    article_date = parse_rss_date(article['pubDate'])
                    if article_date is None:
                        continue
                    # Same day only
                    if article_date.date() != after_date.date():
                        continue

                all_articles.append(article)

            await asyncio.sleep(delay_query)

        # Update preferred hits after fallback
        pref_hits = count_preferred_domain_hits(all_articles)
        instrumentation['preferred_domain_hits'] = pref_hits

    # Sort by domain priority (preferred domains first)
    all_articles.sort(key=lambda a: get_domain_priority(a.get('source_domain', '')))

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
            print(f"Run 'python scripts/wsj_ingest.py --export' first, or use --xml for legacy mode.")
            sys.exit(1)
        wsj_items = load_wsj_jsonl(jsonl_path)
        print(f"Loaded {len(wsj_items)} WSJ items from: {jsonl_path}")

    if not wsj_items:
        print("No WSJ items to process.")
        sys.exit(0)

    # Apply limit
    if limit:
        wsj_items = wsj_items[:limit]

    print(f"Processing {len(wsj_items)} items | delay_item={delay_item}s | delay_query={delay_query}s\n")

    results = []
    all_instrumentation = []
    processed_ids = []  # Track IDs for marking processed later

    async with httpx.AsyncClient() as client:
        for i, wsj in enumerate(wsj_items):
            print("=" * 80)
            print(f"[{i+1}] WSJ: {wsj['title']}")
            print(f"    {wsj['description'][:100]}...")

            # Date filter: only articles from same day as WSJ publish date
            wsj_date = parse_rss_date(wsj['pubDate'])

            # Build multiple queries
            queries = build_queries(wsj['title'], wsj['description'])
            print(f"    Queries ({len(queries)}):")
            for j, q in enumerate(queries):
                print(f"      Q{j+1}: {q[:70]}{'...' if len(q) > 70 else ''}")

            # Extract core keywords for fallback queries
            text = f"{clean_html(wsj['title'])} {clean_html(wsj['description'])}"
            core_keywords = extract_core_keywords(text, max_tokens=5)

            # Search with all queries
            articles, instr = await search_multi_query(
                queries, client, wsj_date, delay_query,
                core_keywords=core_keywords
            )
            print(f"    Found: {len(articles)} articles")

            # Show preferred domain hits
            pref_hits = instr.get('preferred_domain_hits', {})
            pref_with_hits = {k: v for k, v in pref_hits.items() if v > 0}
            if pref_with_hits:
                print(f"    Preferred domains: {pref_with_hits}")
            else:
                print(f"    Preferred domains: (none)")

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

    # Aggregate preferred domain stats
    agg_pref_hits = {d: 0 for d in PREFERRED_DOMAINS}
    total_fallback_queries = 0
    for instr_item in all_instrumentation:
        instr = instr_item.get('instrumentation', {})
        for domain, count in instr.get('preferred_domain_hits', {}).items():
            if domain in agg_pref_hits:
                agg_pref_hits[domain] += count
        total_fallback_queries += len(instr.get('fallback_queries', []))

    print(f"\nPreferred domain coverage:")
    for domain, count in agg_pref_hits.items():
        marker = "✓" if count > 0 else "✗"
        print(f"  {marker} {domain}: {count} articles")
    print(f"  Fallback queries executed: {total_fallback_queries}")

    if results_no_articles:
        print(f"\nSkipped (0 articles):")
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

    print(f"\nResults saved to:")
    print(f"  {jsonl_path}")
    print(f"  {txt_path}")
    print(f"  {instr_path}")
    if processed_ids:
        print(f"  {ids_path}")
        print(f"\nTo mark items as processed in Supabase:")
        print(f"  python scripts/wsj_ingest.py --mark-processed {jsonl_path}")


if __name__ == "__main__":
    asyncio.run(main())
