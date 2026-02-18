"""
Slug generation utilities for WSJ article URLs.

Usage:
    from utils.slug import generate_slug, generate_unique_slug

    slug = generate_slug("Fed Holds Rates Steady Amid Inflation Concerns")
    # → "fed-holds-rates-steady-amid-inflation-concerns"

    unique = generate_unique_slug("Title", "2026-02-17T10:00:00Z", existing_slugs)
    # → "title-2026-02-17" on collision
"""
import re
from datetime import datetime
from typing import Optional


def generate_slug(title: str, max_length: int = 80) -> str:
    """Generate a URL-friendly slug from a title.

    Args:
        title: Article title
        max_length: Maximum slug length (truncated at word boundary)

    Returns:
        Lowercase, hyphenated slug
    """
    if not title:
        return ""

    # Lowercase and strip
    slug = title.lower().strip()

    # Remove special characters, keep alphanumeric and spaces
    slug = re.sub(r"[^\w\s-]", "", slug)

    # Replace whitespace with hyphens
    slug = re.sub(r"[\s_]+", "-", slug)

    # Remove consecutive hyphens
    slug = re.sub(r"-+", "-", slug)

    # Strip leading/trailing hyphens
    slug = slug.strip("-")

    # Truncate at word boundary
    if len(slug) > max_length:
        slug = slug[:max_length].rsplit("-", 1)[0]

    return slug


def generate_unique_slug(
    title: str,
    published_at: Optional[str],
    existing_slugs: set[str],
    max_length: int = 80,
) -> str:
    """Generate a unique slug, appending date suffix on collision.

    Args:
        title: Article title
        published_at: ISO timestamp (used as suffix on collision)
        existing_slugs: Set of already-used slugs
        max_length: Maximum slug length

    Returns:
        Unique slug string
    """
    base = generate_slug(title, max_length)

    if not base:
        base = "untitled"

    if base not in existing_slugs:
        return base

    # Append date suffix
    date_suffix = ""
    if published_at:
        try:
            dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
            date_suffix = dt.strftime("%Y-%m-%d")
        except (ValueError, AttributeError):
            date_suffix = "dup"
    else:
        date_suffix = "dup"

    candidate = f"{base[:max_length - len(date_suffix) - 1]}-{date_suffix}"

    if candidate not in existing_slugs:
        return candidate

    # Final fallback: append counter
    counter = 2
    while True:
        suffix = f"{date_suffix}-{counter}"
        candidate = f"{base[:max_length - len(suffix) - 1]}-{suffix}"
        if candidate not in existing_slugs:
            return candidate
        counter += 1
