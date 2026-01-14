#!/usr/bin/env python3
"""
Resolve Google News URLs for BM25 ranked results.

Adds resolved_url, resolve_status, resolve_reason_code, resolve_strategy_used
fields to each article in wsj_ranked_results.jsonl.

Usage:
    python scripts/resolve_ranked.py [--delay N] [--update-db]

Options:
    --delay N     Delay between requests in seconds (default: 3.0)
    --update-db   Update Supabase after resolution (requires SUPABASE_URL, SUPABASE_KEY)
"""
import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

import httpx

# Import resolver
sys.path.insert(0, str(Path(__file__).parent))
from google_news_resolver import (
    resolve_google_news_url,
    extract_domain,
    ResolveResult,
    ReasonCode,
    Strategy,
)


def parse_args():
    """Parse command line arguments."""
    delay = 3.0
    update_db = False

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--delay" and i + 1 < len(args):
            delay = float(args[i + 1])
            i += 2
        elif args[i] == "--update-db":
            update_db = True
            i += 1
        else:
            i += 1

    return delay, update_db


def atomic_write_jsonl(path: Path, data: list) -> None:
    """Write JSONL atomically using tmp file + rename."""
    # Create temp file in same directory for atomic rename
    fd, tmp_path = tempfile.mkstemp(
        suffix=".jsonl",
        prefix=".resolve_",
        dir=path.parent
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            for item in data:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        # Atomic rename
        os.replace(tmp_path, path)
    except Exception:
        # Clean up on failure
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


async def update_supabase(all_data: list) -> None:
    """Update resolved URLs in Supabase (optional)."""
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")

    if not supabase_url or not supabase_key:
        print("\nSkipping Supabase update (missing SUPABASE_URL or SUPABASE_KEY)")
        return

    print("\nUpdating Supabase...")
    # TODO: Implement Supabase batch update
    # This would update google_news_results table with resolved URLs
    print("  (Supabase update not yet implemented)")


async def main():
    delay, update_db = parse_args()

    # Load ranked results
    input_path = Path(__file__).parent / "output" / "wsj_ranked_results.jsonl"
    if not input_path.exists():
        print(f"Error: Run bm25_rank.py first to generate {input_path}")
        return

    # Read all data
    all_data = []
    total_articles = 0
    with open(input_path) as f:
        for line in f:
            data = json.loads(line)
            all_data.append(data)
            total_articles += len(data.get("ranked", []))

    print(f"Loaded {len(all_data)} WSJ items with {total_articles} ranked articles")
    print(f"Delay between requests: {delay}s")
    print("=" * 80)

    # Track statistics by reason code
    stats = {
        "resolved": 0,
        "failed": 0,
        "skipped": 0,
        "passthrough": 0,
    }
    reason_counts: dict[str, int] = {}
    strategy_counts: dict[str, int] = {}

    async with httpx.AsyncClient(timeout=30.0) as http_client:
        article_num = 0
        for data in all_data:
            wsj_title = data.get("wsj", {}).get("title", "Unknown")
            articles = data.get("ranked", [])

            print(f"\n[WSJ] {wsj_title[:60]}...")

            for article in articles:
                article_num += 1
                google_url = article.get("link", "")
                source = article.get("source", "Unknown")

                # Skip if already resolved successfully
                if article.get("resolve_status") == "success":
                    print(f"  [{article_num}/{total_articles}] {source}: Already resolved")
                    stats["skipped"] += 1
                    continue

                print(f"  [{article_num}/{total_articles}] {source}...", end=" ", flush=True)

                # Resolve URL using new structured resolver
                result: ResolveResult = await resolve_google_news_url(google_url, http_client)

                # Update article with structured result
                if result.success:
                    article["resolved_url"] = result.resolved_url
                    article["resolved_domain"] = extract_domain(result.resolved_url)
                    article["resolve_status"] = "success"
                    article["resolve_reason_code"] = result.reason_code.value
                    article["resolve_strategy_used"] = result.strategy_used.value

                    # Remove old error field if present
                    article.pop("resolve_error", None)

                    domain_display = article["resolved_domain"] or "unknown"
                    print(f"✓ {domain_display} ({result.strategy_used.value})")

                    if result.reason_code == ReasonCode.PASSTHROUGH:
                        stats["passthrough"] += 1
                    else:
                        stats["resolved"] += 1
                else:
                    article["resolved_url"] = None
                    article["resolved_domain"] = None
                    article["resolve_status"] = "fail"
                    article["resolve_reason_code"] = result.reason_code.value
                    article["resolve_strategy_used"] = result.strategy_used.value

                    # Add error detail if available
                    if result.error_detail:
                        article["resolve_error"] = result.error_detail[:100]

                    error_short = result.reason_code.value
                    if result.http_status:
                        error_short = f"{error_short} (HTTP {result.http_status})"
                    print(f"✗ {error_short}")
                    stats["failed"] += 1

                # Track reason codes and strategies
                reason_counts[result.reason_code.value] = reason_counts.get(result.reason_code.value, 0) + 1
                strategy_counts[result.strategy_used.value] = strategy_counts.get(result.strategy_used.value, 0) + 1

                # Rate limit
                if article_num < total_articles:
                    await asyncio.sleep(delay)

    # Write back atomically
    atomic_write_jsonl(input_path, all_data)

    # Summary
    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total articles: {total_articles}")
    print(f"Resolved: {stats['resolved']}")
    print(f"Passthrough (non-Google URLs): {stats['passthrough']}")
    print(f"Failed: {stats['failed']}")
    print(f"Skipped (already resolved): {stats['skipped']}")

    # Show reason code breakdown
    if reason_counts:
        print("\nReason codes:")
        for code, count in sorted(reason_counts.items(), key=lambda x: -x[1]):
            print(f"  {code}: {count}")

    # Show strategy breakdown
    if strategy_counts:
        print("\nStrategies used:")
        for strategy, count in sorted(strategy_counts.items(), key=lambda x: -x[1]):
            print(f"  {strategy}: {count}")

    # Show resolved domains breakdown
    domain_counts: dict[str, int] = {}
    for data in all_data:
        for article in data.get("ranked", []):
            domain = article.get("resolved_domain")
            if domain:
                domain_counts[domain] = domain_counts.get(domain, 0) + 1

    if domain_counts:
        print("\nResolved domains:")
        for domain, count in sorted(domain_counts.items(), key=lambda x: -x[1]):
            print(f"  {domain}: {count}")

    print(f"\nUpdated: {input_path}")

    # Optional: Update Supabase
    if update_db:
        await update_supabase(all_data)


if __name__ == "__main__":
    asyncio.run(main())
