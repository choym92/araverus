#!/usr/bin/env python3
"""
Shared domain utilities for WSJ pipeline.

Provides:
- Blocked domain loading from DB + local JSON
- Domain matching utilities
"""
import os
from pathlib import Path


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
    Load blocked domains from wsj_domain_status + local JSON file.

    Args:
        supabase: Supabase client (optional, will create if None)

    Returns:
        Set of blocked domain strings
    """
    blocked = set()

    # Load from local JSON file
    json_path = Path(__file__).parent / "data" / "blocked_domains.json"
    if json_path.exists():
        import json
        with open(json_path) as f:
            data = json.load(f)
            json_domains = set(data) if isinstance(data, list) else set(data.get("domains", []))
            blocked.update(json_domains)

    # Load from DB
    if supabase is None:
        supabase = get_supabase_client()

    if supabase:
        try:
            response = supabase.table('wsj_domain_status') \
                .select('domain') \
                .eq('status', 'blocked') \
                .execute()

            if response.data:
                db_domains = {row['domain'] for row in response.data if row.get('domain')}
                blocked.update(db_domains)
        except Exception as e:
            print(f"  Warning: Could not load blocked domains from DB: {e}")

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
