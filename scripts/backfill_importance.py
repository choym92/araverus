#!/usr/bin/env python3
"""
Backfill importance + keywords for existing LLM analysis records.

Uses Gemini 2.5 Flash with title + summary (no re-crawl needed).
Processes in batches for validation.

Usage:
    python scripts/backfill_importance.py --limit 50        # test batch
    python scripts/backfill_importance.py --limit 500       # larger batch
    python scripts/backfill_importance.py                    # all remaining
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env.local'))

from supabase import create_client, Client


def get_supabase_client() -> Client:
    url = os.environ["NEXT_PUBLIC_SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)

BATCH_PROMPT = """Classify each article's importance and extract keywords.

Articles:
{articles}

Return ONLY valid JSON:
{{"results": [
  {{"id": "<article_id>", "importance": "<must_read|worth_reading|optional>", "keywords": ["<2-4 keywords>"]}},
  ...
]}}

Importance criteria:
- must_read: Market-moving events, major policy shifts, significant earnings surprises, breaking news
- worth_reading: Notable developments, useful market context, sector trends
- optional: Routine updates, minor follow-ups, background pieces

Keywords: 2-4 short topic tags (e.g. "Fed", "interest rates", "Tesla earnings"). Be specific, not generic."""


def get_items_to_backfill(supabase, limit: int | None = None) -> list[dict]:
    """Fetch LLM analysis records missing importance/keywords."""
    query = (
        supabase.table("wsj_llm_analysis")
        .select("id, summary, crawl_result_id, wsj_crawl_results!inner(wsj_item_id, wsj_items!inner(title, description))")
        .is_("importance", "null")
        .order("id")
    )
    if limit:
        query = query.limit(limit)

    resp = query.execute()
    if not resp.data:
        return []

    items = []
    for row in resp.data:
        crawl = row.get("wsj_crawl_results", {})
        item_data = crawl.get("wsj_items", {})
        # Prefer summary, fall back to description
        context = row.get("summary") or item_data.get("description") or ""
        items.append({
            "id": row["id"],
            "title": item_data.get("title", ""),
            "context": context,
        })
    return items


def classify_batch(items: list[dict], client) -> list[dict]:
    """Send a batch to Gemini for importance + keywords classification."""
    from google.genai import types

    article_list = "\n".join(
        f"- [{item['id'][:8]}] {item['title']}"
        + (f" | {item['context'][:150]}" if item['context'] else "")
        for item in items
    )

    prompt = BATCH_PROMPT.format(articles=article_list)

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0,
            response_mime_type="application/json",
        ),
    )

    raw = json.loads(response.text)
    results = raw if isinstance(raw, list) else raw.get("results", [])

    # Map short IDs back to full IDs
    id_map = {item["id"][:8]: item["id"] for item in items}
    for r in results:
        short_id = r.get("id", "")[:8]
        if short_id in id_map:
            r["id"] = id_map[short_id]

    return results


def save_results(supabase, results: list[dict]) -> tuple[int, int]:
    """Update importance + keywords in DB. Returns (updated, errors)."""
    valid_importances = {"must_read", "worth_reading", "optional"}
    updated = 0
    errors = 0

    for r in results:
        importance = r.get("importance", "optional")
        if importance not in valid_importances:
            importance = "optional"

        keywords = r.get("keywords", [])
        if isinstance(keywords, list):
            keywords = [str(k).strip() for k in keywords if k][:4]
        else:
            keywords = []

        try:
            supabase.table("wsj_llm_analysis").update({
                "importance": importance,
                "keywords": keywords,
            }).eq("id", r["id"]).execute()
            updated += 1
        except Exception as e:
            print(f"  Error updating {r['id'][:8]}: {e}")
            errors += 1

    return updated, errors


def main():
    parser = argparse.ArgumentParser(description="Backfill importance + keywords")
    parser.add_argument("--limit", type=int, help="Max articles to process")
    parser.add_argument("--batch-size", type=int, default=100, help="Articles per LLM call")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and classify but don't save")
    args = parser.parse_args()

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY not set")
        sys.exit(1)

    from google import genai
    client = genai.Client(api_key=api_key)

    supabase = get_supabase_client()

    print("Fetching items with NULL importance...")
    items = get_items_to_backfill(supabase, args.limit)
    print(f"Found {len(items)} items to backfill")

    if not items:
        print("Nothing to do!")
        return

    total_updated = 0
    total_errors = 0

    for i in range(0, len(items), args.batch_size):
        batch = items[i:i + args.batch_size]
        batch_num = i // args.batch_size + 1
        print(f"\nBatch {batch_num}: {len(batch)} articles...")

        try:
            results = classify_batch(batch, client)
            print(f"  Classified: {len(results)}")

            if args.dry_run:
                # Show sample
                for r in results[:5]:
                    print(f"  [{r.get('importance', '?'):14s}] {r.get('keywords', [])}")
                if len(results) > 5:
                    print(f"  ... and {len(results) - 5} more")
            else:
                updated, errors = save_results(supabase, results)
                total_updated += updated
                total_errors += errors
                print(f"  Saved: {updated}, Errors: {errors}")

        except Exception as e:
            print(f"  Batch error: {e}")
            total_errors += len(batch)

        time.sleep(1)  # rate limit

    print(f"\nDone! Updated: {total_updated}, Errors: {total_errors}")

    # Show distribution
    if not args.dry_run and total_updated > 0:
        print("\nImportance distribution:")
        for imp in ["must_read", "worth_reading", "optional"]:
            count = (
                supabase.table("wsj_llm_analysis")
                .select("id", count="exact")
                .eq("importance", imp)
                .execute()
            )
            print(f"  {imp}: {count.count}")


if __name__ == "__main__":
    main()
