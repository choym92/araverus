#!/usr/bin/env python3
"""
Backfill slugs for existing wsj_items where slug IS NULL.

Usage:
    python scripts/backfill_slugs.py
    python scripts/backfill_slugs.py --dry-run
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv(Path(__file__).parent.parent.parent / '.env.local')

from utils.slug import generate_unique_slug


def main():
    dry_run = '--dry-run' in sys.argv

    url = os.getenv('NEXT_PUBLIC_SUPABASE_URL') or os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    if not url or not key:
        print("Missing Supabase credentials")
        sys.exit(1)

    supabase = create_client(url, key)

    # Fetch all items missing slugs
    print("Fetching items with NULL slug...")
    response = supabase.table('wsj_items') \
        .select('id, title, published_at') \
        .is_('slug', 'null') \
        .order('published_at', desc=False) \
        .limit(2000) \
        .execute()

    items = response.data or []
    print(f"Found {len(items)} items to backfill")

    if not items:
        print("Nothing to do.")
        return

    # Get existing slugs to avoid collisions
    existing_response = supabase.table('wsj_items') \
        .select('slug') \
        .not_.is_('slug', 'null') \
        .execute()
    existing_slugs = {row['slug'] for row in (existing_response.data or []) if row.get('slug')}
    print(f"Existing slugs: {len(existing_slugs)}")

    updated = 0
    errors = 0

    for item in items:
        slug = generate_unique_slug(
            item['title'],
            item.get('published_at'),
            existing_slugs,
        )

        if dry_run:
            print(f"  [DRY] {item['title'][:60]} → {slug}")
            existing_slugs.add(slug)
            updated += 1
            continue

        try:
            supabase.table('wsj_items') \
                .update({'slug': slug}) \
                .eq('id', item['id']) \
                .execute()
            existing_slugs.add(slug)
            updated += 1
        except Exception as e:
            print(f"  ERROR: {item['id']}: {e}")
            errors += 1

    print(f"\n{'[DRY RUN] ' if dry_run else ''}Updated: {updated}, Errors: {errors}")

    if not dry_run:
        # Verify
        null_count = supabase.table('wsj_items') \
            .select('id', count='exact') \
            .is_('slug', 'null') \
            .execute()
        print(f"Remaining NULL slugs: {null_count.count}")


if __name__ == "__main__":
    main()
