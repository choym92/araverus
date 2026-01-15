#!/usr/bin/env python3
"""
Crawl resolved URLs from BM25 ranked results.

Strategy: Crawl 1 article per WSJ item, with fallback to next if failed.

Usage:
    python scripts/crawl_ranked.py [--delay N]
"""
import asyncio
import json
import os
import sys
from pathlib import Path

# Import the crawler
sys.path.insert(0, str(Path(__file__).parent))
from crawl_article import crawl_article

# Use stealth mode in CI (headless), undetected locally (better evasion)
IS_CI = os.environ.get("CI") == "true" or os.environ.get("GITHUB_ACTIONS") == "true"
CRAWL_MODE = "stealth" if IS_CI else "undetected"


async def main():
    # Parse arguments
    delay = 3.0
    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg == "--delay" and i + 1 < len(args):
            delay = float(args[i + 1])

    # Load ranked results
    input_path = Path(__file__).parent / "output" / "wsj_ranked_results.jsonl"
    if not input_path.exists():
        print(f"Error: Run embedding_rank.py and resolve_ranked.py first")
        return

    # Read all data
    all_data = []
    with open(input_path) as f:
        for line in f:
            all_data.append(json.loads(line))

    print(f"Loaded {len(all_data)} WSJ items")
    print(f"Strategy: 1 article per WSJ, fallback on failure")
    print(f"Crawl mode: {CRAWL_MODE} ({'CI detected' if IS_CI else 'local'})")
    print(f"Delay: {delay}s")
    print("=" * 80)

    # Track results
    wsj_success = 0
    wsj_failed = 0
    total_attempts = 0

    for i, data in enumerate(all_data):
        wsj_title = data.get("wsj", {}).get("title", "Unknown")
        articles = data.get("ranked", [])

        # Filter to articles with resolved URLs
        crawlable = [a for a in articles if a.get("resolved_url")]

        print(f"\n[{i+1}/{len(all_data)}] WSJ: {wsj_title[:60]}...")
        print(f"  Candidates: {len(crawlable)}")

        if not crawlable:
            print(f"  ✗ No resolved URLs")
            wsj_failed += 1
            continue

        # Try each article until one succeeds
        success = False
        for j, article in enumerate(crawlable):
            url = article["resolved_url"]
            source = article.get("source", "Unknown")
            domain = article.get("resolved_domain", "")
            is_pref = "★" if article.get("is_preferred") else " "

            total_attempts += 1
            print(f"  {is_pref} Trying [{j+1}/{len(crawlable)}]: {domain}...", end=" ", flush=True)

            try:
                result = await crawl_article(url, mode=CRAWL_MODE)

                if result.get("success") and result.get("markdown_length", 0) > 500:
                    # Success! Mark this article
                    article["crawl_status"] = "success"
                    article["crawl_title"] = result.get("title", "")
                    article["crawl_markdown"] = result.get("markdown", "")
                    article["crawl_length"] = result.get("markdown_length", 0)

                    print(f"✓ {result.get('markdown_length', 0):,} chars")
                    success = True
                    wsj_success += 1
                    break  # Stop trying more articles for this WSJ
                else:
                    # Failed - mark and try next
                    article["crawl_status"] = "failed"
                    article["crawl_error"] = result.get("skip_reason", "Content too short")
                    print(f"✗ {result.get('skip_reason', 'Too short')[:30]}")

            except Exception as e:
                article["crawl_status"] = "error"
                article["crawl_error"] = str(e)[:100]
                print(f"✗ {str(e)[:30]}")

            # Rate limit before next attempt
            if j < len(crawlable) - 1:
                await asyncio.sleep(delay)

        if not success:
            print(f"  → All candidates failed")
            wsj_failed += 1

        # Rate limit between WSJ items
        if i < len(all_data) - 1:
            await asyncio.sleep(delay)

    # Write back to file
    with open(input_path, "w") as f:
        for data in all_data:
            f.write(json.dumps(data, ensure_ascii=False) + "\n")

    # Summary
    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"WSJ items: {len(all_data)}")
    print(f"  ✓ Success: {wsj_success}")
    print(f"  ✗ Failed: {wsj_failed}")
    print(f"Total crawl attempts: {total_attempts}")

    # Show successful crawls
    print("\nSuccessful crawls:")
    for data in all_data:
        wsj = data.get("wsj", {}).get("title", "")[:40]
        for art in data.get("ranked", []):
            if art.get("crawl_status") == "success":
                domain = art.get("resolved_domain", "")
                length = art.get("crawl_length", 0)
                print(f"  [{domain}] {length:,} chars - {wsj}...")

    print(f"\nUpdated: {input_path}")


if __name__ == "__main__":
    asyncio.run(main())
