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


def is_garbage_content(text: str) -> tuple[bool, str | None]:
    """Detect unusable crawled content (paywall, CSS/JS, repeated words).

    Args:
        text: Crawled markdown content

    Returns:
        Tuple of (is_garbage, reason) where reason is None if not garbage
    """
    if not text:
        return True, "empty_content"

    words = text.split()

    # Check for repeated words pattern (e.g., "word word word...")
    if len(words) > 50:
        unique_ratio = len(set(words)) / len(words)
        if unique_ratio < 0.1:
            return True, "repeated_words"

    # Check for CSS/JS code patterns
    css_patterns = ['mask-image:url', '.f_', '{display:', '@media', 'font-family:', 'padding:']
    first_2000 = text[:2000]
    css_matches = sum(1 for p in css_patterns if p in first_2000)
    if css_matches >= 3:
        return True, "css_js_code"

    # Check for paywall indicators
    paywall_patterns = ['meterActive', 'meterExpired', 'piano', 'subscribe to continue', 'subscription required']
    first_1000_lower = text[:1000].lower()
    if any(p.lower() in first_1000_lower for p in paywall_patterns):
        return True, "paywall"

    return False, None


def get_supabase_client():
    """Get Supabase client if credentials are available."""
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / '.env.local')

    supabase_url = os.getenv("NEXT_PUBLIC_SUPABASE_URL") or os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")

    if not supabase_url or not supabase_key:
        return None

    from supabase import create_client
    return create_client(supabase_url, supabase_key)


def get_pending_items_from_db(supabase) -> list[dict]:
    """Get pending crawl items from database, grouped by WSJ item.

    Returns list of dicts with 'wsj' info and 'ranked' list of pending articles.
    """
    if not supabase:
        return []

    # Query pending crawl results with WSJ item info
    response = supabase.table('wsj_crawl_results') \
        .select('*, wsj_items(id, title, description)') \
        .eq('crawl_status', 'pending') \
        .not_.is_('resolved_url', 'null') \
        .order('created_at') \
        .execute()

    if not response.data:
        return []

    # Group by wsj_item_id
    by_wsj: dict = {}
    for row in response.data:
        wsj_item = row.get('wsj_items') or {}
        wsj_id = row.get('wsj_item_id')

        if not wsj_id:
            continue

        if wsj_id not in by_wsj:
            by_wsj[wsj_id] = {
                'wsj': {
                    'id': wsj_id,
                    'title': wsj_item.get('title', ''),
                    'description': wsj_item.get('description', ''),
                },
                'ranked': []
            }

        by_wsj[wsj_id]['ranked'].append({
            'resolved_url': row.get('resolved_url'),
            'resolved_domain': row.get('resolved_domain'),
            'source': row.get('source'),
            'bm25_rank': row.get('bm25_rank'),
        })

    return list(by_wsj.values())


def save_crawl_result_to_db(supabase, article: dict, wsj: dict) -> bool:
    """Save a single crawl result to Supabase immediately.

    Updates the existing 'pending' record with crawl data.
    """
    if not supabase:
        return False

    from datetime import datetime, timezone

    record = {
        'resolved_url': article.get('resolved_url'),
        'crawl_status': article.get('crawl_status'),
        'crawl_error': article.get('crawl_error'),
        'crawl_length': article.get('crawl_length'),
        'content': article.get('crawl_markdown'),
        'crawled_at': datetime.now(timezone.utc).isoformat() if article.get('crawl_status') == 'success' else None,
        'relevance_score': article.get('relevance_score'),
        'relevance_flag': article.get('relevance_flag'),
    }

    try:
        supabase.table('wsj_crawl_results').upsert(
            record,
            on_conflict='resolved_url'
        ).execute()
        return True
    except Exception as e:
        print(f"  DB save error: {e}")
        return False


def mark_other_articles_skipped(supabase, wsj_item_id: str, success_url: str) -> int:
    """Mark other pending articles for the same WSJ item as 'skipped'.

    After a successful crawl, we don't need the backup articles anymore.
    This makes the status more accurate (not 'pending' when they won't be crawled).
    """
    if not supabase or not wsj_item_id:
        return 0

    try:
        # Update all pending articles for this WSJ item (except the successful one)
        response = supabase.table('wsj_crawl_results').update({
            'crawl_status': 'skipped',
            'crawl_error': 'Another article succeeded for this WSJ item',
        }).eq('wsj_item_id', wsj_item_id).eq('crawl_status', 'pending').neq('resolved_url', success_url).execute()

        return len(response.data) if response.data else 0
    except Exception as e:
        print(f"  DB skip error: {e}")
        return 0


async def main():
    # Parse arguments
    delay = 3.0
    update_db = False
    from_db = False
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--delay" and i + 1 < len(args):
            delay = float(args[i + 1])
            i += 2
        elif args[i] == "--update-db":
            update_db = True
            i += 1
        elif args[i] == "--from-db":
            from_db = True
            update_db = True  # --from-db implies --update-db
            i += 1
        else:
            i += 1

    # Initialize Supabase client
    supabase = get_supabase_client() if (update_db or from_db) else None
    if (update_db or from_db) and not supabase:
        print("Error: Database credentials not found in .env.local")
        print("Required: NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY")
        return

    # Load data from DB or file
    if from_db:
        print("Loading pending items from database...")
        all_data = get_pending_items_from_db(supabase)
        if not all_data:
            print("No pending items found in database.")
            return
        print(f"Loaded {len(all_data)} WSJ items with pending backups")
    else:
        # Load ranked results from file (default behavior for GitHub Actions)
        input_path = Path(__file__).parent / "output" / "wsj_ranked_results.jsonl"
        if not input_path.exists():
            print(f"Error: Run embedding_rank.py and resolve_ranked.py first")
            return

        # Read all data
        all_data = []
        with open(input_path) as f:
            for line in f:
                all_data.append(json.loads(line))

        print(f"Loaded {len(all_data)} WSJ items from file")
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
                    crawled_content = result.get("markdown", "")

                    # Step 1: Check for garbage content (paywall, CSS/JS, repeated words)
                    is_garbage, garbage_reason = is_garbage_content(crawled_content)
                    if is_garbage:
                        article["crawl_status"] = "garbage"
                        article["crawl_error"] = garbage_reason
                        article["crawl_length"] = result.get("markdown_length", 0)
                        print(f"✗ Garbage: {garbage_reason}")

                        # Save garbage result to DB and try next backup
                        if supabase:
                            save_crawl_result_to_db(supabase, article, wsj)

                        # Rate limit before next attempt
                        if j < len(crawlable) - 1:
                            await asyncio.sleep(delay)
                        continue  # Try next backup article

                    # Step 2: Check relevance score
                    relevance = compute_relevance_score(wsj_text, crawled_content)
                    article["relevance_score"] = round(relevance, 4)

                    if relevance < RELEVANCE_THRESHOLD:
                        # Mark as success but with low relevance flag
                        # This allows domain tracking while enabling backup retries
                        article["crawl_status"] = "success"
                        article["relevance_flag"] = "low"
                        article["crawl_length"] = result.get("markdown_length", 0)
                        article["crawl_markdown"] = crawled_content  # Save content for reference
                        print(f"⚠ Low relevance: {relevance:.2f} - trying next backup")

                        # Save low relevance result to DB and try next backup
                        if supabase:
                            save_crawl_result_to_db(supabase, article, wsj)

                        # Rate limit before next attempt
                        if j < len(crawlable) - 1:
                            await asyncio.sleep(delay)
                        continue  # Try next backup article

                    # Step 3: All checks passed - mark as success
                    article["crawl_status"] = "success"
                    article["crawl_title"] = result.get("title", "")
                    article["crawl_markdown"] = crawled_content
                    article["crawl_length"] = result.get("markdown_length", 0)
                    article["relevance_flag"] = "ok"

                    # Output with success indicator
                    print(f"✓ {result.get('markdown_length', 0):,} chars | rel:{relevance:.2f} ✓")

                    # Save to DB immediately
                    if supabase:
                        save_crawl_result_to_db(supabase, article, wsj)
                        # Mark other pending articles for this WSJ as skipped
                        skipped = mark_other_articles_skipped(supabase, wsj.get('id'), url)
                        if skipped > 0:
                            print(f"    → Marked {skipped} backup articles as skipped")

                    success = True
                    wsj_success += 1
                    break  # Stop trying more articles for this WSJ
                else:
                    # Failed - mark and try next
                    article["crawl_status"] = "failed"
                    article["crawl_error"] = result.get("skip_reason", "Content too short")
                    print(f"✗ {result.get('skip_reason', 'Too short')[:30]}")

                    # Save failure to DB
                    if supabase:
                        save_crawl_result_to_db(supabase, article, wsj)

            except Exception as e:
                article["crawl_status"] = "error"
                article["crawl_error"] = str(e)[:100]
                print(f"✗ {str(e)[:30]}")

                # Save error to DB
                if supabase:
                    save_crawl_result_to_db(supabase, article, wsj)

            # Rate limit before next attempt
            if j < len(crawlable) - 1:
                await asyncio.sleep(delay)

        if not success:
            print(f"  → All candidates failed")
            wsj_failed += 1

        # Rate limit between WSJ items
        if i < len(all_data) - 1:
            await asyncio.sleep(delay)

    # Write back to file (only when reading from file, not --from-db)
    if not from_db:
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

    if from_db:
        print(f"\nResults saved to database.")
    else:
        print(f"\nUpdated: {input_path}")


if __name__ == "__main__":
    asyncio.run(main())
