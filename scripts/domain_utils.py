#!/usr/bin/env python3
"""
Shared domain utilities for WSJ pipeline.

Provides:
- Blocked domain loading from DB (wsj_domain_status)
- Hardcoded uncrawlable domains (SNS, video platforms)
- Domain matching utilities
"""
import os
from pathlib import Path

# Domains that can never contain crawlable article content.
# These are blocked unconditionally, regardless of DB stats.
UNCRAWLABLE_DOMAINS = {
    # Social media
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "reddit.com",
    "threads.com",
    "tiktok.com",
    "twitter.com",
    "x.com",
    # Video platforms
    "youtube.com",
    # Aggregator redirects
    "news.google.com",
}


def get_supabase_client():
    """Get Supabase client if credentials are available."""
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / '.env.local')

    supabase_url = os.getenv("NEXT_PUBLIC_SUPABASE_URL") or os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")

    if not supabase_url or not supabase_key:
        return None

    from supabase import create_client
    return create_client(supabase_url, supabase_key)


def load_blocked_domains(supabase=None) -> set[str]:
    """
    Load blocked domains from wsj_domain_status table.

    Args:
        supabase: Supabase client (optional, will create if None)

    Returns:
        Set of blocked domain strings
    """
    blocked = set()

    if supabase is None:
        supabase = get_supabase_client()

    if supabase:
        try:
            response = supabase.table('wsj_domain_status') \
                .select('domain') \
                .eq('status', 'blocked') \
                .execute()

            if response.data:
                blocked = {row['domain'] for row in response.data if row.get('domain')}
        except Exception as e:
            print(f"  Warning: Could not load blocked domains from DB: {e}")

    # Always include hardcoded uncrawlable domains
    blocked |= UNCRAWLABLE_DOMAINS

    return blocked


def is_blocked_domain(domain: str, blocked_domains: set[str]) -> bool:
    """
    Check if domain is in blocked list.

    Args:
        domain: Domain to check
        blocked_domains: Set of blocked domains

    Returns:
        True if domain is blocked
    """
    if not domain or not blocked_domains:
        return False

    domain_lower = domain.lower()
    for blocked in blocked_domains:
        blocked_lower = blocked.lower()
        if blocked_lower in domain_lower or domain_lower in blocked_lower:
            return True

    return False
