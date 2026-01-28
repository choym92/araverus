#!/usr/bin/env python3
"""
Crawl article content using hybrid approach: newspaper4k + crawl4ai fallback.

Features:
- HYBRID APPROACH: Try newspaper4k first (fast + metadata), fall back to browser
- Google News URL resolution
- newspaper4k: Fast HTTP fetch with author/date extraction
- crawl4ai fetch (basic/stealth/undetected) for protected sites
- HTML-first extraction via trafilatura (with crawl4ai fallback)
- Quality metrics + reason codes for debugging
- Section cutting to remove noise

Usage:
    python scripts/crawl_article.py <url> [mode] [--save]

Modes: basic, stealth, undetected (default: undetected)

As a module:
    from crawl_article import crawl_article
    result = await crawl_article("https://...")
    # result includes: extraction_method, authors, publish_date (when available)
"""
import asyncio
import base64
import json
import re
import sys
from dataclasses import dataclass, asdict
from datetime import date
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import httpx
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig

# Optional: trafilatura for better content extraction
try:
    import trafilatura
    HAS_TRAFILATURA = True
except ImportError:
    trafilatura = None
    HAS_TRAFILATURA = False

# Optional: newspaper4k for fast extraction with metadata
try:
    import newspaper
    HAS_NEWSPAPER4K = True
except ImportError:
    newspaper = None
    HAS_NEWSPAPER4K = False


# ============================================================================
# Quality Metrics
# ============================================================================

@dataclass
class QualityMetrics:
    """Content quality metrics for debugging and filtering."""
    char_len: int
    word_len: int
    line_count: int
    short_line_ratio: float  # Menu/nav indicator
    link_line_ratio: float   # Navigation indicator
    boilerplate_ratio: float # Noise indicator
    quality_score: float     # 0-1 overall score
    reason_code: Optional[str]  # TOO_SHORT, TOO_LONG, MENU_HEAVY, etc.

# Boilerplate keywords that indicate noise
BOILERPLATE_KEYWORDS = [
    "cookie", "privacy", "terms of service", "sign in", "subscribe",
    "newsletter", "all rights reserved", "advertisement", "related articles",
    "recommended for you", "most read", "more from", "sitemap", "contact us",
    "read next", "continue reading", "references", "acknowledgements",
]

# Section markers where we should cut content
SECTION_CUT_MARKERS = [
    r"^\s*#{1,3}\s*related\s*articles?\s*$",
    r"^\s*#{1,3}\s*read\s*next\s*$",
    r"^\s*#{1,3}\s*recommended\s*(for\s*you)?\s*$",
    r"^\s*#{1,3}\s*more\s*from\s+",
    r"^\s*#{1,3}\s*references\s*$",
    r"^\s*#{1,3}\s*citations?\s*$",
    r"^\s*#{1,3}\s*acknowledg(e)?ments?\s*$",
    r"^\s*\*\*read\s*next:?\*\*",
    r"^\s*mentioned\s*in\s*this\s*article",
    r"^\s*#{1,3}\s*latest\s*news\s*$",
    r"^\s*#{1,3}\s*topics?\s*$",
    r"^\s*explore\s*more\s*on\s*these\s*topics",
]


def _compute_quality(text: str) -> QualityMetrics:
    """Compute quality metrics for extracted content."""
    if not text:
        return QualityMetrics(0, 0, 0, 1.0, 0.0, 0.0, 0.0, "EMPTY")

    chars = len(text)
    words = len(text.split())
    lines = [ln for ln in text.split("\n") if ln.strip()]
    line_count = max(1, len(lines))

    # Short line ratio (menu/nav indicator)
    short_lines = sum(1 for ln in lines if len(ln.strip()) < 40)
    short_line_ratio = short_lines / line_count

    # Link line ratio (navigation indicator)
    link_lines = sum(1 for ln in lines if re.search(r"https?://|^\s*\[[^\]]+\]\([^)]+\)\s*$", ln))
    link_line_ratio = link_lines / line_count

    # Boilerplate ratio
    text_lower = text.lower()
    bp_hits = sum(1 for kw in BOILERPLATE_KEYWORDS if kw in text_lower)
    boilerplate_ratio = bp_hits / len(BOILERPLATE_KEYWORDS)

    # Quality score (0-1)
    # Prefer 800-15000 chars
    if 800 <= chars <= 15000:
        length_score = 1.0
    elif 400 <= chars < 800:
        length_score = 0.7
    elif 15000 < chars <= 30000:
        length_score = 0.7
    elif chars < 400:
        length_score = 0.3
    else:
        length_score = 0.4

    score = (
        0.40 * length_score
        + 0.25 * (1.0 - min(1.0, short_line_ratio))
        + 0.20 * (1.0 - min(1.0, link_line_ratio))
        + 0.15 * (1.0 - min(1.0, boilerplate_ratio))
    )
    score = max(0.0, min(1.0, score))

    # Determine reason code
    reason = None
    if chars < 350 or words < 60:
        reason = "TOO_SHORT"
    elif chars > 50000:
        reason = "TOO_LONG"
    elif link_line_ratio > 0.30:
        reason = "LINK_HEAVY"
    elif short_line_ratio > 0.55:
        reason = "MENU_HEAVY"
    elif boilerplate_ratio > 0.40:
        reason = "BOILERPLATE_HEAVY"

    return QualityMetrics(
        char_len=chars,
        word_len=words,
        line_count=line_count,
        short_line_ratio=round(short_line_ratio, 3),
        link_line_ratio=round(link_line_ratio, 3),
        boilerplate_ratio=round(boilerplate_ratio, 3),
        quality_score=round(score, 3),
        reason_code=reason,
    )


def _cut_at_section_markers(text: str) -> str:
    """Cut content at section markers like 'Related Articles', 'References'."""
    if not text:
        return text

    lines = text.split("\n")
    result = []

    for line in lines:
        stripped = line.strip().lower()

        # Check if this line matches a section cut marker
        should_cut = False
        for pattern in SECTION_CUT_MARKERS:
            if re.match(pattern, stripped, re.IGNORECASE):
                should_cut = True
                break

        if should_cut:
            break

        result.append(line)

    return "\n".join(result).strip()


def _extract_with_trafilatura(html: str, url: str = None) -> tuple[str, str]:
    """
    Extract main content using trafilatura.
    Returns (content, method) where method is 'trafilatura' or 'failed'.
    """
    if not HAS_TRAFILATURA or not html or not html.strip():
        return "", "no_trafilatura"

    try:
        content = trafilatura.extract(
            html,
            url=url,
            include_comments=False,
            include_tables=False,
            favor_precision=True,  # Prefer accuracy over recall
            output_format="txt",
        )
        if content and len(content) > 200:
            return content.strip(), "trafilatura"
    except Exception:
        pass

    return "", "trafilatura_failed"


# ============================================================================
# Google News URL Resolution
# ============================================================================

def is_google_news_url(url: str) -> bool:
    """Check if URL is a Google News redirect URL."""
    return "news.google.com" in url and "/articles/" in url


def decode_google_news_url_direct(google_url: str) -> str | None:
    """
    Strategy 1: Direct decode for old-format Google News URLs.
    Decodes the base64 article ID and extracts embedded URL.
    """
    try:
        match = re.search(r"/articles/([^/?]+)", google_url)
        if not match:
            return None

        encoded = match.group(1)
        # Convert URL-safe base64 to standard base64
        base64_str = encoded.replace("-", "+").replace("_", "/")
        # Add padding if needed
        padding = 4 - len(base64_str) % 4
        if padding != 4:
            base64_str += "=" * padding

        decoded = base64.b64decode(base64_str)
        content = decoded.decode("latin-1")

        # Check for protobuf prefix markers and strip
        prefix = bytes([0x08, 0x13, 0x22]).decode("latin-1")
        if content.startswith(prefix):
            content = content[len(prefix):]

        # Remove known suffix if present
        suffix = bytes([0xD2, 0x01, 0x00]).decode("latin-1")
        if content.endswith(suffix):
            content = content[:-len(suffix)]

        # Parse length byte and extract inner content
        length_byte = ord(content[0])
        if length_byte >= 0x80:
            content = content[2:length_byte + 2]
        else:
            content = content[1:length_byte + 1]

        # Check if this is new format that needs batchexecute API
        if content.startswith("AU_yqL"):
            return None  # Signal to use batchexecute

        # Old format: look for URL directly
        url_match = re.search(r"https?://[^\s\x00-\x1f\"<>]+", content)
        if url_match:
            return re.sub(r"[\x00-\x1f\x7f-\xff]+$", "", url_match.group(0))

        return None
    except Exception:
        return None


async def fetch_google_news_batchexecute(article_id: str, client: httpx.AsyncClient) -> str | None:
    """
    Strategy 2: Use Google's batchexecute API for new-format URLs.
    2-step process: fetch page for signature/timestamp, then call batchexecute.
    """
    try:
        # Step 1: Fetch article page to get signature and timestamp
        article_url = f"https://news.google.com/articles/{article_id}"
        resp = await client.get(article_url, follow_redirects=True)

        if resp.status_code != 200:
            return None

        html = resp.text

        # Extract signature and timestamp
        sig_match = re.search(r'data-n-a-sg="([^"]+)"', html)
        ts_match = re.search(r'data-n-a-ts="([^"]+)"', html)

        if not sig_match or not ts_match:
            return None

        signature = sig_match.group(1)
        timestamp = ts_match.group(1)

        # Step 2: Call batchexecute with signature and timestamp
        payload = json.dumps([
            [
                [
                    "Fbv4je",
                    json.dumps([
                        "garturlreq",
                        [
                            ["X", "X", ["X", "X"], None, None, 1, 1, "US:en", None, 1, None, None, None, None, None, 0, 1],
                            "X",
                            "X",
                            1,
                            [1, 1, 1],
                            1,
                            1,
                            None,
                            0,
                            0,
                            None,
                            0,
                        ],
                        article_id,
                        int(timestamp),
                        signature,
                    ]),
                ],
            ],
        ])

        batch_resp = await client.post(
            "https://news.google.com/_/DotsSplashUi/data/batchexecute?rpcids=Fbv4je",
            headers={
                "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                "Referer": "https://news.google.com/",
            },
            content=f"f.req={payload}",
        )

        if batch_resp.status_code != 200:
            return None

        text = batch_resp.text

        # Parse URL from response
        # Response format: ["garturlres","URL",1] but may be escaped inside JSON string
        # Pattern 1: Direct format
        url_match = re.search(r'\["garturlres","(https?:[^"]+)"', text)
        if url_match:
            url = url_match.group(1)
            url = url.replace("\\u003d", "=").replace("\\u0026", "&")
            return url

        # Pattern 2: Escaped format (inside JSON string)
        url_match = re.search(r'\[\\?"garturlres\\?",\\?"(https?:[^"\\]+)\\?"', text)
        if url_match:
            url = url_match.group(1)
            url = url.replace("\\u003d", "=").replace("\\u0026", "&")
            return url

        return None
    except Exception:
        return None


async def fetch_google_news_canonical(google_url: str, client: httpx.AsyncClient) -> str | None:
    """
    Strategy 3: Follow redirect and extract canonical URL from HTML.
    """
    try:
        resp = await client.get(google_url, follow_redirects=True)

        # If redirected to non-Google URL, that's our answer
        final_url = str(resp.url)
        if "news.google.com" not in final_url:
            return final_url

        html = resp.text

        # Try canonical URL
        canonical_match = re.search(
            r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)["\']',
            html, re.IGNORECASE
        )
        if canonical_match and "news.google.com" not in canonical_match.group(1):
            return canonical_match.group(1)

        # Try og:url
        og_match = re.search(
            r'<meta[^>]+property=["\']og:url["\'][^>]+content=["\']([^"\']+)["\']',
            html, re.IGNORECASE
        )
        if og_match and "news.google.com" not in og_match.group(1):
            return og_match.group(1)

        return None
    except Exception:
        return None


async def resolve_google_news_url(google_url: str) -> str | None:
    """
    Resolve a Google News URL to the actual article URL.
    Uses 3 strategies in order:
    1. Direct base64 decode (old format)
    2. batchexecute API (new format)
    3. Follow redirect / canonical URL
    """
    # Sanitize URL
    clean_url = google_url.strip()
    if re.search(r"\s", clean_url):
        return None  # Corrupted URL

    # Strategy 1: Direct decode
    decoded = decode_google_news_url_direct(clean_url)
    if decoded and "news.google.com" not in decoded:
        return decoded

    # Strategies 2 & 3 need HTTP client
    async with httpx.AsyncClient(
        timeout=15,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }
    ) as client:
        # Strategy 2: batchexecute API
        match = re.search(r"/articles/([^/?]+)", clean_url)
        if match:
            article_id = match.group(1)
            batch_url = await fetch_google_news_batchexecute(article_id, client)
            if batch_url and "news.google.com" not in batch_url:
                return batch_url

        # Strategy 3: Follow redirect / canonical
        canonical = await fetch_google_news_canonical(clean_url, client)
        if canonical:
            return canonical

    return None


# Blocked domains file path
BLOCKED_DOMAINS_FILE = Path(__file__).parent / "data" / "blocked_domains.json"


def load_blocked_domains() -> dict:
    """Load blocked domains from JSON file."""
    if BLOCKED_DOMAINS_FILE.exists():
        with open(BLOCKED_DOMAINS_FILE) as f:
            return json.load(f)
    return {"blocked": {}, "working": {}}


def save_blocked_domains(data: dict) -> None:
    """Save blocked domains to JSON file."""
    BLOCKED_DOMAINS_FILE.parent.mkdir(exist_ok=True)
    with open(BLOCKED_DOMAINS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def is_domain_blocked(domain: str) -> tuple[bool, str | None]:
    """Check if domain is in blocked list. Returns (is_blocked, reason)."""
    data = load_blocked_domains()
    for blocked_domain, info in data.get("blocked", {}).items():
        if blocked_domain in domain:
            return True, info.get("reason")
    return False, None


def log_crawl_result(domain: str, success: bool, status_code: int, content_length: int) -> None:
    """Log crawl result to blocked/working domains list.

    Only marks as blocked for actual HTTP blocks (401, 403, 429).
    200 with low content could be paywall/selector-mismatch/overlay - not blocked.
    """
    data = load_blocked_domains()
    today = date.today().isoformat()

    # Actual block: non-200 status codes that indicate blocking
    is_blocked = status_code in [401, 403, 429] or (not success and status_code not in [200, 302])

    if is_blocked:
        reason = f"Status {status_code}"
        data["blocked"][domain] = {"reason": reason, "tested": today}
        data["working"].pop(domain, None)
    elif success and content_length >= 500:
        # Good result: mark as working
        data["working"][domain] = {"tested": today}
        data["blocked"].pop(domain, None)
    # For 200 with low content: don't update lists (could be paywall/selector issue)

    save_blocked_domains(data)


# Domain-specific config for article extraction
# css_selector: targets article content directly (most effective)
# excluded_tags: removes noise elements
DOMAIN_CONFIG = {
    # Sites that need CSS selector (JS-heavy, complex structure)
    "cnn.com": {
        "css_selector": "h1, article, .article__content, .article-body",
    },
    "forbes.com": {
        "css_selector": "article, .article-body, .body-container",
    },
    "engadget.com": {
        "css_selector": "article, .caas-body",
    },
    # CNBC - use CSS selector for cleaner output
    "cnbc.com": {
        "css_selector": "article, .ArticleBody-articleBody, .RenderKeyPoints-list",
    },
    # Finviz - news aggregator with custom layout
    "finviz.com": {
        "css_selector": ".news-content, h1.title",
    },
    # Livemint - Indian business news (stable selectors, no hash-based classes)
    "livemint.com": {
        "css_selector": ".storyParagraph, h1",  # Works for both premium and non-premium
    },
    # Hindustan Times - Indian news
    "hindustantimes.com": {
        "css_selector": ".storyDetails, h1",
    },
    # The Guardian - UK news
    "theguardian.com": {
        "css_selector": "article, h1",  # Main article container
    },
    "reuters.com": {
        "excluded_tags": ["aside", "nav", "footer", "script", "style", "header"],
    },
    "wsj.com": {
        "excluded_tags": ["aside", "nav", "footer", "script", "style", "header"],
    },
    "bloomberg.com": {
        "excluded_tags": ["aside", "nav", "footer", "script", "style", "header"],
    },
    "marketwatch.com": {
        "excluded_tags": ["aside", "nav", "footer", "script", "style", "header"],
    },
    "finance.yahoo.com": {
        "excluded_tags": ["aside", "nav", "footer", "script", "style", "header"],
    },
    "seekingalpha.com": {
        "excluded_tags": ["aside", "nav", "footer", "script", "style", "header"],
    },
    "businessinsider.com": {
        "excluded_tags": ["aside", "nav", "footer", "script", "style", "header"],
    },
}

# Default: try common article selectors for unknown domains
DEFAULT_CSS_SELECTOR = "article, main, .article-body, .entry-content, .post-content"
DEFAULT_EXCLUDED_TAGS = ["aside", "nav", "footer", "script", "style", "header"]


def get_domain(url: str) -> str:
    """Extract domain from URL (e.g., 'www.cnbc.com' -> 'cnbc.com')."""
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    # Remove www. prefix
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def get_domain_config(url: str) -> dict | None:
    """Get domain-specific config, or None for unknown domains."""
    domain = get_domain(url)
    for key, config in DOMAIN_CONFIG.items():
        if key in domain:
            return config
    return None  # Unknown domain - will use fallback strategy


# ============================================================================
# Newspaper4k Fast Extraction (Hybrid Approach - Phase 1)
# ============================================================================

def _try_newspaper4k(url: str, domain: str, blocked_domains: set[str] = None, min_length: int = 300) -> dict | None:
    """
    Try fast extraction using newspaper4k.

    Returns dict with content if successful, None if failed.
    This is Phase 1 of the hybrid approach - fast HTTP fetch + extraction.

    Args:
        url: Article URL
        domain: Domain string for checking blocked list
        blocked_domains: Set of domains that require browser rendering (from DB)
        min_length: Minimum content length to consider successful

    Returns:
        dict with keys: success, title, markdown, markdown_length, authors, publish_date, extraction_method
        or None if extraction failed
    """
    if not HAS_NEWSPAPER4K:
        return None

    # Skip domains that require browser rendering (loaded from wsj_domain_status)
    if blocked_domains:
        from domain_utils import is_blocked_domain
        if is_blocked_domain(domain, blocked_domains):
            return None

    try:
        article = newspaper.article(url, timeout=15)
        article.parse()

        text = article.text
        if not text or len(text) < min_length:
            return None

        # Apply section cutting to remove noise
        text = _cut_at_section_markers(text)

        # Check quality
        metrics = _compute_quality(text)
        if metrics.reason_code in ("TOO_SHORT", "MENU_HEAVY", "LINK_HEAVY"):
            return None

        return {
            "success": True,
            "title": article.title or "",
            "markdown": text,
            "markdown_length": len(text),
            "authors": article.authors or [],
            "publish_date": str(article.publish_date) if article.publish_date else None,
            "top_image": article.top_image or None,
            "extraction_method": "newspaper4k",
            "quality": asdict(metrics),
        }

    except Exception:
        # newspaper4k failed - will fall back to browser
        return None


async def crawl_article(
    url: str,
    mode: str = "undetected",
    use_domain_selector: bool = True,
    skip_blocked: bool = True,
    log_result: bool = True,
    blocked_domains: set[str] = None,
) -> dict:
    """
    Crawl an article URL and extract content.

    Uses hybrid approach: tries newspaper4k first (fast), falls back to browser.

    Args:
        url: The article URL to crawl
        mode: "basic", "stealth", or "undetected"
        use_domain_selector: If True, use domain-specific CSS selectors when available
        skip_blocked: If True, skip domains known to be blocked
        log_result: If True, log success/failure to blocked_domains.json
        blocked_domains: Set of domains to skip newspaper4k (from wsj_domain_status)

    Returns:
        dict with keys: success, status_code, title, markdown, markdown_length, domain, skipped, resolved_url
        Also includes: extraction_method, authors, publish_date (when newspaper4k succeeds)
    """
    original_url = url
    resolved_url = None

    # Auto-resolve Google News URLs
    if is_google_news_url(url):
        resolved_url = await resolve_google_news_url(url)
        if resolved_url:
            url = resolved_url
        else:
            # Resolution failed - return error
            return {
                "success": False,
                "status_code": 0,
                "title": None,
                "markdown": "",
                "markdown_length": 0,
                "domain": "news.google.com",
                "skipped": True,
                "skip_reason": "Could not resolve Google News URL",
                "original_url": original_url,
                "resolved_url": None,
            }

    domain = get_domain(url)

    # Check if domain is blocked
    is_blocked, block_reason = is_domain_blocked(domain)
    if skip_blocked and is_blocked:
        return {
            "success": False,
            "status_code": 0,
            "title": None,
            "markdown": "",
            "markdown_length": 0,
            "domain": domain,
            "skipped": True,
            "skip_reason": block_reason,
        }

    # =========================================================================
    # HYBRID APPROACH: Try newspaper4k first (fast), fall back to browser
    # =========================================================================
    np_result = _try_newspaper4k(url, domain, blocked_domains)
    if np_result:
        # newspaper4k succeeded - return result with standard fields
        if log_result:
            log_crawl_result(domain, True, 200, np_result["markdown_length"])

        return {
            "success": True,
            "status_code": 200,
            "title": np_result["title"],
            "markdown": np_result["markdown"],
            "markdown_length": np_result["markdown_length"],
            "domain": domain,
            "skipped": False,
            "original_url": original_url,
            "resolved_url": resolved_url,
            "extraction_method": "newspaper4k",
            "authors": np_result.get("authors", []),
            "publish_date": np_result.get("publish_date"),
            "top_image": np_result.get("top_image"),
            "quality": np_result.get("quality"),
        }

    # newspaper4k failed or skipped - fall back to browser-based crawling
    domain_config = get_domain_config(url)
    is_known_domain = domain_config is not None

    # Build crawler config
    base_kwargs = {
        "word_count_threshold": 50,
        "page_timeout": 45000,
    }

    if is_known_domain and use_domain_selector:
        # Known domain: use site-specific config
        crawler_kwargs = base_kwargs.copy()
        if "css_selector" in domain_config:
            crawler_kwargs["css_selector"] = domain_config["css_selector"]
        if "excluded_tags" in domain_config:
            crawler_kwargs["excluded_tags"] = domain_config["excluded_tags"]

        result = await _do_crawl(url, crawler_kwargs, domain, mode)
    else:
        # Unknown domain: use 2-pass fallback strategy
        # Pass 1: Generic pruning (no CSS selector, just excluded tags)
        pass1_kwargs = base_kwargs.copy()
        pass1_kwargs["excluded_tags"] = DEFAULT_EXCLUDED_TAGS
        pass1_kwargs["remove_overlay_elements"] = True

        result = await _do_crawl(url, pass1_kwargs, domain, mode)

        # If Pass 1 failed or too short, try Pass 2 with article selectors
        if result["markdown_length"] < 500 and result["success"]:
            pass2_kwargs = base_kwargs.copy()
            pass2_kwargs["css_selector"] = DEFAULT_CSS_SELECTOR
            pass2_kwargs["excluded_tags"] = DEFAULT_EXCLUDED_TAGS

            result2 = await _do_crawl(url, pass2_kwargs, domain, mode)
            # Use Pass 2 only if it gives more content
            if result2["markdown_length"] > result["markdown_length"]:
                result = result2

    # Log result for future reference
    if log_result:
        log_crawl_result(domain, result["success"], result["status_code"], result["markdown_length"])

    result["skipped"] = False
    result["original_url"] = original_url
    result["resolved_url"] = resolved_url
    return result


async def _do_crawl(url: str, crawler_kwargs: dict, domain: str, mode: str) -> dict:
    """Execute crawl with given mode and kwargs."""
    if mode == "basic":
        return await _crawl_basic(url, crawler_kwargs, domain)
    elif mode == "stealth":
        return await _crawl_stealth(url, crawler_kwargs, domain)
    else:  # undetected (default)
        return await _crawl_undetected(url, crawler_kwargs, domain)


async def _crawl_basic(url: str, crawler_kwargs: dict, domain: str) -> dict:
    """Basic crawl without stealth features."""
    browser_config = BrowserConfig(headless=True, verbose=False)
    crawler_config = CrawlerRunConfig(**crawler_kwargs)

    async with AsyncWebCrawler(config=browser_config) as crawler:
        result = await crawler.arun(url=url, config=crawler_config)
        return _build_result(result, domain, url)


async def _crawl_stealth(url: str, crawler_kwargs: dict, domain: str) -> dict:
    """Crawl with stealth mode enabled."""
    browser_config = BrowserConfig(
        headless=True,
        verbose=False,
        enable_stealth=True,
    )

    crawler_kwargs.update({
        "magic": True,
        "simulate_user": True,
        "delay_before_return_html": 2.0,
    })
    crawler_config = CrawlerRunConfig(**crawler_kwargs)

    async with AsyncWebCrawler(config=browser_config) as crawler:
        result = await crawler.arun(url=url, config=crawler_config)
        return _build_result(result, domain, url)


async def _crawl_undetected(url: str, crawler_kwargs: dict, domain: str) -> dict:
    """Crawl with undetected browser adapter (most robust)."""
    from crawl4ai import UndetectedAdapter
    from crawl4ai.async_crawler_strategy import AsyncPlaywrightCrawlerStrategy

    browser_config = BrowserConfig(
        headless=False,  # Docs recommend False for undetected
        verbose=True,
    )

    undetected_adapter = UndetectedAdapter()
    crawler_strategy = AsyncPlaywrightCrawlerStrategy(
        browser_config=browser_config,
        browser_adapter=undetected_adapter
    )

    crawler_config = CrawlerRunConfig(**crawler_kwargs)

    async with AsyncWebCrawler(
        crawler_strategy=crawler_strategy,
        config=browser_config
    ) as crawler:
        result = await crawler.arun(url=url, config=crawler_config)
        return _build_result(result, domain, url)


def _extract_title(result) -> str | None:
    """Extract title from metadata, HTML, or markdown heading."""
    # Try metadata first
    if result.metadata and result.metadata.get("title"):
        return result.metadata.get("title")

    # Try HTML <title> tag
    if result.html:
        match = re.search(r"<title[^>]*>([^<]+)</title>", result.html, re.IGNORECASE)
        if match:
            return match.group(1).strip()

    # Common consent/privacy popup titles to skip
    consent_keywords = ["opt out", "cookie", "privacy", "consent", "gdpr", "personal information"]

    # Try <h1> tag from HTML (for CSS-selected content)
    if result.html:
        match = re.search(r"<h1[^>]*>([^<]+)</h1>", result.html, re.IGNORECASE | re.DOTALL)
        if match:
            title = match.group(1).strip()
            title = re.sub(r"<[^>]+>", "", title)  # Remove nested tags
            # Skip consent/privacy popup titles
            if title and not any(kw in title.lower() for kw in consent_keywords):
                return title

    # Fallback: extract first H1 from markdown (only single #, not ##)
    markdown = str(result.markdown) if result.markdown else ""
    if markdown:
        # Match # Heading at start of line (but not ## or more)
        match = re.search(r"^#\s+([^#].+)$", markdown, re.MULTILINE)
        if match:
            title = match.group(1).strip()
            # Clean up markdown formatting from title
            title = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", title)  # Remove links
            title = re.sub(r"[*_`]", "", title)  # Remove formatting
            # Skip consent/privacy popup titles
            if not any(kw in title.lower() for kw in consent_keywords):
                return title

    return None


def _fetch_title_from_url(url: str) -> str | None:
    """Fetch title from URL using httpx (for when CSS selector strips <head>)."""
    try:
        with httpx.Client(timeout=10, follow_redirects=True, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }) as client:
            resp = client.get(url)
            html = resp.text

            # Try og:title first (most reliable)
            og_match = re.search(
                r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']',
                html, re.IGNORECASE
            )
            if og_match:
                title = og_match.group(1).strip()
                # Unescape HTML entities
                import html as html_module
                return html_module.unescape(title)

            # Try <title> tag
            title_match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
            if title_match:
                import html as html_module
                return html_module.unescape(title_match.group(1).strip())

    except Exception:
        pass
    return None


def _build_result(result, domain: str, url: str = None) -> dict:
    """Build standardized result dict from crawler result.

    Extraction strategy:
    1. Try trafilatura on raw HTML (best quality)
    2. Fall back to crawl4ai markdown + cleaning
    3. Apply section cutting and truncation
    4. Compute quality metrics
    """
    # Get raw HTML and markdown from result
    html = getattr(result, "html", "") or ""
    if result.markdown:
        markdown = str(result.markdown)
    else:
        markdown = ""

    # Strategy 1: Try trafilatura on HTML (preferred)
    content = ""
    extraction_method = "none"

    if html:
        content, extraction_method = _extract_with_trafilatura(html, url)

    # Strategy 2: Fall back to crawl4ai markdown + cleaning
    if not content or len(content) < 300:
        cleaned_md = clean_article_content(markdown)
        if len(cleaned_md) > len(content):
            content = cleaned_md
            extraction_method = "crawl4ai_cleaned"

    # Post-process: cut at section markers
    content = _cut_at_section_markers(content)

    # Truncate if too long (max 20k chars)
    MAX_CONTENT_LENGTH = 20000
    truncated = False
    if len(content) > MAX_CONTENT_LENGTH:
        content = content[:MAX_CONTENT_LENGTH].rstrip()
        # Try to cut at last paragraph
        last_para = content.rfind("\n\n")
        if last_para > MAX_CONTENT_LENGTH * 0.8:
            content = content[:last_para]
        content += "\n\n[TRUNCATED]"
        truncated = True

    # Compute quality metrics
    quality = _compute_quality(content)

    # Extract title - try from result first, then fetch from URL
    title = _extract_title(result)
    if not title and url:
        title = _fetch_title_from_url(url)

    # Determine success: fetch OK + content quality OK
    fetch_success = bool(getattr(result, "success", False))
    quality_ok = quality.char_len >= 350 and quality.word_len >= 50 and quality.reason_code not in ("MENU_HEAVY", "LINK_HEAVY")

    return {
        "success": fetch_success and quality_ok,
        "status_code": result.status_code,
        "title": title,
        "markdown": content,  # Keep field name for compatibility
        "markdown_length": len(content),
        "domain": domain,
        "extraction_method": extraction_method,
        "truncated": truncated,
        "quality": asdict(quality),
    }


def _deduplicate_content(text: str) -> str:
    """Remove duplicated content (when CSS selector matches multiple similar elements)."""
    if not text or len(text) < 500:
        return text

    # Split into lines (non-empty)
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    if len(lines) < 8:
        return text

    # Find where duplication starts by looking for a repeated line
    # Check each line in first half to see if it appears again later
    for start_idx in range(3, len(lines) // 2):
        line_to_find = lines[start_idx][:80].lower()
        if len(line_to_find) < 30:  # Skip short lines
            continue

        # Look for this line appearing again in the second half
        for dup_idx in range(start_idx + 3, len(lines)):
            if lines[dup_idx][:80].lower() == line_to_find:
                # Found potential duplicate start - verify by checking next few lines
                matches = 0
                check_count = min(5, len(lines) - dup_idx)
                for j in range(check_count):
                    if start_idx + j < len(lines) and dup_idx + j < len(lines):
                        if lines[start_idx + j][:60].lower() == lines[dup_idx + j][:60].lower():
                            matches += 1

                if matches >= 3:  # At least 3 consecutive matching lines
                    # Duplicate confirmed - keep only up to dup_idx
                    return '\n'.join(lines[:dup_idx])

    return text


def clean_article_content(markdown: str) -> str:
    """Remove navigation, boilerplate, and noise from article markdown.

    Strategy:
    - If content is already substantial (100+ words), CSS selector did its job
      → Do minimal cleaning (just trim obvious boilerplate)
    - If content is sparse, use aggressive pattern-based cleaning
    """
    if not markdown:
        return ""

    word_count = len(markdown.split())

    # CSS selector already targeted article content - minimal cleaning
    if word_count > 100:
        lines = markdown.split('\n')
        cleaned = []

        # Noise lines to skip entirely
        noise_patterns = [
            'ad feedback', 'advertisement', 'cookie', 'privacy policy',
            'sign in', 'subscribe now', 'skip to', 'see all topics',
            'facebook tweet email', 'share this article'
        ]

        # End-of-article markers - stop processing when we hit these
        stop_patterns = [
            '**read next:**', 'read next:', 'mentioned in this article',
            '## latest news', '## related', '## more from', 'disclosure: none',
            '## mentioned in',
            'catch all the',  # livemint footer
            '## topics',  # livemint/hindustantimes topic tags
            'explore more on these topics',  # guardian
            '### most viewed',  # guardian
            'quick guide',  # guardian sidebar
            'contact us about this story',  # guardian
        ]

        # Skip leading empty lines and obvious boilerplate
        started = False
        for line in lines:
            stripped = line.strip()
            if not started and not stripped:
                continue

            lower = stripped.lower()

            # Stop at end-of-article markers
            if any(x in lower for x in stop_patterns):
                break

            # Skip short noise lines (don't filter long content lines)
            if len(stripped) < 100 and any(x in lower for x in noise_patterns):
                continue

            # Skip standalone short navigation links [Text](url)
            if stripped.startswith('[') and stripped.endswith(')') and len(stripped) < 60:
                if '](http' in stripped or '](/follow' in stripped:
                    continue

            if not started:
                started = True
            cleaned.append(line)

        # Trim trailing boilerplate
        while cleaned:
            last = cleaned[-1].strip().lower()
            if any(x in last for x in ['privacy policy', 'terms of service', 'cookie', 'newsletter', 'related articles', 'recommended for you', 'more from']):
                cleaned.pop()
            elif not last:  # Remove trailing empty lines
                cleaned.pop()
            else:
                break

        result = '\n'.join(cleaned)
        result = re.sub(r'\n{3,}', '\n\n', result)  # Collapse multiple blank lines

        # Deduplicate: if content is repeated, keep only first half
        result = _deduplicate_content(result)

        return result.strip()

    # Sparse content - use aggressive pattern-based cleaning (original logic)
    lines = markdown.split('\n')
    cleaned_lines = []
    in_article = False

    # Patterns to skip (navigation, CTAs, boilerplate)
    skip_patterns = [
        # CNBC patterns
        r'^\[Skip Navigation\]',
        r'^CREATE FREE ACCOUNT',
        r'^\[Markets\]',
        r'^\[Business\]',
        r'^\[Investing\]',
        r'^\[Tech\]',
        r'^\[Politics\]',
        r'^\[Video\]',
        r'^\[Watchlist\]',
        r'^\[Investing Club\]',
        r'^\[PRO\]',
        r'^\[Livestream\]',
        r'^!\[Join',  # Join IC, Join Pro images
        r'^Menu$',
        r'^In this article',
        r'Follow your favorite stocks',
        r'^\s*\*\s*\[JPM\]',  # Stock ticker links
        r'^\s*\*\s*\[GS\]',
        r'^\s*\*\s*\[GSBD\]',
        r'^\s*\*\s*\[AAPL\]',
        r'^\[Prefer to Listen\?\]',
        r'^\[\]\(https://.*live-tv',  # Empty live-tv links
        r'^NOW$',
        r'^UP NEXT$',
        r'^Squawk on the Street',
        r'^Money Movers',
        # Yahoo Finance / Simply Wall St patterns
        r'^Scroll back up to restore',
        r'^Prediction Market powered by',
        r'^\[\s*\]\(https://polymarket',  # Empty polymarket links
        r'stocks are working on everything from',
        r'still time to get in early',
        r'Read the full narrative',
        r'Uncover how.*fair value',
        r'Explore \d+ other fair value',
        r'Create your own in under',
        r'extraordinary investment returns',
        r'great starting point for your.*research',
        r'Our free.*research report',
        r'Trump.*oil.*primed to profit',
        r'companies with promising cash flow',
        r'survived and thrived after COVID',
        r'Discover why before your portfolio',
        r'^\[\s*AAPL\s*[+-]?\d',  # Stock ticker with price change
        r'^Story Continues',
        r'^\!\[AAPL.*Stock Price Chart',  # Chart images
        r'^AAPL \d+-Year Stock Price',
        # Bloomberg patterns
        r'^FacebookXLinkedIn',
        r'^EmailLink',
        r'^GiftGift this article',
        r'^Gift$',
        r'Contact us.*Provide news feedback',
        r'Confidential tip.*Send a tip',
        r'Site feedback.*Take our Survey',
        r'^BookmarkSave',
        r'^\[Home\]',
        r'^\[BTV\+\]',
        r'^\[Market Data\]',
        r'^\[Opinion\]',
        r'^\[Audio\]',
        r'^\[Originals\]',
        r'^\[Magazine\]',
        r'^\[Events\]',
        r'^News$',
        r'^Work & Life',
        r'^\[Wealth\]',
        r'^\[Pursuits\]',
        r'^\[Businessweek\]',
        r'^\[CityLab\]',
        r'^\[Sports\]',
        r'^\[Equality\]',
        r'^\[Management & Work\]',
        r'^Market Data$',
        r'^\[Stocks\]',
        r'^\[Commodities\]',
        r'^\[Rates & Bonds\]',
        r'^\[Currencies\]',
        r'^\[Futures\]',
        r'^\[Sectors\]',
        r'^\[Economic Calendar\]',
        r'^Explore$',
    ]

    # Patterns that indicate article content has started
    article_start_patterns = [
        r'^Key Points',
        r'^##\s',  # H2 headers
        r'^\w.{50,}',  # Long paragraph starting with word
    ]

    # Patterns that indicate article has ended (stop processing)
    article_end_patterns = [
        r'This site is now part of',
        r'Privacy Policy',
        r'Your Privacy Choices',
        r'cookie',
        r'Opt-Out',
        r'Versant',
        r'Terms of Service',
        r'Advertisement',
        r'^Related:',
        r'Sign up for',
        r'Subscribe to',
        r'Newsletter',
        r'Have feedback on this article',
        r'Get in touch.*with us directly',
        r'This article by Simply Wall St',
        r'general in nature',
        r'not intended to be financial advice',
        r'Ready To Venture',
        r'Build Your Own.*Narrative',
        r'Exploring Other Perspectives',
        r'Our top stock finds',
        r'Companies discussed in this article',
    ]

    for line in lines:
        stripped = line.strip()

        # Check if we've hit end-of-article markers
        for pattern in article_end_patterns:
            if re.search(pattern, stripped, re.IGNORECASE):
                # Stop processing - we've hit the footer/boilerplate
                result = '\n'.join(cleaned_lines)
                result = re.sub(r'\n{3,}', '\n\n', result)
                return result.strip()

        # Skip empty lines at the start
        if not in_article and not stripped:
            continue

        # Check if we should skip this line
        should_skip = False
        for pattern in skip_patterns:
            # Use search for non-anchored patterns, match for anchored ones
            if pattern.startswith('^'):
                if re.match(pattern, stripped, re.IGNORECASE):
                    should_skip = True
                    break
            else:
                if re.search(pattern, stripped, re.IGNORECASE):
                    should_skip = True
                    break

        if should_skip:
            continue

        # Check if article content has started
        if not in_article:
            for pattern in article_start_patterns:
                if re.match(pattern, stripped):
                    in_article = True
                    break

        # Once in article, include the line
        if in_article:
            # Skip lines that are just markdown links to other pages
            if re.match(r'^\[\w+\]\(https?://[^)]+\)$', stripped):
                continue
            # Skip standalone image lines
            if re.match(r'^!\[.*\]\(.*\)$', stripped):
                continue
            cleaned_lines.append(line)

    # Join and clean up multiple blank lines
    result = '\n'.join(cleaned_lines)
    result = re.sub(r'\n{3,}', '\n\n', result)

    return result.strip()


def save_article(result: dict, url: str, output_dir: str = None) -> Path:
    """Save article content to markdown file."""
    title = result["title"] or "article"
    safe_name = re.sub(r'[^\w\s-]', '', title)[:50].strip().replace(' ', '_')

    # Use absolute path relative to this script
    if output_dir is None:
        output_path = Path(__file__).parent / "output"
    else:
        output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    output_file = output_path / f"{safe_name}.md"

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(f"# {result['title']}\n\n")
        f.write(f"**Source:** {url}\n\n")
        f.write(f"**Domain:** {result['domain']}\n\n")
        f.write("---\n\n")
        f.write(result["markdown"] or "")

    return output_file


async def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/crawl_article.py <url> [mode] [--save] [--force] [--no-domain-selector]")
        print("Modes: basic, stealth, undetected (default)")
        print("Options:")
        print("  --save                Save full content to file")
        print("  --force               Force crawl even if domain is blocked")
        print("  --no-domain-selector  Disable domain-specific CSS selectors")
        print("\nBlocked domains are tracked in scripts/data/blocked_domains.json")
        sys.exit(1)

    url = sys.argv[1]
    mode = "undetected"
    save_to_file = False
    use_domain_selector = True
    skip_blocked = True

    for arg in sys.argv[2:]:
        if arg == "--save":
            save_to_file = True
        elif arg == "--force":
            skip_blocked = False
        elif arg == "--no-domain-selector":
            use_domain_selector = False
        elif arg in ["basic", "stealth", "undetected"]:
            mode = arg

    # Handle Google News URLs first
    if is_google_news_url(url):
        print(f"Google News URL detected: {url[:80]}...")
        print("Resolving to actual article URL...")
        resolved = await resolve_google_news_url(url)
        if resolved:
            print(f"Resolved to: {resolved}")
            url = resolved
        else:
            print("ERROR: Could not resolve Google News URL")
            sys.exit(1)

    domain = get_domain(url)
    is_known_domain = get_domain_config(url) is not None

    # Check blocked status
    is_blocked, block_reason = is_domain_blocked(domain)
    if is_blocked:
        print(f"Domain blocked: {domain}")
        print(f"  Reason: {block_reason}")
        if skip_blocked:
            print("  Use --force to attempt anyway")
            sys.exit(0)
        print("  Attempting anyway due to --force flag...")

    print(f"Crawling: {url}")
    print(f"Mode: {mode}")
    print(f"Domain: {domain} ({'configured' if is_known_domain else 'fallback'})")
    print("=" * 60)

    result = await crawl_article(url, mode=mode, use_domain_selector=use_domain_selector, skip_blocked=skip_blocked)

    if result.get("skipped"):
        print(f"Skipped: {result.get('skip_reason', 'Domain blocked')}")
        sys.exit(0)

    print(f"Success: {result['success']}")
    print(f"Status: {result['status_code']}")
    print(f"Title: {result['title']}")
    print(f"Extraction: {result.get('extraction_method', 'unknown')}")
    if result.get('quality'):
        q = result['quality']
        print(f"Quality: score={q['quality_score']:.2f}, reason={q['reason_code']}")
    print(f"Content length: {result['markdown_length']} chars" + (" [TRUNCATED]" if result.get('truncated') else ""))

    if result["markdown"] and result["markdown_length"] > 100:
        if save_to_file:
            output_file = save_article(result, url)
            print(f"\n✓ Saved to: {output_file}")
        else:
            print("\n" + "=" * 60)
            print("FULL CONTENT:")
            print("=" * 60)
            print(result["markdown"])
    else:
        print("\n⚠ No meaningful content extracted")


if __name__ == "__main__":
    asyncio.run(main())
