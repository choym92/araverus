#!/usr/bin/env python3
"""
Backfill LLM analysis for existing 'ok' articles.

Analyzes articles that passed embedding check but haven't been LLM-verified yet.
Updates relevance_flag to 'low' if LLM determines the content doesn't match.

Usage:
    python scripts/llm_backfill.py [--limit N] [--dry-run] [--delay N]

Options:
    --limit N     Process only N articles (default: all)
    --dry-run     Show what would be analyzed without making changes
    --delay N     Delay between API calls in seconds (default: 0.5)

Example:
    python scripts/llm_backfill.py --limit 10 --dry-run
    python scripts/llm_backfill.py --limit 50
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

# Load env vars
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env.local")

from supabase import create_client

# Import LLM analysis functions
sys.path.insert(0, str(Path(__file__).parent))
from llm_analysis import (
    analyze_content,
    save_analysis_to_db,
    update_domain_llm_failure,
)


def get_supabase_client():
    """Get Supabase client."""
    url = os.getenv("NEXT_PUBLIC_SUPABASE_URL") or os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise ValueError("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
    return create_client(url, key)


def get_articles_to_analyze(supabase, limit: int | None = None) -> list[dict]:
    """Get articles that need LLM analysis.

    Returns articles where:
    - crawl_status = 'success'
    - relevance_flag = 'ok'
    - No existing LLM analysis

    Includes WSJ item info for context.
    """
    # Query successful articles with OK relevance
    query = supabase.table("wsj_crawl_results") \
        .select("id, wsj_item_id, wsj_title, content, resolved_domain, relevance_score, wsj_items(title, description)") \
        .eq("crawl_status", "success") \
        .eq("relevance_flag", "ok") \
        .not_.is_("content", "null")

    if limit:
        query = query.limit(limit * 2)  # Over-fetch to account for already-analyzed

    response = query.execute()
    if not response.data:
        return []

    # Get already-analyzed IDs
    analyzed_response = supabase.table("wsj_llm_analysis") \
        .select("crawl_result_id") \
        .execute()
    analyzed_ids = {r["crawl_result_id"] for r in analyzed_response.data} if analyzed_response.data else set()

    # Filter out already-analyzed
    to_analyze = [r for r in response.data if r["id"] not in analyzed_ids]

    if limit:
        to_analyze = to_analyze[:limit]

    return to_analyze


def estimate_cost(count: int) -> str:
    """Estimate Gemini API cost for analyzing N articles."""
    # Gemini 2.5 Flash: ~$0.00015 per article (input + output)
    cost = count * 0.00015
    return f"${cost:.4f}"


def main():
    parser = argparse.ArgumentParser(description="Backfill LLM analysis for existing articles")
    parser.add_argument("--limit", type=int, help="Process only N articles")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be analyzed")
    parser.add_argument("--delay", type=float, default=0.5, help="Delay between API calls (seconds)")
    args = parser.parse_args()

    # Check for API key
    if not os.getenv("GEMINI_API_KEY"):
        print("Error: GEMINI_API_KEY not set in environment")
        sys.exit(1)

    print("=" * 60)
    print("LLM Analysis Backfill")
    print("=" * 60)

    supabase = get_supabase_client()

    # Get articles to analyze
    print("\nFetching articles to analyze...")
    articles = get_articles_to_analyze(supabase, args.limit)

    if not articles:
        print("No articles need analysis. All done!")
        return

    print(f"Found {len(articles)} articles to analyze")
    print(f"Estimated cost: {estimate_cost(len(articles))}")

    if args.dry_run:
        print("\n[DRY RUN] Would analyze:")
        for i, article in enumerate(articles[:10]):
            wsj_title = article.get("wsj_title") or article.get("wsj_items", {}).get("title", "")
            print(f"  {i+1}. {wsj_title[:60]}...")
        if len(articles) > 10:
            print(f"  ... and {len(articles) - 10} more")
        return

    # Process articles
    print("\n" + "-" * 60)
    analyzed = 0
    low_relevance = 0
    errors = 0

    for i, article in enumerate(articles):
        # Extract info
        crawl_result_id = article["id"]
        wsj_info = article.get("wsj_items") or {}
        wsj_title = wsj_info.get("title") or article.get("wsj_title", "")
        wsj_description = wsj_info.get("description", "")
        content = article.get("content", "")
        domain = article.get("resolved_domain", "")

        print(f"\n[{i+1}/{len(articles)}] {wsj_title[:50]}...")

        # Call LLM
        analysis = analyze_content(
            wsj_title=wsj_title,
            wsj_description=wsj_description,
            crawled_content=content,
        )

        if not analysis:
            print("  ✗ LLM call failed")
            errors += 1
            continue

        # Save analysis to DB
        if not save_analysis_to_db(supabase, crawl_result_id, analysis):
            print("  ✗ DB save failed")
            errors += 1
            continue

        analyzed += 1
        llm_score = analysis.get("relevance_score", 0)
        is_same = analysis.get("is_same_event", False)
        quality = analysis.get("content_quality", "")

        # Check if LLM says not same event
        if not is_same or llm_score < 5:
            low_relevance += 1
            print(f"  ⚠ score={llm_score}, same_event={is_same}, quality={quality}")

            # Update relevance_flag to 'low' and llm_same_event to false
            try:
                supabase.table("wsj_crawl_results") \
                    .update({"relevance_flag": "low", "llm_same_event": False}) \
                    .eq("id", crawl_result_id) \
                    .execute()
                print("    → Updated relevance_flag to 'low', llm_same_event to false")
            except Exception as e:
                print(f"    → Failed to update: {e}")

            # Update domain failure count
            if domain:
                update_domain_llm_failure(supabase, domain)
                print(f"    → Incremented llm_fail_count for {domain}")
        else:
            print(f"  ✓ score={llm_score}, same_event={is_same}, quality={quality}")

            # Update llm_same_event to true for passing articles
            try:
                supabase.table("wsj_crawl_results") \
                    .update({"llm_same_event": True}) \
                    .eq("id", crawl_result_id) \
                    .execute()
            except Exception as e:
                print(f"    → Failed to update llm_same_event: {e}")

        # Rate limit
        if i < len(articles) - 1:
            time.sleep(args.delay)

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Analyzed: {analyzed}")
    print(f"Low relevance (updated): {low_relevance}")
    print(f"Errors: {errors}")
    print(f"Actual cost: ~{estimate_cost(analyzed)}")


if __name__ == "__main__":
    main()
