#!/usr/bin/env python3
"""
Phase 2 · Step 2 · URL Resolve — Resolve Google News URLs for embedding-ranked results.

Adds resolved_url, resolve_status, resolve_reason_code, resolve_strategy_used
fields to each article in wsj_ranked_results.jsonl.

Usage:
    python scripts/resolve_ranked.py [--delay N] [--update-db]
"""
import json
import os
import sys
import tempfile
import time
from pathlib import Path

import httpx

# Import resolver
sys.path.insert(0, str(Path(__file__).parent))
from google_news_resolver import (
    resolve_google_news_url,
    extract_domain,
    ResolveResult,
    ReasonCode,
)
from domain_utils import get_supabase_client


def atomic_write_jsonl(path: Path, data: list) -> None:
    """Write JSONL atomically using tmp file + rename."""
    fd, tmp_path = tempfile.mkstemp(
        suffix=".jsonl",
        prefix=".resolve_",
        dir=path.parent
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            for item in data:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def update_supabase(all_data: list) -> None:
    """Save resolve results to Supabase.

    - Successful resolutions: crawl_status='pending' (ready for crawl)
    - Failed resolutions: crawl_status='resolve_failed' (tracked for domain blocking)

    Uses INSERT with ignore_duplicates to preserve existing records.
    """
    supabase = get_supabase_client()
    if not supabase:
        print("\nSkipping Supabase update (missing credentials)")
        return

    print("\nSaving resolve results to Supabase...")
    saved_success = 0
    saved_failed = 0
    skipped = 0

    for data in all_data:
        wsj = data.get('wsj', {})
        ranked = data.get('ranked', [])

        for article in ranked:
            resolve_status = article.get('resolve_status')

            if resolve_status == 'success':
                record = {
                    'wsj_item_id': wsj.get('id'),
                    'wsj_title': wsj.get('title'),
                    'wsj_link': wsj.get('link'),
                    'source': article.get('source'),
                    'title': article.get('title'),
                    'resolved_url': article.get('resolved_url'),
                    'resolved_domain': article.get('resolved_domain'),
                    'embedding_score': article.get('embedding_score'),
                    'crawl_status': 'pending',
                }
                try:
                    supabase.table('wsj_crawl_results').insert(record).execute()
                    saved_success += 1
                except Exception as e:
                    if 'duplicate' in str(e).lower() or '23505' in str(e):
                        skipped += 1
                    else:
                        print(f"  Error saving {article.get('resolved_url')}: {e}")

            elif resolve_status in ('failed', 'skipped'):
                original_url = article.get('link', '')
                record = {
                    'wsj_item_id': wsj.get('id'),
                    'wsj_title': wsj.get('title'),
                    'wsj_link': wsj.get('link'),
                    'source': article.get('source'),
                    'title': article.get('title'),
                    'resolved_url': original_url,
                    'resolved_domain': extract_domain(original_url),
                    'embedding_score': article.get('embedding_score'),
                    'crawl_status': 'resolve_failed',
                    'crawl_error': article.get('resolve_reason_code', 'UNKNOWN'),
                }
                try:
                    supabase.table('wsj_crawl_results').insert(record).execute()
                    saved_failed += 1
                except Exception as e:
                    if 'duplicate' in str(e).lower() or '23505' in str(e):
                        skipped += 1
                    else:
                        print(f"  Error saving resolve failure: {e}")

    print(f"  Saved: {saved_success} pending, {saved_failed} resolve_failed (skipped {skipped} existing)")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Resolve Google News URLs for embedding-ranked results")
    parser.add_argument('--delay', type=float, default=3.0, help='Delay between requests in seconds')
    parser.add_argument('--update-db', action='store_true', help='Update Supabase after resolution')
    args = parser.parse_args()

    # Load ranked results
    input_path = Path(__file__).parent / "output" / "wsj_ranked_results.jsonl"
    if not input_path.exists():
        print(f"Error: Run embedding_rank.py first to generate {input_path}")
        sys.exit(1)

    all_data = []
    total_articles = 0
    with open(input_path) as f:
        for line in f:
            data = json.loads(line)
            all_data.append(data)
            total_articles += len(data.get("ranked", []))

    print(f"Loaded {len(all_data)} WSJ items with {total_articles} ranked articles")
    print(f"Delay between requests: {args.delay}s")
    print("=" * 80)

    stats = {
        "resolved": 0,
        "failed": 0,
        "skipped": 0,
        "passthrough": 0,
    }
    reason_counts: dict[str, int] = {}
    strategy_counts: dict[str, int] = {}

    with httpx.Client(timeout=30.0) as http_client:
        article_num = 0
        for wsj_idx, data in enumerate(all_data):
            wsj_title = data.get("wsj", {}).get("title", "Unknown")
            articles = data.get("ranked", [])

            print(f"\n[{wsj_idx+1}/{len(all_data)}] WSJ: {wsj_title[:60]}...")

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

                result: ResolveResult = resolve_google_news_url(google_url, http_client)

                if result.success:
                    article["resolved_url"] = result.resolved_url
                    article["resolved_domain"] = extract_domain(result.resolved_url)
                    article["resolve_status"] = "success"
                    article["resolve_reason_code"] = result.reason_code.value
                    article["resolve_strategy_used"] = result.strategy_used.value

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

                    if result.error_detail:
                        article["resolve_error"] = result.error_detail[:100]

                    error_short = result.reason_code.value
                    if result.http_status:
                        error_short = f"{error_short} (HTTP {result.http_status})"
                    print(f"✗ {error_short}")
                    stats["failed"] += 1

                reason_counts[result.reason_code.value] = reason_counts.get(result.reason_code.value, 0) + 1
                strategy_counts[result.strategy_used.value] = strategy_counts.get(result.strategy_used.value, 0) + 1

                # Rate limit
                if article_num < total_articles:
                    time.sleep(args.delay)

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

    if reason_counts:
        print("\nReason codes:")
        for code, count in sorted(reason_counts.items(), key=lambda x: -x[1]):
            print(f"  {code}: {count}")

    if strategy_counts:
        print("\nStrategies used:")
        for strategy, count in sorted(strategy_counts.items(), key=lambda x: -x[1]):
            print(f"  {strategy}: {count}")

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

    if args.update_db:
        update_supabase(all_data)


if __name__ == "__main__":
    main()
