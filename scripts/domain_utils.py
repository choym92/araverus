#!/usr/bin/env python3
"""
Shared domain utilities for WSJ pipeline.

Provides:
- Base preferred domains (hardcoded reliable sources)
- Dynamic loading of top domains from DB by weighted_score
- Domain matching utilities
"""
import os
from functools import lru_cache
from pathlib import Path

# Base preferred domains - manually verified as reliable
BASE_PREFERRED_DOMAINS = [
    'livemint.com',
    'marketwatch.com',
    'finance.yahoo.com',
    'cnbc.com',
    'finviz.com',
    'hindustantimes.com',
]


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


def load_top_domains_from_db(supabase, limit: int = 10) -> list[str]:
    """
    Load top domains from wsj_domain_status by weighted_score.

    weighted_score = avg_relevance_score * success_rate

    Args:
        supabase: Supabase client
        limit: Number of top domains to fetch

    Returns:
        List of domain strings, sorted by weighted_score descending
    """
    if not supabase:
        return []

    try:
        response = supabase.table('wsj_domain_status') \
            .select('domain, weighted_score') \
            .eq('status', 'active') \
            .not_.is_('weighted_score', 'null') \
            .order('weighted_score', desc=True) \
            .limit(limit) \
            .execute()

        if response.data:
            domains = [row['domain'] for row in response.data if row.get('domain')]
            return domains
    except Exception as e:
        print(f"  Warning: Could not load top domains from DB: {e}")

    return []


def load_preferred_domains(supabase=None, top_n: int = 10) -> list[str]:
    """
    Get combined list of preferred domains.

    Combines:
    - BASE_PREFERRED_DOMAINS (hardcoded reliable sources)
    - Top N domains from DB by weighted_score

    Args:
        supabase: Supabase client (optional, will create if None)
        top_n: Number of top domains to fetch from DB

    Returns:
        Deduplicated list of preferred domains
    """
    # Start with base domains
    result = BASE_PREFERRED_DOMAINS.copy()

    # Get supabase client if not provided
    if supabase is None:
        supabase = get_supabase_client()

    # Load top domains from DB
    if supabase:
        top_domains = load_top_domains_from_db(supabase, limit=top_n)

        # Add new domains (deduplicated)
        for domain in top_domains:
            if domain not in result:
                result.append(domain)

        if top_domains:
            print(f"  Loaded {len(top_domains)} top domains from DB, total preferred: {len(result)}")

    return result


def is_preferred_domain(source_domain: str, preferred_domains: list[str]) -> bool:
    """
    Check if domain is in preferred list.

    Args:
        source_domain: Domain to check
        preferred_domains: List of preferred domains

    Returns:
        True if domain matches any preferred domain
    """
    if not source_domain:
        return False

    source_lower = source_domain.lower()
    for pref in preferred_domains:
        pref_lower = pref.lower()
        if pref_lower in source_lower or source_lower in pref_lower:
            return True

    return False


def get_domain_priority(source_domain: str, preferred_domains: list[str]) -> int:
    """
    Get priority score for domain (lower = higher priority).

    Args:
        source_domain: Domain to check
        preferred_domains: List of preferred domains

    Returns:
        Priority score (0 = highest priority, 999 = not preferred)
    """
    if not source_domain:
        return 999

    source_lower = source_domain.lower()
    for i, pref in enumerate(preferred_domains):
        pref_lower = pref.lower()
        if pref_lower in source_lower or source_lower in pref_lower:
            return i  # Lower index = higher priority

    return 100  # Non-preferred domains get low priority


def load_blocked_domains(supabase=None) -> set[str]:
    """
    Load blocked domains from wsj_domain_status.

    These domains require browser rendering (Cloudflare, paywall, etc.)
    and should skip newspaper4k fast extraction.

    Args:
        supabase: Supabase client (optional, will create if None)

    Returns:
        Set of blocked domain strings
    """
    if supabase is None:
        supabase = get_supabase_client()

    if not supabase:
        return set()

    try:
        response = supabase.table('wsj_domain_status') \
            .select('domain') \
            .eq('status', 'blocked') \
            .execute()

        if response.data:
            domains = {row['domain'] for row in response.data if row.get('domain')}
            return domains
    except Exception as e:
        print(f"  Warning: Could not load blocked domains from DB: {e}")

    return set()


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
