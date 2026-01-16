#!/usr/bin/env python3
"""
Crawl resolved URLs from BM25 ranked results.

Strategy: Crawl 1 article per WSJ item, with fallback to next if failed.

Usage:
    python scripts/crawl_ranked.py [--delay N] [--no-relevance]
"""
import asyncio
import json
import os
import sys
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

# Import the crawler
sys.path.insert(0, str(Path(__file__).parent))
from crawl_article import crawl_article

# Use stealth mode in CI (headless), undetected locally (better evasion)
IS_CI = os.environ.get("CI") == "true" or os.environ.get("GITHUB_ACTIONS") == "true"
CRAWL_MODE = "stealth" if IS_CI else "undetected"

# Relevance check settings
RELEVANCE_THRESHOLD = 0.25  # Flag if below this
RELEVANCE_CHARS = 800       # Characters from crawled content to compare

# Load embedding model for relevance check (cached after first load)
print("Loading embedding model for relevance check...")
RELEVANCE_MODEL = SentenceTransformer('all-MiniLM-L6-v2')
print("Model loaded.\n")


def compute_relevance_score(wsj_text: str, crawled_text: str) -> float:
    """Compute cosine similarity between WSJ and crawled content.

    Args:
        wsj_text: WSJ title + description
        crawled_text: First N characters of crawled content

    Returns:
        Cosine similarity score (0-1)
    """
    if not wsj_text or not crawled_text:
        return 0.0

    # Truncate crawled text to stay within token limit
    crawled_truncated = crawled_text[:RELEVANCE_CHARS]

    # Encode both texts
    embeddings = RELEVANCE_MODEL.encode(
        [wsj_text, crawled_truncated],
        normalize_embeddings=True
    )

    # Cosine similarity (dot product since normalized)
    score = float(np.dot(embeddings[0], embeddings[1]))
    return score


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
        wsj = data.get("wsj", {})
        wsj_title = wsj.get("title", "Unknown")
        wsj_description = wsj.get("description", "")
        wsj_text = f"{wsj_title} {wsj_description}".strip()
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

                    # Compute relevance score
                    crawled_content = result.get("markdown", "")
                    relevance = compute_relevance_score(wsj_text, crawled_content)
                    article["relevance_score"] = round(relevance, 4)
                    article["relevance_flag"] = "low" if relevance < RELEVANCE_THRESHOLD else "ok"

                    # Output with relevance indicator
                    rel_indicator = "⚠" if relevance < RELEVANCE_THRESHOLD else "✓"
                    print(f"✓ {result.get('markdown_length', 0):,} chars | rel:{relevance:.2f} {rel_indicator}")

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

    # Relevance statistics
    relevance_scores = []
    low_relevance = []
    for data in all_data:
        wsj_title = data.get("wsj", {}).get("title", "")[:40]
        for art in data.get("ranked", []):
            if art.get("crawl_status") == "success" and "relevance_score" in art:
                score = art["relevance_score"]
                relevance_scores.append(score)
                if art.get("relevance_flag") == "low":
                    low_relevance.append((wsj_title, art.get("resolved_domain", ""), score))

    if relevance_scores:
        print(f"\nRelevance scores:")
        print(f"  Min: {min(relevance_scores):.3f}")
        print(f"  Max: {max(relevance_scores):.3f}")
        print(f"  Avg: {sum(relevance_scores)/len(relevance_scores):.3f}")
        print(f"  Low relevance (<{RELEVANCE_THRESHOLD}): {len(low_relevance)}")

    if low_relevance:
        print(f"\n⚠ Low relevance articles:")
        for wsj, domain, score in low_relevance:
            print(f"  [{score:.2f}] {domain} - {wsj}...")

    # Show successful crawls
    print("\nSuccessful crawls:")
    for data in all_data:
        wsj = data.get("wsj", {}).get("title", "")[:40]
        for art in data.get("ranked", []):
            if art.get("crawl_status") == "success":
                domain = art.get("resolved_domain", "")
                length = art.get("crawl_length", 0)
                rel = art.get("relevance_score", 0)
                flag = "⚠" if art.get("relevance_flag") == "low" else "✓"
                print(f"  {flag} [{domain}] {length:,} chars, rel:{rel:.2f} - {wsj}...")

    print(f"\nUpdated: {input_path}")


if __name__ == "__main__":
    asyncio.run(main())
