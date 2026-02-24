#!/usr/bin/env python3
"""
Phase 3 · Step 1 · Crawl — Crawl resolved URLs from embedding-ranked results.

Strategy: Crawl 1 article per WSJ item, with fallback to next if failed.
Relevance check: Compares crawled content to WSJ title using sentence embeddings.

Usage:
    python scripts/crawl_ranked.py [--delay N] [--from-db] [--update-db] [--concurrent N]
"""
import asyncio
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

# Import the crawler and LLM analysis
sys.path.insert(0, str(Path(__file__).parent))
from lib.crawl_article import crawl_article
from lib.llm_analysis import (
    analyze_content,
    save_analysis_to_db,
    update_domain_llm_failure,
    reset_domain_llm_success,
)
from domain_utils import load_blocked_domains, get_supabase_client, normalize_crawl_error

# Use stealth mode in CI (headless), undetected locally (better evasion)
IS_CI = os.environ.get("CI") == "true" or os.environ.get("GITHUB_ACTIONS") == "true"
CRAWL_MODE = "stealth" if IS_CI else "undetected"

# Relevance check settings
RELEVANCE_THRESHOLD = 0.25  # Flag if below this
RELEVANCE_CHARS = 800       # Characters from crawled content to compare

# LLM analysis settings
LLM_ENABLED = bool(os.getenv("GEMINI_API_KEY"))

# Lazy-load embedding model for relevance check
_relevance_model = None


def _get_relevance_model():
    """Lazy-load sentence-transformer model (first call only)."""
    global _relevance_model
    if _relevance_model is None:
        from sentence_transformers import SentenceTransformer
        print("Loading embedding model for relevance check...")
        _relevance_model = SentenceTransformer('BAAI/bge-base-en-v1.5')
        print("Model loaded.\n")
    return _relevance_model

# Per-domain rate limiter: prevents concurrent items from hammering the same domain.
# Each domain gets an asyncio.Lock + last-request timestamp.
DOMAIN_MIN_INTERVAL = 3.0  # seconds between requests to the same domain
_domain_locks: dict[str, asyncio.Lock] = {}
_domain_last_request: dict[str, float] = {}


async def domain_rate_limit(domain: str) -> None:
    """Ensure minimum interval between requests to the same domain.

    Uses per-domain locks so concurrent items wait their turn.
    """
    if not domain:
        return
    if domain not in _domain_locks:
        _domain_locks[domain] = asyncio.Lock()

    async with _domain_locks[domain]:
        now = time.monotonic()
        last = _domain_last_request.get(domain, 0)
        wait = DOMAIN_MIN_INTERVAL - (now - last)
        if wait > 0:
            await asyncio.sleep(wait)
        _domain_last_request[domain] = time.monotonic()


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
    embeddings = _get_relevance_model().encode(
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

    # Check for copyright/unavailable content (often from news aggregators)
    unavailable_patterns = [
        'copyright issues',
        'temporarily unavailable',
        'automatic translation',
        'content not available',
        'article unavailable',
        'content is not available',
        'news is temporarily unavailable',
        'due to copyright',
        'this article is no longer available',
    ]
    if any(p in first_1000_lower for p in unavailable_patterns):
        return True, "copyright_unavailable"

    return False, None



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
            'embedding_score': row.get('embedding_score'),
        })

    return list(by_wsj.values())


def save_crawl_result_to_db(supabase, article: dict, wsj: dict) -> str | None:
    """Save a single crawl result to Supabase immediately.

    Updates the existing 'pending' record with crawl data.

    Returns:
        The database record ID (UUID) if successful, None otherwise.
    """
    if not supabase:
        return None

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
        'llm_same_event': article.get('llm_same_event'),
        'llm_score': article.get('llm_score'),
        'top_image': article.get('top_image'),
    }

    try:
        response = supabase.table('wsj_crawl_results').upsert(
            record,
            on_conflict='resolved_url'
        ).execute()
        # Return the ID of the upserted record
        if response.data and len(response.data) > 0:
            return response.data[0].get('id')
        return None
    except Exception as e:
        print(f"  DB save error: {e}")
        return None


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


async def process_wsj_item(
    idx: int,
    total: int,
    data: dict,
    *,
    delay: float,
    supabase,
    domain_stats: dict,
    run_blocked: set,
    semaphore: asyncio.Semaphore,
) -> dict:
    """Process a single WSJ item: crawl candidates until one succeeds.

    Returns dict with keys: success (bool), attempts (int).
    Shared state (run_blocked) is mutated in-place (safe in asyncio single-thread).
    """
    async with semaphore:
        wsj = data.get("wsj", {})
        wsj_title = wsj.get("title", "Unknown")
        wsj_description = wsj.get("description", "")
        wsj_text = f"{wsj_title} {wsj_description}".strip()
        articles = data.get("ranked", [])

        # Filter to articles with resolved URLs
        crawlable = [a for a in articles if a.get("resolved_url")]

        # Sort by weighted score: 50% embedding + 25% wilson + 25% llm quality
        # Defaults for unknown/insufficient-data domains: wilson=0.4, llm=5.0
        def weighted_score(article):
            emb = article.get("embedding_score") or 0.5
            domain = article.get("resolved_domain", "")
            d = domain_stats.get(domain, {})
            raw_w = d.get("wilson_score")
            raw_l = d.get("avg_llm_score")
            total = (d.get("success_count") or 0) + (d.get("fail_count") or 0)
            # Use defaults when no meaningful data exists
            wilson = float(raw_w) if raw_w is not None and total >= 3 else 0.4
            llm = (float(raw_l) if raw_l is not None else 5.0) / 10.0
            return 0.50 * emb + 0.25 * wilson + 0.25 * llm

        crawlable.sort(key=weighted_score, reverse=True)

        print(f"\n[{idx+1}/{total}] WSJ: {wsj_title[:60]}...")
        print(f"  Candidates: {len(crawlable)} (sorted by weighted score)")

        if not crawlable:
            print("  ✗ No resolved URLs")
            return {"success": False, "attempts": 0}

        # Try each article until one succeeds
        success = False
        attempts = 0
        for j, article in enumerate(crawlable):
            url = article["resolved_url"]
            domain = article.get("resolved_domain", "")
            w_score = weighted_score(article)

            attempts += 1

            # Per-domain rate limit: wait if another concurrent item recently hit this domain
            await domain_rate_limit(domain)

            print(f"  Trying [{j+1}/{len(crawlable)}]: {domain} (w:{w_score:.2f})...", end=" ", flush=True)

            try:
                result = await asyncio.wait_for(
                    crawl_article(url, mode=CRAWL_MODE, blocked_domains=run_blocked),
                    timeout=90
                )

                content = result.get("markdown", "")
                content_len = result.get("markdown_length", 0) or len(content)
                wsj_desc = wsj.get("description", "") or ""
                is_quality_ok = result.get("success") and content_len > 500
                # Short but has more info than WSJ RSS description?
                skip_reason = result.get("skip_reason", "")
                is_short_but_real = (
                    not is_quality_ok
                    and content_len >= 150
                    and len(wsj_desc) > 0
                    and content_len > len(wsj_desc) * 1.5
                    and skip_reason in ("TOO_SHORT", "Content too short", "")
                )

                if is_quality_ok or is_short_but_real:
                    crawled_content = content
                    if is_short_but_real:
                        print(f"↳ Short ({content_len}ch, {content_len/len(wsj_desc):.1f}x desc) — checking gates...", end=" ")

                    # Step 1: Check for garbage content
                    is_garbage, garbage_reason = is_garbage_content(crawled_content)
                    if is_garbage:
                        article["crawl_status"] = "garbage"
                        article["crawl_error"] = garbage_reason
                        article["crawl_length"] = result.get("markdown_length", 0)
                        remaining = len(crawlable) - j - 1
                        print(f"✗ Garbage: {garbage_reason} ({remaining} backups remaining)")
                        if supabase:
                            save_crawl_result_to_db(supabase, article, wsj)
                        if j < len(crawlable) - 1:
                            await asyncio.sleep(delay)
                        continue

                    # Step 2: Check relevance score
                    relevance = compute_relevance_score(wsj_text, crawled_content)
                    article["relevance_score"] = round(relevance, 4)

                    if relevance < RELEVANCE_THRESHOLD:
                        article["crawl_status"] = "success"
                        article["crawl_error"] = "low relevance"
                        article["relevance_flag"] = "low"
                        article["crawl_length"] = result.get("markdown_length", 0)
                        article["crawl_markdown"] = crawled_content
                        remaining = len(crawlable) - j - 1
                        print(f"⚠ Low embedding relevance: {relevance:.2f} ({remaining} backups remaining)")
                        if supabase:
                            save_crawl_result_to_db(supabase, article, wsj)
                        if j < len(crawlable) - 1:
                            await asyncio.sleep(delay)
                        continue

                    # Step 3: LLM verification (if enabled)
                    llm_passed = True
                    llm_analysis = None

                    if LLM_ENABLED and supabase:
                        print("    → LLM verification...", end=" ")
                        llm_analysis = analyze_content(
                            wsj_title=wsj.get("title", ""),
                            wsj_description=wsj.get("description", ""),
                            crawled_content=crawled_content,
                        )

                        if llm_analysis:
                            llm_score = llm_analysis.get("relevance_score", 0)
                            is_same_event = llm_analysis.get("is_same_event", False)
                            content_quality = llm_analysis.get("content_quality", "")

                            print(f"score={llm_score}, same_event={is_same_event}, quality={content_quality}")

                            if not is_same_event and llm_score < 7:
                                llm_passed = False
                                remaining = len(crawlable) - j - 1
                                print(f"    ⚠ LLM rejected ({remaining} backups remaining)")

                                article["crawl_status"] = "success"
                                article["crawl_error"] = "llm rejected"
                                article["relevance_flag"] = "low"
                                article["llm_same_event"] = False
                                article["llm_score"] = llm_score
                                article["crawl_length"] = result.get("markdown_length", 0)
                                article["crawl_markdown"] = crawled_content

                                crawl_result_id = save_crawl_result_to_db(supabase, article, wsj)
                                if crawl_result_id:
                                    save_analysis_to_db(supabase, crawl_result_id, llm_analysis)

                                update_domain_llm_failure(supabase, article.get("resolved_domain"))

                                if j < len(crawlable) - 1:
                                    await asyncio.sleep(delay)
                                continue
                        else:
                            print("failed (continuing without LLM)")

                    # Step 4: All checks passed - mark as success
                    article["crawl_status"] = "success"
                    article["crawl_title"] = result.get("title", "")
                    article["crawl_markdown"] = crawled_content
                    article["crawl_length"] = result.get("markdown_length", 0)
                    article["relevance_flag"] = "ok"
                    article["top_image"] = result.get("top_image")
                    if llm_analysis:
                        article["llm_same_event"] = llm_analysis.get("is_same_event", True)
                        article["llm_score"] = llm_analysis.get("relevance_score", 0)

                    llm_indicator = "LLM✓" if LLM_ENABLED and llm_analysis else ""
                    print(f"✓ {result.get('markdown_length', 0):,} chars | rel:{relevance:.2f} {llm_indicator} ✓")

                    if supabase:
                        crawl_result_id = save_crawl_result_to_db(supabase, article, wsj)

                        if llm_analysis and crawl_result_id:
                            save_analysis_to_db(supabase, crawl_result_id, llm_analysis)
                            reset_domain_llm_success(supabase, article.get("resolved_domain"))

                        skipped = mark_other_articles_skipped(supabase, wsj.get('id'), url)
                        if skipped > 0:
                            print(f"    → Marked {skipped} backup articles as skipped")

                    success = True
                    break  # Stop trying more articles for this WSJ
                else:
                    article["crawl_status"] = "failed"
                    article["crawl_error"] = normalize_crawl_error(result.get("skip_reason"))
                    run_blocked.add(domain)
                    print(f"✗ {result.get('skip_reason', 'Too short')[:30]}")

                    if supabase:
                        save_crawl_result_to_db(supabase, article, wsj)

            except Exception as e:
                article["crawl_status"] = "error"
                article["crawl_error"] = normalize_crawl_error(str(e)[:100])
                run_blocked.add(domain)
                print(f"✗ {str(e)[:30]}")

                if supabase:
                    save_crawl_result_to_db(supabase, article, wsj)

            # Rate limit before next attempt
            if j < len(crawlable) - 1:
                await asyncio.sleep(delay)

        if not success:
            print("  → All candidates failed")

        return {"success": success, "attempts": attempts}


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Crawl resolved URLs from embedding-ranked results")
    parser.add_argument('--delay', type=float, default=1.5, help='Delay between requests in seconds')
    parser.add_argument('--from-db', action='store_true', help='Load pending items from database (implies --update-db)')
    parser.add_argument('--update-db', action='store_true', help='Save crawl results to Supabase')
    parser.add_argument('--concurrent', type=int, default=1, help='Max concurrent WSJ items')
    args = parser.parse_args()

    if args.from_db:
        args.update_db = True

    delay = args.delay
    from_db = args.from_db
    update_db = args.update_db
    concurrent = max(1, args.concurrent)

    # Initialize Supabase client
    supabase = get_supabase_client() if (update_db or from_db) else None
    if (update_db or from_db) and not supabase:
        print("Error: Database credentials not found in .env.local")
        print("Required: NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY")
        return

    # Fetch domain quality stats for weighted ranking
    domain_stats = {}
    if supabase:
        try:
            domain_response = supabase.table('wsj_domain_status') \
                .select('domain, wilson_score, avg_llm_score, success_count, fail_count') \
                .eq('status', 'active') \
                .execute()
            if domain_response.data:
                domain_stats = {
                    row['domain']: {
                        'wilson_score': row.get('wilson_score'),
                        'avg_llm_score': row.get('avg_llm_score'),
                        'success_count': row.get('success_count'),
                        'fail_count': row.get('fail_count'),
                    }
                    for row in domain_response.data
                }
                print(f"Loaded domain quality stats for {len(domain_stats)} domains")
        except Exception as e:
            print(f"Warning: Could not load domain stats: {e}")

    # Load blocked domains (skip newspaper4k for these)
    blocked_domains = load_blocked_domains(supabase)
    if blocked_domains:
        print(f"Loaded {len(blocked_domains)} blocked domains (will skip newspaper4k)")

    # In-memory set for tracking domains that fail during this run
    run_blocked = set(blocked_domains)

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
            print("Error: Run embedding_rank.py and resolve_ranked.py first")
            return

        # Read all data
        all_data = []
        with open(input_path) as f:
            for line in f:
                all_data.append(json.loads(line))

        print(f"Loaded {len(all_data)} WSJ items from file")
    print("Strategy: 1 article per WSJ, fallback on failure")
    print(f"Crawl mode: {CRAWL_MODE} ({'CI detected' if IS_CI else 'local'})")
    print(f"Delay: {delay}s | Concurrent: {concurrent}")
    print("=" * 80)

    # Process items (parallel with semaphore, or sequential when concurrent=1)
    semaphore = asyncio.Semaphore(concurrent)

    tasks = [
        process_wsj_item(
            idx=i,
            total=len(all_data),
            data=data,
            delay=delay,
            supabase=supabase,
            domain_stats=domain_stats,
            run_blocked=run_blocked,
            semaphore=semaphore,
        )
        for i, data in enumerate(all_data)
    ]

    results = await asyncio.gather(*tasks)

    wsj_success = sum(1 for r in results if r["success"])
    wsj_failed = sum(1 for r in results if not r["success"])
    total_attempts = sum(r["attempts"] for r in results)

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
        print("\nRelevance scores:")
        print(f"  Min: {min(relevance_scores):.3f}")
        print(f"  Max: {max(relevance_scores):.3f}")
        print(f"  Avg: {sum(relevance_scores)/len(relevance_scores):.3f}")
        print(f"  Low relevance (<{RELEVANCE_THRESHOLD}): {len(low_relevance)}")

    if low_relevance:
        print("\n⚠ Low relevance articles:")
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
        print("\nResults saved to database.")
    else:
        print(f"\nUpdated: {input_path}")


if __name__ == "__main__":
    asyncio.run(main())
