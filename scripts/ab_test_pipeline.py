#!/usr/bin/env python3
"""
A/B Test: OLD pipeline (main) vs NEW pipeline (feature/phase0-wsj-preprocess).

Compares today's actual cron results (OLD: regex queries, MiniLM) against
the same WSJ items run through the new pipeline (NEW: LLM queries, bge-base).

All embedding scores use bge-base for fair comparison.

Steps:
    1. Export today's WSJ items from DB
    2. Get OLD ranked results from wsj_crawl_results
    3. Re-rank OLD results with bge-base
    4. Backfill LLM search queries if needed
    5. Run NEW search pipeline
    6. Rank NEW with bge-base
    7. Print comparison table

Usage:
    # Full pipeline (steps 1-7)
    python scripts/ab_test_pipeline.py

    # Skip search (use existing google_news_results.jsonl for NEW)
    python scripts/ab_test_pipeline.py --skip-search

    # Skip LLM preprocessing (if already backfilled)
    python scripts/ab_test_pipeline.py --skip-preprocess
"""
import asyncio
import json
import os
import sys
from collections import Counter
from datetime import date
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from supabase import create_client, Client

# Add scripts dir to path
sys.path.insert(0, str(Path(__file__).parent))

# Load environment variables
load_dotenv(Path(__file__).parent.parent / '.env.local')

# ============================================================
# Config
# ============================================================

TODAY = date.today().isoformat()
OUTPUT_DIR = Path(__file__).parent / 'output'
AB_DIR = OUTPUT_DIR / 'ab_test'

# ============================================================
# Supabase
# ============================================================

def get_supabase() -> Client:
    url = os.getenv('NEXT_PUBLIC_SUPABASE_URL') or os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    if not url or not key:
        raise ValueError("Missing SUPABASE credentials in .env.local")
    return create_client(url, key)


# ============================================================
# Step 1: Export today's WSJ items from DB
# ============================================================

def step1_export_items(sb: Client) -> list[dict]:
    """Export today's WSJ items from DB (bypass --export which needs searched=false)."""
    print("=" * 70)
    print("STEP 1: Export today's WSJ items from DB")
    print("=" * 70)

    resp = sb.table('wsj_items') \
        .select('*') \
        .gte('published_at', f'{TODAY}T00:00:00') \
        .order('published_at', desc=True) \
        .execute()

    items = resp.data or []
    print(f"  Found {len(items)} items for {TODAY}")

    if not items:
        print("  ERROR: No items found for today.")
        sys.exit(1)

    # Export to JSONL (format compatible with wsj_to_google_news.py)
    AB_DIR.mkdir(parents=True, exist_ok=True)
    jsonl_path = AB_DIR / 'today_wsj_items.jsonl'

    with open(jsonl_path, 'w') as f:
        for item in items:
            export_item = {
                'id': item['id'],
                'title': item['title'],
                'description': item['description'],
                'link': item['link'],
                'pubDate': item['published_at'],
                'feed_name': item['feed_name'],
                'creator': item.get('creator'),
                'subcategory': item.get('subcategory'),
                'extracted_entities': item.get('extracted_entities'),
                'extracted_keywords': item.get('extracted_keywords'),
                'extracted_tickers': item.get('extracted_tickers'),
                'llm_search_queries': item.get('llm_search_queries'),
            }
            f.write(json.dumps(export_item, ensure_ascii=False) + '\n')

    print(f"  Exported to: {jsonl_path}")

    # Show LLM preprocessing status
    has_llm = sum(1 for i in items if i.get('llm_search_queries'))
    print(f"  With llm_search_queries: {has_llm}/{len(items)}")

    return items


# ============================================================
# Step 2: Get OLD crawl results from DB
# ============================================================

def step2_get_old_results(sb: Client, items: list[dict]) -> list[dict]:
    """Get OLD ranked results from wsj_crawl_results for today's items."""
    print("\n" + "=" * 70)
    print("STEP 2: Get OLD pipeline results from DB")
    print("=" * 70)

    item_ids = [i['id'] for i in items]

    all_results = []
    for batch_start in range(0, len(item_ids), 50):
        batch = item_ids[batch_start:batch_start + 50]
        resp = sb.table('wsj_crawl_results') \
            .select('wsj_item_id, wsj_title, title, source, '
                     'embedding_score, resolved_url, resolved_domain') \
            .in_('wsj_item_id', batch) \
            .execute()
        all_results.extend(resp.data or [])

    print(f"  OLD crawl results: {len(all_results)}")

    # Per-item stats
    per_item = Counter(r['wsj_item_id'] for r in all_results)
    items_with = len(per_item)
    items_without = len(items) - items_with
    counts = list(per_item.values()) if per_item else [0]

    print(f"  Items with results: {items_with}")
    print(f"  Items without results: {items_without}")
    print(f"  Candidates/item: min={min(counts)} avg={sum(counts)/len(counts):.1f} max={max(counts)}")

    # MiniLM score distribution (from OLD cron)
    miniLM_scores = [r['embedding_score'] for r in all_results if r.get('embedding_score')]
    if miniLM_scores:
        print(f"\n  OLD MiniLM scores: n={len(miniLM_scores)}")
        print(f"    min={min(miniLM_scores):.3f} avg={sum(miniLM_scores)/len(miniLM_scores):.3f} max={max(miniLM_scores):.3f}")

    # Save for reference
    old_path = AB_DIR / 'old_crawl_results.json'
    with open(old_path, 'w') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"\n  Saved to: {old_path}")

    return all_results


# ============================================================
# Step 3: Re-rank OLD results with bge-base
# ============================================================

def step3_rerank_old_with_bge(items: list[dict], old_results: list[dict]) -> dict:
    """Re-rank OLD results using bge-base for fair comparison."""
    print("\n" + "=" * 70)
    print("STEP 3: Re-rank OLD results with bge-base")
    print("=" * 70)

    from sentence_transformers import SentenceTransformer

    print("  Loading bge-base model...")
    model = SentenceTransformer('BAAI/bge-base-en-v1.5')
    print("  Model loaded.")

    # Build item lookup
    item_map = {i['id']: i for i in items}

    # Group OLD results by wsj_item_id
    from collections import defaultdict
    grouped = defaultdict(list)
    for r in old_results:
        grouped[r['wsj_item_id']].append(r)

    all_bge_scores = []
    per_item_results = {}

    for wsj_id, candidates in grouped.items():
        item = item_map.get(wsj_id)
        if not item:
            continue

        # Query = WSJ title + description (same as embedding_rank.py)
        query_text = f"{item['title']} {item.get('description', '')}"
        query_vec = model.encode(query_text, normalize_embeddings=True)

        # Encode candidates
        doc_texts = [f"{c.get('title', '')} {c.get('source', '')}" for c in candidates]
        doc_vecs = model.encode(doc_texts, normalize_embeddings=True)

        scores = np.dot(doc_vecs, query_vec).tolist()

        scored = []
        for c, score in zip(candidates, scores):
            c['bge_score'] = round(float(score), 4)
            scored.append(c)
            all_bge_scores.append(float(score))

        scored.sort(key=lambda x: x['bge_score'], reverse=True)
        per_item_results[wsj_id] = scored

    print(f"\n  Re-ranked {len(all_bge_scores)} candidates across {len(per_item_results)} items")

    if all_bge_scores:
        print(f"  OLD bge-base scores: n={len(all_bge_scores)}")
        print(f"    min={min(all_bge_scores):.3f} avg={sum(all_bge_scores)/len(all_bge_scores):.3f} max={max(all_bge_scores):.3f}")
        print(f"    >= 0.7: {sum(1 for s in all_bge_scores if s >= 0.7)}")
        print(f"    >= 0.5: {sum(1 for s in all_bge_scores if s >= 0.5)}")

    # Save
    old_bge_path = AB_DIR / 'old_bge_rescored.json'
    with open(old_bge_path, 'w') as f:
        json.dump(per_item_results, f, ensure_ascii=False, indent=2, default=str)
    print(f"  Saved to: {old_bge_path}")

    return {
        'per_item': per_item_results,
        'all_scores': all_bge_scores,
    }


# ============================================================
# Step 4: Backfill LLM preprocessing
# ============================================================

def step4_backfill_preprocess(sb: Client, items: list[dict]) -> list[dict]:
    """Backfill llm_search_queries for items that don't have them."""
    print("\n" + "=" * 70)
    print("STEP 4: Backfill LLM preprocessing (Gemini Flash-Lite)")
    print("=" * 70)

    needs_preprocess = [i for i in items if not i.get('llm_search_queries')]

    if not needs_preprocess:
        print("  All items already have llm_search_queries. Skipping.")
        return items

    print(f"  Items needing preprocessing: {len(needs_preprocess)}")

    from wsj_preprocess import preprocess_item, save_preprocess_result

    success = 0
    for idx, item in enumerate(needs_preprocess):
        title = item['title']
        desc = item.get('description', '')
        print(f"  [{idx+1}/{len(needs_preprocess)}] {title[:60]}...")

        result = preprocess_item(title, desc)
        if result is None:
            print("    FAILED")
            continue

        success += 1
        item['llm_search_queries'] = result.search_queries
        item['extracted_entities'] = result.entities
        item['extracted_keywords'] = result.keywords
        item['extracted_tickers'] = result.tickers

        # Save to DB
        save_preprocess_result(sb, item['id'], result)
        print(f"    queries: {result.search_queries}")

    print(f"\n  Preprocessed: {success}/{len(needs_preprocess)}")

    # Re-export JSONL with updated llm_search_queries
    jsonl_path = AB_DIR / 'today_wsj_items.jsonl'
    with open(jsonl_path, 'w') as f:
        for item in items:
            export_item = {
                'id': item['id'],
                'title': item['title'],
                'description': item.get('description'),
                'link': item.get('link'),
                'pubDate': item.get('published_at'),
                'feed_name': item.get('feed_name'),
                'creator': item.get('creator'),
                'subcategory': item.get('subcategory'),
                'extracted_entities': item.get('extracted_entities'),
                'extracted_keywords': item.get('extracted_keywords'),
                'extracted_tickers': item.get('extracted_tickers'),
                'llm_search_queries': item.get('llm_search_queries'),
            }
            f.write(json.dumps(export_item, ensure_ascii=False) + '\n')

    print(f"  Updated JSONL: {jsonl_path}")
    return items


# ============================================================
# Step 5: Run NEW search pipeline
# ============================================================

def step5_run_new_search(items: list[dict]) -> list[dict]:
    """Run NEW search pipeline (wsj_to_google_news.py logic) on today's items."""
    print("\n" + "=" * 70)
    print("STEP 5: Run NEW Google News search")
    print("=" * 70)

    jsonl_path = AB_DIR / 'today_wsj_items.jsonl'
    print(f"  Input: {jsonl_path}")

    # Import search functions from wsj_to_google_news
    from wsj_to_google_news import (
        load_wsj_jsonl,
        build_queries,
        search_multi_query,
        parse_rss_date,
    )
    import httpx

    wsj_items = load_wsj_jsonl(str(jsonl_path))
    print(f"  Loaded {len(wsj_items)} WSJ items")

    results = []

    async def run_search():
        async with httpx.AsyncClient() as client:
            for i, wsj in enumerate(wsj_items):
                print(f"\n  [{i+1}/{len(wsj_items)}] {wsj['title'][:60]}...")

                wsj_date = parse_rss_date(wsj.get('pubDate', ''))
                llm_queries = wsj.get('llm_search_queries') or None
                queries = build_queries(wsj['title'], wsj.get('description', ''), llm_queries=llm_queries)

                print(f"    Queries ({len(queries)}):")
                for j, q in enumerate(queries):
                    print(f"      Q{j+1}: {q[:65]}{'...' if len(q) > 65 else ''}")

                articles, instr = await search_multi_query(queries, client, wsj_date, delay_query=1.0)
                print(f"    Found: {len(articles)} articles")

                results.append({
                    'wsj': wsj,
                    'queries': queries,
                    'google_news': articles,
                })

                if i < len(wsj_items) - 1:
                    await asyncio.sleep(2.0)

    asyncio.run(run_search())

    # Save results
    results_with = [r for r in results if r['google_news']]
    results_without = [r for r in results if not r['google_news']]

    new_results_path = AB_DIR / 'new_google_news_results.jsonl'
    with open(new_results_path, 'w') as f:
        for r in results_with:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')

    print(f"\n  NEW search: {len(results_with)} with articles, {len(results_without)} without")
    print(f"  Total candidates: {sum(len(r['google_news']) for r in results)}")
    print(f"  Saved to: {new_results_path}")

    return results


# ============================================================
# Step 6: Rank NEW with bge-base
# ============================================================

def step6_rank_new_with_bge(search_results: list[dict]) -> dict:
    """Rank NEW search results with bge-base."""
    print("\n" + "=" * 70)
    print("STEP 6: Rank NEW results with bge-base")
    print("=" * 70)

    from embedding_rank import rank_candidates
    from domain_utils import load_blocked_domains, is_blocked_domain

    blocked_domains = load_blocked_domains()
    print(f"  Blocked domains: {len(blocked_domains)}")

    all_scores = []
    per_item_results = {}

    for i, r in enumerate(search_results):
        wsj = r['wsj']
        candidates = r['google_news']

        if not candidates:
            continue

        # Filter blocked domains
        candidates = [c for c in candidates
                      if not is_blocked_domain(c.get('source_domain', ''), blocked_domains)]

        query_text = f"{wsj.get('title', '')} {wsj.get('description', '')}"
        ranked = rank_candidates(query_text, candidates, top_k=10, min_score=0.3)

        item_scores = []
        ranked_list = []
        for article, score in ranked:
            item_scores.append(score)
            all_scores.append(score)
            ranked_list.append({
                'title': article.get('title', ''),
                'source': article.get('source', ''),
                'source_domain': article.get('source_domain', ''),
                'bge_score': round(score, 4),
            })

        wsj_id = wsj.get('id', f'item_{i}')
        per_item_results[wsj_id] = ranked_list

        top = ranked_list[0]['bge_score'] if ranked_list else 0
        print(f"  [{i+1}] {wsj['title'][:50]}... → {len(ranked_list)} ranked (top={top:.3f})")

    print(f"\n  NEW bge-base scores: n={len(all_scores)}")
    if all_scores:
        print(f"    min={min(all_scores):.3f} avg={sum(all_scores)/len(all_scores):.3f} max={max(all_scores):.3f}")
        print(f"    >= 0.7: {sum(1 for s in all_scores if s >= 0.7)}")
        print(f"    >= 0.5: {sum(1 for s in all_scores if s >= 0.5)}")

    # Save
    new_bge_path = AB_DIR / 'new_bge_ranked.json'
    with open(new_bge_path, 'w') as f:
        json.dump(per_item_results, f, ensure_ascii=False, indent=2)
    print(f"  Saved to: {new_bge_path}")

    return {
        'per_item': per_item_results,
        'all_scores': all_scores,
    }


# ============================================================
# Step 7: Compare OLD vs NEW
# ============================================================

def step7_compare(
    items: list[dict],
    old_results: list[dict],
    old_bge: dict,
    search_results: list[dict],
    new_bge: dict,
):
    """Print side-by-side comparison of OLD vs NEW pipeline."""
    print("\n" + "=" * 70)
    print("STEP 7: A/B COMPARISON — OLD vs NEW")
    print("=" * 70)

    old_scores = old_bge['all_scores']
    new_scores = new_bge['all_scores']
    old_per_item = old_bge['per_item']
    new_per_item = new_bge['per_item']

    # --- Aggregate Metrics ---
    old_total_candidates = len(old_results)
    new_total_candidates = sum(len(r['google_news']) for r in search_results)

    old_items_with = len(old_per_item)
    new_items_with = sum(1 for r in search_results if r['google_news'])

    old_items_without = len(items) - old_items_with
    new_items_without = len(items) - new_items_with

    # Avg candidates per item
    old_counts = [len(v) for v in old_per_item.values()] if old_per_item else [0]
    new_counts_per_item = [len(r['google_news']) for r in search_results]

    # OLD pipeline used only top ranked ones from DB (not raw candidates)
    # So old_total_candidates represents ranked results, not raw search results

    print(f"\n  Date: {TODAY}")
    print(f"  WSJ items: {len(items)}")

    print(f"\n  {'Metric':<40} {'OLD (main)':>15} {'NEW (feature)':>15} {'Δ':>10}")
    print(f"  {'-'*40} {'-'*15} {'-'*15} {'-'*10}")

    def row(label, old_val, new_val, fmt='.0f', higher_better=True):
        if isinstance(old_val, float) and isinstance(new_val, float):
            delta = new_val - old_val
            sign = '+' if delta > 0 else ''
            delta_str = f"{sign}{delta:{fmt}}"
            # Color hint
            if higher_better:
                marker = '↑' if delta > 0 else ('↓' if delta < 0 else '=')
            else:
                marker = '↓' if delta > 0 else ('↑' if delta < 0 else '=')
            print(f"  {label:<40} {old_val:>15{fmt}} {new_val:>15{fmt}} {delta_str:>8} {marker}")
        else:
            old_s = str(old_val)
            new_s = str(new_val)
            print(f"  {label:<40} {old_s:>15} {new_s:>15}")

    # Note about OLD candidates
    print("\n  Note: OLD 'candidates' = ranked results from DB (post-resolve)")
    print("  Note: NEW 'candidates' = raw Google News search results\n")

    row("Ranked candidates (in DB/output)", float(len(old_scores)), float(len(new_scores)))
    row("Raw search candidates", float(old_total_candidates), float(new_total_candidates))
    row("Items with candidates", float(old_items_with), float(new_items_with))
    row("Items with 0 candidates", float(old_items_without), float(new_items_without), higher_better=False)

    if old_counts:
        row("Avg ranked/item", sum(old_counts)/len(old_counts), sum(len(v) for v in new_per_item.values())/(len(new_per_item) or 1), fmt='.1f')

    print()

    # bge-base score comparison (the key metric!)
    if old_scores and new_scores:
        row("bge-base min", min(old_scores), min(new_scores), fmt='.3f')
        row("bge-base avg", sum(old_scores)/len(old_scores), sum(new_scores)/len(new_scores), fmt='.3f')
        row("bge-base max", max(old_scores), max(new_scores), fmt='.3f')

        # Percentile comparison
        old_arr = np.array(old_scores)
        new_arr = np.array(new_scores)
        for pct in [25, 50, 75, 90]:
            row(f"bge-base P{pct}", float(np.percentile(old_arr, pct)), float(np.percentile(new_arr, pct)), fmt='.3f')

        print()
        row("Candidates bge >= 0.7", float(sum(1 for s in old_scores if s >= 0.7)), float(sum(1 for s in new_scores if s >= 0.7)))
        row("Candidates bge >= 0.5", float(sum(1 for s in old_scores if s >= 0.5)), float(sum(1 for s in new_scores if s >= 0.5)))
        row("Candidates bge >= 0.3", float(sum(1 for s in old_scores if s >= 0.3)), float(sum(1 for s in new_scores if s >= 0.3)))

    # --- Unique domains ---
    print()
    old_domains = set()
    for candidates in old_per_item.values():
        for c in candidates:
            d = c.get('resolved_domain') or c.get('source_domain', '')
            if d:
                old_domains.add(d)

    new_domains = set()
    for candidates in new_per_item.values():
        for c in candidates:
            d = c.get('source_domain', '')
            if d:
                new_domains.add(d)

    row("Unique domains", float(len(old_domains)), float(len(new_domains)))

    # Domains only in NEW
    new_only = new_domains - old_domains
    if new_only:
        print(f"\n  Domains only in NEW ({len(new_only)}):")
        for d in sorted(new_only)[:15]:
            print(f"    + {d}")

    # --- Per-item comparison ---
    print(f"\n\n  {'='*70}")
    print("  PER-ITEM COMPARISON (bge-base top score)")
    print(f"  {'='*70}")
    print(f"\n  {'WSJ Title':<50} {'OLD top':>10} {'NEW top':>10} {'Δ':>8}")
    print(f"  {'-'*50} {'-'*10} {'-'*10} {'-'*8}")

    item_map = {i['id']: i for i in items}
    improvements = 0
    regressions = 0

    for wsj_id in sorted(old_per_item.keys() | new_per_item.keys()):
        item = item_map.get(wsj_id)
        title = (item['title'][:47] + '...') if item else wsj_id[:47]

        old_top = max((c['bge_score'] for c in old_per_item.get(wsj_id, [])), default=0)
        new_top = max((c['bge_score'] for c in new_per_item.get(wsj_id, [])), default=0)
        delta = new_top - old_top

        if delta > 0.01:
            improvements += 1
            marker = '↑'
        elif delta < -0.01:
            regressions += 1
            marker = '↓'
        else:
            marker = '='

        sign = '+' if delta > 0 else ''
        print(f"  {title:<50} {old_top:>10.3f} {new_top:>10.3f} {sign}{delta:>7.3f} {marker}")

    print(f"\n  Improvements: {improvements} | Regressions: {regressions} | Same: {len(items) - improvements - regressions}")

    # --- Query comparison sample ---
    print(f"\n\n  {'='*70}")
    print("  QUERY COMPARISON (first 5 items)")
    print(f"  {'='*70}")

    for r in search_results[:5]:
        wsj = r['wsj']
        print(f"\n  WSJ: {wsj['title'][:60]}")
        llm_q = wsj.get('llm_search_queries') or []
        print(f"    OLD Q1 (title-only): {wsj['title'][:60]}")
        if llm_q:
            for j, q in enumerate(llm_q):
                print(f"    NEW Q{j+2} (LLM): {q[:60]}")
        print(f"    OLD candidates: {len(old_per_item.get(wsj.get('id', ''), []))}")
        print(f"    NEW candidates: {len(r['google_news'])}")

    # Save full report
    report_path = AB_DIR / 'ab_comparison_report.txt'
    # (The console output is the report — user can redirect)
    print(f"\n\n  Output dir: {AB_DIR}")


# ============================================================
# Main
# ============================================================

def main():
    skip_search = '--skip-search' in sys.argv
    skip_preprocess = '--skip-preprocess' in sys.argv

    print("=" * 70)
    print("  A/B TEST: OLD (main) vs NEW (feature/phase0-wsj-preprocess)")
    print(f"  Date: {TODAY}")
    print(f"  skip_search={skip_search}, skip_preprocess={skip_preprocess}")
    print("=" * 70)

    sb = get_supabase()

    # Step 1: Export today's items
    items = step1_export_items(sb)

    # Step 2: Get OLD results from DB
    old_results = step2_get_old_results(sb, items)

    # Step 3: Re-rank OLD with bge-base
    old_bge = step3_rerank_old_with_bge(items, old_results)

    # Step 4: Backfill LLM preprocessing
    if not skip_preprocess:
        items = step4_backfill_preprocess(sb, items)
    else:
        print("\n  Skipping LLM preprocessing (--skip-preprocess)")

    # Step 5: Run NEW search
    if not skip_search:
        search_results = step5_run_new_search(items)
    else:
        print("\n  Skipping search (--skip-search), loading from file...")
        new_results_path = AB_DIR / 'new_google_news_results.jsonl'
        if not new_results_path.exists():
            print(f"  ERROR: {new_results_path} not found. Run without --skip-search first.")
            sys.exit(1)
        search_results = []
        with open(new_results_path) as f:
            for line in f:
                if line.strip():
                    search_results.append(json.loads(line))
        # Add items without results
        result_titles = {r['wsj']['title'] for r in search_results}
        for item in items:
            if item['title'] not in result_titles:
                search_results.append({
                    'wsj': {
                        'id': item['id'],
                        'title': item['title'],
                        'description': item.get('description', ''),
                        'llm_search_queries': item.get('llm_search_queries'),
                    },
                    'queries': [],
                    'google_news': [],
                })
        print(f"  Loaded {len(search_results)} results from file")

    # Step 6: Rank NEW with bge-base
    new_bge = step6_rank_new_with_bge(search_results)

    # Step 7: Compare!
    step7_compare(items, old_results, old_bge, search_results, new_bge)


if __name__ == '__main__':
    main()
