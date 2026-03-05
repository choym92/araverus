#!/usr/bin/env python3
"""
One-off Backfill · Headlines — Generate AI headlines for existing articles missing them.

Queries wsj_llm_analysis rows where headline IS NULL, generates a lightweight
headline using title + description + summary, and updates only the headline column.

Usage:
    cd scripts
    python backfill_headlines.py --dry-run
    python backfill_headlines.py --limit 5
    python backfill_headlines.py
"""
import argparse
import time

from dotenv import load_dotenv

load_dotenv(".env.local")

from domain_utils import require_supabase_client  # noqa: E402
from lib.llm_analysis import generate_headline_only  # noqa: E402


def get_missing_headlines(supabase, limit: int | None = None):
    """Fetch articles with NULL headline, joined with wsj_items for title/description.

    Paginates through all results to bypass Supabase's default 1000-row limit.
    """
    PAGE_SIZE = 1000
    all_rows = []
    offset = 0

    while True:
        query = (
            supabase.table("wsj_llm_analysis")
            .select("id, crawl_result_id, summary, wsj_crawl_results!inner(wsj_items!inner(title, description))")
            .is_("headline", "null")
            .order("created_at", desc=False)
            .range(offset, offset + PAGE_SIZE - 1)
        )
        if limit:
            remaining = limit - len(all_rows)
            query = query.limit(min(remaining, PAGE_SIZE))

        result = query.execute()
        rows = result.data or []
        all_rows.extend(rows)

        if len(rows) < PAGE_SIZE or (limit and len(all_rows) >= limit):
            break
        offset += PAGE_SIZE

    return all_rows


def cleanup_non_ok_headlines(supabase, dry_run: bool = False):
    """NULL out headlines on crawl results where relevance_flag != 'ok'.

    Ensures "headline exists = ok crawl = quality guaranteed" invariant.
    """
    # Find llm_analysis rows with headline where the parent crawl is not 'ok'
    PAGE_SIZE = 1000
    rows = []
    offset = 0
    while True:
        result = (
            supabase.table("wsj_llm_analysis")
            .select("id, headline, wsj_crawl_results!inner(relevance_flag)")
            .not_.is_("headline", "null")
            .neq("wsj_crawl_results.relevance_flag", "ok")
            .range(offset, offset + PAGE_SIZE - 1)
            .execute()
        )
        batch = result.data or []
        rows.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    print(f"Found {len(rows)} headlines on non-ok crawls")

    if dry_run or not rows:
        return

    ids = [r["id"] for r in rows]
    BATCH = 500
    for i in range(0, len(ids), BATCH):
        batch = ids[i : i + BATCH]
        supabase.table("wsj_llm_analysis").update({"headline": None}).in_("id", batch).execute()
        print(f"  Cleared {min(i + BATCH, len(ids))}/{len(ids)}")

    print(f"Done: {len(ids)} headlines cleared")


def main():
    parser = argparse.ArgumentParser(description="Backfill missing headlines")
    parser.add_argument("--dry-run", action="store_true", help="Show count only")
    parser.add_argument("--limit", type=int, default=None, help="Process N articles")
    parser.add_argument("--delay", type=float, default=0.3, help="Seconds between LLM calls")
    parser.add_argument("--cleanup", action="store_true", help="Remove headlines from non-ok crawls")
    args = parser.parse_args()

    supabase = require_supabase_client()

    if args.cleanup:
        cleanup_non_ok_headlines(supabase, args.dry_run)
        return

    rows = get_missing_headlines(supabase, args.limit)

    print(f"Found {len(rows)} articles with missing headlines")
    if args.dry_run or not rows:
        return

    total_input = 0
    total_output = 0
    success = 0

    for i, row in enumerate(rows, 1):
        wsj_item = row["wsj_crawl_results"]["wsj_items"]
        title = wsj_item["title"]
        description = wsj_item.get("description", "")
        summary = row.get("summary")

        result = generate_headline_only(title, description, summary)
        if not result or not result.get("headline"):
            print(f"  [{i}/{len(rows)}] ✗ Failed for: {title[:60]}")
            if i < len(rows):
                time.sleep(args.delay)
            continue

        headline = result["headline"]
        total_input += result.get("input_tokens") or 0
        total_output += result.get("output_tokens") or 0

        # Update only headline
        try:
            supabase.table("wsj_llm_analysis").update(
                {"headline": headline}
            ).eq("id", row["id"]).execute()
            success += 1
            print(f"  [{i}/{len(rows)}] ✓ {headline[:60]}")
        except Exception as e:
            print(f"  [{i}/{len(rows)}] ✗ DB error: {e}")

        if i < len(rows):
            time.sleep(args.delay)

    print(f"\nDone: {success}/{len(rows)} headlines generated")
    print(f"Tokens: {total_input:,} input + {total_output:,} output")


if __name__ == "__main__":
    main()
