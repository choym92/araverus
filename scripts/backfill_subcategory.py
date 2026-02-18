"""Backfill NULL subcategory with feed_name fallback + delete junk content."""

import os
import sys
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env.local'))

from supabase import create_client

SUPABASE_URL = os.getenv("NEXT_PUBLIC_SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

JUNK_PATTERNS = ['/buyside/', '/sports/', '/opinion/',
                 '/lifestyle/', '/real-estate/', '/arts/', '/arts-culture/',
                 '/style/', '/livecoverage/', '/health/']

URL_CATEGORY_MAP = {
    'tech': 'tech',
    'finance': 'business-markets',
    'business': 'business-markets',
    'markets': 'business-markets',
    'personal-finance': 'business-markets',
    'science': 'tech',
    'economy': 'economy',
    'politics': 'politics',
    'world': 'world',
}


def main():
    dry_run = '--dry-run' in sys.argv
    sb = create_client(SUPABASE_URL, SUPABASE_KEY)

    # 1) Find and delete junk content
    print("=== Step 1: Delete junk content ===")
    all_items = sb.table('wsj_items').select('id, link, title').execute().data or []
    junk_ids = []
    for item in all_items:
        if any(pat in item['link'] for pat in JUNK_PATTERNS):
            junk_ids.append(item['id'])
            if len(junk_ids) <= 10:
                print(f"  JUNK: {item['title'][:60]}  ({item['link'][:50]}...)")

    print(f"\n  Found {len(junk_ids)} junk items to delete")
    if junk_ids and not dry_run:
        for i in range(0, len(junk_ids), 100):
            batch = junk_ids[i:i+100]
            sb.table('wsj_items').delete().in_('id', batch).execute()
        print(f"  Deleted {len(junk_ids)} junk items")

    # 2) Backfill NULL subcategory
    print("\n=== Step 2: Backfill NULL subcategory ===")
    null_items = sb.table('wsj_items').select('id, link, feed_name, subcategory').is_('subcategory', 'null').execute().data or []
    print(f"  Found {len(null_items)} items with NULL subcategory")

    updates = []
    for item in null_items:
        # Try URL-based extraction first
        try:
            from urllib.parse import urlparse
            path = urlparse(item['link']).pathname.strip('/')
            parts = path.split('/')
            top_path = parts[0].lower() if parts else ''

            if top_path in URL_CATEGORY_MAP:
                # 3+ segments: use parts[1] as subcategory
                if len(parts) >= 3:
                    sub = parts[1]
                else:
                    sub = URL_CATEGORY_MAP[top_path]
            else:
                # Fallback to feed_name
                sub = item['feed_name'].lower().replace('_', '-')
        except Exception:
            sub = item['feed_name'].lower().replace('_', '-')

        updates.append({'id': item['id'], 'subcategory': sub})
        if len(updates) <= 5:
            print(f"  {item['feed_name']:20s} | {sub:20s} | {item['link'][:60]}")

    if len(updates) > 5:
        print(f"  ... and {len(updates) - 5} more")

    if updates and not dry_run:
        count = 0
        for u in updates:
            sb.table('wsj_items').update({'subcategory': u['subcategory']}).eq('id', u['id']).execute()
            count += 1
        print(f"\n  Updated {count} items")

    # 3) Summary
    print("\n=== Summary ===")
    remaining = sb.table('wsj_items').select('id', count='exact').is_('subcategory', 'null').execute()
    total = sb.table('wsj_items').select('id', count='exact').execute()
    print(f"  Total items: {total.count}")
    print(f"  NULL subcategory remaining: {remaining.count}")

    if dry_run:
        print("\n  (DRY RUN — no changes made)")


if __name__ == '__main__':
    main()
