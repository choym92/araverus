"""
Google News URL Resolver (Python port) - Production Grade

Resolves Google News redirect URLs to actual article URLs.
Multi-strategy approach:
1. Direct base64 decode (old format)
2. batchexecute API (new AU_yqL format)
3. HTML canonical fallback

Returns structured results with reason codes for debugging.
"""

import base64
import json
import re
import time
from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlparse, quote

import httpx

# User agent for requests
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


class ReasonCode(str, Enum):
    """Reason codes for resolution results."""
    # Success codes
    SUCCESS = "SUCCESS"
    PASSTHROUGH = "PASSTHROUGH"  # Non-Google-News URL, returned as-is

    # URL validation failures
    GN_URL_INVALID = "GN_URL_INVALID"  # Not a valid Google News URL
    GN_FORMAT_UNKNOWN = "GN_FORMAT_UNKNOWN"  # Unknown URL format
    URL_CORRUPTED = "URL_CORRUPTED"  # URL contains whitespace/invalid chars

    # Decode failures
    DECODE_FAIL = "DECODE_FAIL"  # Base64 decode failed
    DECODE_NO_URL = "DECODE_NO_URL"  # Decoded but no URL found

    # Batchexecute failures
    SIG_TS_MISSING = "SIG_TS_MISSING"  # Could not extract signature/timestamp
    BATCH_EXEC_FAIL = "BATCH_EXEC_FAIL"  # Batchexecute API call failed
    BATCH_PARSE_FAIL = "BATCH_PARSE_FAIL"  # Could not parse batchexecute response

    # Canonical fallback failures
    CANONICAL_NOT_FOUND = "CANONICAL_NOT_FOUND"  # No canonical URL in HTML
    REDIRECT_STUCK = "REDIRECT_STUCK"  # Redirect didn't leave Google News

    # HTTP errors
    HTTP_403 = "HTTP_403"  # Forbidden
    HTTP_429 = "HTTP_429"  # Rate limited
    HTTP_4XX = "HTTP_4XX"  # Other 4xx error
    HTTP_5XX = "HTTP_5XX"  # Server error

    # Network errors
    TIMEOUT = "TIMEOUT"
    NETWORK_ERROR = "NETWORK_ERROR"

    # Fallback
    BROWSER_REQUIRED = "BROWSER_REQUIRED"  # Needs headless browser
    ALL_STRATEGIES_FAILED = "ALL_STRATEGIES_FAILED"


class Strategy(str, Enum):
    """Resolution strategies used."""
    PASSTHROUGH = "passthrough"
    DECODE = "decode"
    BATCHEXECUTE = "batchexecute"
    CANONICAL = "canonical"
    BROWSER = "browser"
    NONE = "none"


@dataclass
class ResolveResult:
    """Structured result from URL resolution."""
    success: bool
    resolved_url: str | None
    reason_code: ReasonCode
    strategy_used: Strategy
    http_status: int | None = None
    elapsed_ms: int = 0
    final_url: str | None = None
    error_detail: str | None = None

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "resolved_url": self.resolved_url,
            "reason_code": self.reason_code.value,
            "strategy_used": self.strategy_used.value,
            "http_status": self.http_status,
            "elapsed_ms": self.elapsed_ms,
            "final_url": self.final_url,
            "error_detail": self.error_detail,
        }


def is_google_news_url(url: str) -> bool:
    """Check if URL is a Google News redirect URL."""
    return "news.google.com" in url and "/articles/" in url


def decode_google_news_url(google_url: str) -> tuple[str | None, ReasonCode]:
    """
    Decode a Google News URL to extract the actual article URL.

    Works for old format where URL is directly in base64 encoded content.
    Returns (url, reason_code) tuple.
    """
    try:
        match = re.search(r'/articles/([^/?]+)', google_url)
        if not match:
            return None, ReasonCode.GN_URL_INVALID

        encoded = match.group(1)
        # Convert URL-safe base64 to standard base64
        base64_str = encoded.replace('-', '+').replace('_', '/')
        # Add padding if needed
        padding = 4 - len(base64_str) % 4
        if padding != 4:
            base64_str += '=' * padding

        try:
            decoded = base64.b64decode(base64_str)
            content = decoded.decode('latin-1')
        except Exception:
            return None, ReasonCode.DECODE_FAIL

        # Check for protobuf prefix markers
        prefix = bytes([0x08, 0x13, 0x22]).decode('latin-1')
        if content.startswith(prefix):
            content = content[len(prefix):]

        # Remove known suffix if present
        suffix = bytes([0xd2, 0x01, 0x00]).decode('latin-1')
        if content.endswith(suffix):
            content = content[:-len(suffix)]

        # Parse length byte and extract inner content
        if content:
            length = ord(content[0])
            if length >= 0x80:
                content = content[2:length + 2]
            else:
                content = content[1:length + 1]

        # Check if this is the new format that needs batchexecute API
        if content.startswith('AU_yqL'):
            return None, ReasonCode.GN_FORMAT_UNKNOWN  # Needs batchexecute

        # Old format: look for URL directly
        url_match = re.search(r'https?://[^\s\x00-\x1f"<>]+', content)
        if url_match:
            url = url_match.group(0)
            # Clean trailing non-URL characters
            url = re.sub(r'[\x00-\x1f\x7f-\xff]+$', '', url)
            return url, ReasonCode.SUCCESS

        return None, ReasonCode.DECODE_NO_URL
    except Exception:
        return None, ReasonCode.DECODE_FAIL


def needs_batch_execute(google_url: str) -> bool:
    """Check if a Google News URL uses the new format requiring batchexecute API."""
    try:
        match = re.search(r'/articles/([^/?]+)', google_url)
        if not match:
            return False

        encoded = match.group(1)
        base64_str = encoded.replace('-', '+').replace('_', '/')
        padding = 4 - len(base64_str) % 4
        if padding != 4:
            base64_str += '=' * padding

        decoded = base64.b64decode(base64_str).decode('latin-1')
        return 'AU_yqL' in decoded
    except Exception:
        return False


def extract_article_id(google_url: str) -> str | None:
    """Extract the article ID from a Google News URL."""
    match = re.search(r'/articles/([^/?]+)', google_url)
    return match.group(1) if match else None


def fetch_decoded_batch_execute(
    article_id: str,
    client: httpx.Client
) -> tuple[str | None, ReasonCode, int | None]:
    """
    Decode Google News URL using the batchexecute API.
    Returns (url, reason_code, http_status).
    """
    # Step 1: Fetch article page to get signature and timestamp
    article_url = f"https://news.google.com/articles/{article_id}"

    try:
        response = client.get(
            article_url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml",
            },
            follow_redirects=True,
            timeout=15.0,
        )
    except httpx.TimeoutException:
        return None, ReasonCode.TIMEOUT, None
    except httpx.RequestError:
        return None, ReasonCode.NETWORK_ERROR, None

    if response.status_code == 403:
        return None, ReasonCode.HTTP_403, 403
    if response.status_code == 429:
        return None, ReasonCode.HTTP_429, 429
    if response.status_code >= 500:
        return None, ReasonCode.HTTP_5XX, response.status_code
    if response.status_code >= 400:
        return None, ReasonCode.HTTP_4XX, response.status_code
    if response.status_code != 200:
        return None, ReasonCode.BATCH_EXEC_FAIL, response.status_code

    html = response.text

    # Extract signature and timestamp
    sig_match = re.search(r'data-n-a-sg="([^"]+)"', html)
    ts_match = re.search(r'data-n-a-ts="([^"]+)"', html)

    if not sig_match or not ts_match:
        return None, ReasonCode.SIG_TS_MISSING, 200

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

    try:
        response = client.post(
            "https://news.google.com/_/DotsSplashUi/data/batchexecute?rpcids=Fbv4je",
            headers={
                "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                "Referer": "https://news.google.com/",
                "User-Agent": USER_AGENT,
            },
            content=f"f.req={quote(payload)}",
            timeout=15.0,
        )
    except httpx.TimeoutException:
        return None, ReasonCode.TIMEOUT, None
    except httpx.RequestError:
        return None, ReasonCode.NETWORK_ERROR, None

    if response.status_code != 200:
        return None, ReasonCode.BATCH_EXEC_FAIL, response.status_code

    text = response.text

    # Parse the response to extract the URL
    url_match = re.search(r'\["garturlres","(https?:[^"]+)"', text)
    if url_match:
        url = url_match.group(1)
        url = url.replace('\\u003d', '=').replace('\\u0026', '&')
        return url, ReasonCode.SUCCESS, 200

    # Alternative format with escaped quotes
    alt_match = re.search(r'\[\\"garturlres\\",\\"(https?:[^"\\]+)\\"', text)
    if alt_match:
        url = alt_match.group(1)
        url = url.replace('\\u003d', '=').replace('\\u0026', '&')
        return url, ReasonCode.SUCCESS, 200

    return None, ReasonCode.BATCH_PARSE_FAIL, 200


def fetch_canonical_from_html(
    google_url: str,
    client: httpx.Client
) -> tuple[str | None, ReasonCode, int | None]:
    """
    Fallback: Parse canonical URL from HTML page.
    Returns (url, reason_code, http_status).
    """
    try:
        response = client.get(
            google_url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
            },
            follow_redirects=True,
            timeout=15.0,
        )
    except httpx.TimeoutException:
        return None, ReasonCode.TIMEOUT, None
    except httpx.RequestError:
        return None, ReasonCode.NETWORK_ERROR, None

    if response.status_code == 403:
        return None, ReasonCode.HTTP_403, 403
    if response.status_code == 429:
        return None, ReasonCode.HTTP_429, 429
    if response.status_code >= 500:
        return None, ReasonCode.HTTP_5XX, response.status_code
    if response.status_code >= 400:
        return None, ReasonCode.HTTP_4XX, response.status_code

    # If we got redirected to a non-Google URL, that's our answer
    final_url = str(response.url)
    if "news.google.com" not in final_url:
        return final_url, ReasonCode.SUCCESS, response.status_code

    html = response.text

    # Try to find canonical URL
    canonical_match = re.search(
        r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)["\']',
        html, re.IGNORECASE
    )
    if canonical_match and "news.google.com" not in canonical_match.group(1):
        return canonical_match.group(1), ReasonCode.SUCCESS, response.status_code

    # Try og:url
    og_match = re.search(
        r'<meta[^>]+property=["\']og:url["\'][^>]+content=["\']([^"\']+)["\']',
        html, re.IGNORECASE
    )
    if og_match and "news.google.com" not in og_match.group(1):
        return og_match.group(1), ReasonCode.SUCCESS, response.status_code

    return None, ReasonCode.CANONICAL_NOT_FOUND, response.status_code


def resolve_google_news_url(
    url: str,
    client: httpx.Client
) -> ResolveResult:
    """
    Resolve a Google News URL to get the canonical URL.

    Multi-strategy approach:
    1. Passthrough for non-Google-News URLs
    2. Try direct base64 decode (old format, no HTTP needed)
    3. For new format (AU_yqL), use Google's batchexecute API
    4. Fallback: GET HTML and parse canonical/og:url

    Returns structured ResolveResult with success, url, reason_code, strategy, timing.
    """
    start_time = time.perf_counter()

    # Sanitize URL
    clean_url = url.strip()
    if any(c in clean_url for c in [' ', '\n', '\t']):
        return ResolveResult(
            success=False,
            resolved_url=None,
            reason_code=ReasonCode.URL_CORRUPTED,
            strategy_used=Strategy.NONE,
            elapsed_ms=int((time.perf_counter() - start_time) * 1000),
            error_detail="URL contains whitespace or newline",
        )

    # Check if this is a Google News URL
    if not is_google_news_url(clean_url):
        # Passthrough: return original URL
        return ResolveResult(
            success=True,
            resolved_url=clean_url,
            reason_code=ReasonCode.PASSTHROUGH,
            strategy_used=Strategy.PASSTHROUGH,
            elapsed_ms=int((time.perf_counter() - start_time) * 1000),
            final_url=clean_url,
        )

    # Strategy 1: Try direct decode (works for old format)
    decoded_url, decode_reason = decode_google_news_url(clean_url)
    if decoded_url and "news.google.com" not in decoded_url:
        return ResolveResult(
            success=True,
            resolved_url=decoded_url,
            reason_code=ReasonCode.SUCCESS,
            strategy_used=Strategy.DECODE,
            elapsed_ms=int((time.perf_counter() - start_time) * 1000),
            final_url=decoded_url,
        )

    # Strategy 2: For new format, use batchexecute API
    if needs_batch_execute(clean_url):
        article_id = extract_article_id(clean_url)
        if article_id:
            batch_url, batch_reason, batch_status = fetch_decoded_batch_execute(
                article_id, client
            )
            if batch_url and "news.google.com" not in batch_url:
                return ResolveResult(
                    success=True,
                    resolved_url=batch_url,
                    reason_code=ReasonCode.SUCCESS,
                    strategy_used=Strategy.BATCHEXECUTE,
                    http_status=batch_status,
                    elapsed_ms=int((time.perf_counter() - start_time) * 1000),
                    final_url=batch_url,
                )
            # Store batchexecute failure reason for later
            last_reason = batch_reason
            last_status = batch_status
        else:
            last_reason = ReasonCode.GN_URL_INVALID
            last_status = None
    else:
        last_reason = decode_reason
        last_status = None

    # Strategy 3: Fallback - GET HTML and parse canonical URL
    canonical_url, canonical_reason, canonical_status = fetch_canonical_from_html(
        clean_url, client
    )
    if canonical_url:
        return ResolveResult(
            success=True,
            resolved_url=canonical_url,
            reason_code=ReasonCode.SUCCESS,
            strategy_used=Strategy.CANONICAL,
            http_status=canonical_status,
            elapsed_ms=int((time.perf_counter() - start_time) * 1000),
            final_url=canonical_url,
        )

    # All strategies failed - return most relevant failure reason
    final_reason = canonical_reason if canonical_reason != ReasonCode.SUCCESS else last_reason
    final_status = canonical_status or last_status

    return ResolveResult(
        success=False,
        resolved_url=None,
        reason_code=final_reason,
        strategy_used=Strategy.NONE,
        http_status=final_status,
        elapsed_ms=int((time.perf_counter() - start_time) * 1000),
        error_detail=f"All strategies failed. Last: {final_reason.value}",
    )


def extract_domain(url: str | None) -> str:
    """Extract domain from URL, removing www. prefix. Safe for None input."""
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        hostname = parsed.netloc.lower()
        if hostname.startswith("www."):
            hostname = hostname[4:]
        return hostname
    except Exception:
        return ""
