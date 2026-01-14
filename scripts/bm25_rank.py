#!/usr/bin/env python3
"""
BM25 ranking for WSJ → Google News candidates.

Reads candidates from wsj_google_news_results.jsonl and ranks by relevance.

Usage:
    python scripts/bm25_rank.py [--top-k 5] [--min-ratio 0.6]
"""
import json
import re
import sys
from pathlib import Path

from rank_bm25 import BM25Okapi
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

STOP_WORDS = set(ENGLISH_STOP_WORDS)

# Preferred domains - should be kept even with lower BM25 scores
PREFERRED_DOMAINS = [
    'livemint.com',
    'marketwatch.com',
    'finance.yahoo.com',
    'cnbc.com',
    'finviz.com',
    'hindustantimes.com',
]


def is_preferred_domain(source_domain: str) -> bool:
    """Check if domain is in preferred list."""
    if not source_domain:
        return False
    for pref in PREFERRED_DOMAINS:
        if pref in source_domain or source_domain in pref:
            return True
    return False


def tokenize(text: str) -> list[str]:
    """
    Tokenize text for BM25.
    - Handles tickers (NVDA, AAPL)
    - Handles hyphenated words (AI-driven → AI, driven)
    - Handles dollar amounts ($10 → $10)
    """
    # First, handle hyphenated words by splitting
    text = re.sub(r'(\w+)-(\w+)', r'\1 \2', text)

    # Extract tokens including $ prefix for dollar amounts
    words = re.findall(r'\$?\b[\w]+\b', text.lower())

    # Filter stopwords and short tokens, but keep tickers (all caps, 2-5 chars)
    result = []
    for w in words:
        # Keep tickers (uppercase in original)
        if re.match(r'^[A-Z]{2,5}$', w.upper()) and w.upper() == w:
            result.append(w)
        elif w not in STOP_WORDS and len(w) > 1:
            result.append(w)

    return result


def normalize_title(title: str) -> str:
    """Remove ' - Publisher' suffix from title."""
    # Pattern: " - Some Publisher" at end
    return re.sub(r'\s*[-–]\s*[A-Za-z0-9][A-Za-z0-9 .&\']+$', '', title).strip()


def rank_candidates(
    query_text: str,
    candidates: list[dict],
    top_k: int = 10,
    min_ratio: float = 0.6,
    preferred_min_ratio: float = 0.4,
) -> list[tuple[dict, float, bool]]:
    """
    Rank candidates by BM25 relevance to query.

    Args:
        query_text: WSJ title + description
        candidates: List of article dicts
        top_k: Maximum results to return
        min_ratio: Keep if score >= min_ratio * top_score (relative threshold)
        preferred_min_ratio: Lower threshold for preferred domains

    Returns:
        List of (article, score, is_preferred) tuples
    """
    if not candidates:
        return []

    query_tokens = tokenize(query_text)

    # Build corpus from normalized candidate titles
    corpus = []
    for c in candidates:
        title = normalize_title(c.get('title', ''))
        source = c.get('source', '')
        doc_text = f"{title} {source}"
        corpus.append(tokenize(doc_text))

    bm25 = BM25Okapi(corpus)
    scores = bm25.get_scores(query_tokens)

    # Pair with scores and preferred status
    scored = []
    for c, score in zip(candidates, scores):
        is_pref = is_preferred_domain(c.get('source_domain', ''))
        scored.append((c, score, is_pref))

    # Sort by score descending
    scored.sort(key=lambda x: x[1], reverse=True)

    if not scored:
        return []

    top_score = scored[0][1]
    threshold = top_score * min_ratio if top_score > 0 else 0
    pref_threshold = top_score * preferred_min_ratio if top_score > 0 else 0

    results = []
    seen_keys = set()

    # Phase 1: Add top articles that meet normal threshold
    for article, score, is_pref in scored[:top_k]:
        if score >= threshold:
            key = f"{article.get('title', '')}|{article.get('source', '')}"
            if key not in seen_keys:
                results.append((article, score, is_pref))
                seen_keys.add(key)

    # Phase 2: Add best preferred domain articles (if not already included)
    # This ensures we don't lose valuable preferred domain results
    preferred_added = 0
    for article, score, is_pref in scored:
        if not is_pref:
            continue
        if score < pref_threshold:
            continue  # Still need minimum relevance

        key = f"{article.get('title', '')}|{article.get('source', '')}"
        if key in seen_keys:
            continue

        # Add preferred domain article
        results.append((article, score, is_pref))
        seen_keys.add(key)
        preferred_added += 1

        # Limit additional preferred to 3
        if preferred_added >= 3:
            break

    # Re-sort by score
    results.sort(key=lambda x: x[1], reverse=True)

    return results


def main():
    top_k = 5
    min_ratio = 0.6

    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg == '--top-k' and i + 1 < len(args):
            top_k = int(args[i + 1])
        elif arg == '--min-ratio' and i + 1 < len(args):
            min_ratio = float(args[i + 1])

    # Read candidates
    input_path = Path(__file__).parent / 'output' / 'wsj_google_news_results.jsonl'
    if not input_path.exists():
        print(f"Error: Run wsj_to_google_news.py first to generate {input_path}")
        sys.exit(1)

    results = []
    with open(input_path) as f:
        for line in f:
            results.append(json.loads(line))

    print(f"Loaded {len(results)} WSJ items from {input_path.name}")
    print(f"Ranking with top_k={top_k}, min_ratio={min_ratio}\n")

    ranked_results = []

    for i, r in enumerate(results):
        wsj = r['wsj']
        candidates = r['google_news']

        print("=" * 80)
        print(f"[{i+1}] WSJ: {wsj.get('title', 'N/A')}")
        print(f"    Candidates: {len(candidates)}")

        # BM25 query = WSJ title + description
        query_text = f"{wsj.get('title', '')} {wsj.get('description', '')}"

        # Rank
        ranked = rank_candidates(query_text, candidates, top_k=top_k, min_ratio=min_ratio)

        top_score = ranked[0][1] if ranked else 0
        pref_count = sum(1 for _, _, is_pref in ranked if is_pref)
        print(f"    After BM25 (min_ratio={min_ratio}, top_score={top_score:.2f}): {len(ranked)} ({pref_count} preferred)")
        print()

        for j, (article, score, is_pref) in enumerate(ranked):
            ratio = score / top_score if top_score > 0 else 0
            # Markers: ★ for preferred, + for high score, o for medium, - for low
            if is_pref:
                marker = "★"
            elif ratio >= 0.8:
                marker = "+"
            elif ratio >= 0.6:
                marker = "o"
            else:
                marker = "-"
            print(f"    {marker} [{j+1}] score={score:.2f} ({ratio:.0%})")
            print(f"       {article.get('source', 'N/A')}: {article.get('title', 'N/A')[:60]}...")

        # Build crawl-ready structure
        ranked_articles = []
        for article, score, is_pref in ranked:
            ranked_articles.append({
                'title': article.get('title', ''),
                'source': article.get('source', ''),
                'source_domain': article.get('source_domain', ''),
                'link': article.get('link', ''),
                'pubDate': article.get('pubDate', ''),
                'bm25_score': round(score, 2),
                'is_preferred': is_pref,
                'crawl_status': 'pending',  # For next step
            })

        ranked_results.append({
            'wsj': wsj,
            'ranked': ranked_articles,
        })

    # Summary
    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)

    total_candidates = sum(len(r['google_news']) for r in results)
    total_ranked = sum(len(r['ranked']) for r in ranked_results)
    total_preferred = sum(1 for r in ranked_results for a in r['ranked'] if a.get('is_preferred'))

    print(f"Total candidates: {total_candidates}")
    print(f"After BM25 filter: {total_ranked} ({total_preferred} from preferred domains)")
    print()

    # Count by preferred domain
    pref_domain_counts = {d: 0 for d in PREFERRED_DOMAINS}
    for r in ranked_results:
        for a in r['ranked']:
            domain = a.get('source_domain', '')
            for pref in PREFERRED_DOMAINS:
                if pref in domain or domain in pref:
                    pref_domain_counts[pref] += 1
                    break

    print("Preferred domain breakdown:")
    for domain, count in pref_domain_counts.items():
        marker = "✓" if count > 0 else "✗"
        print(f"  {marker} {domain}: {count}")

    print()
    print("Score interpretation:")
    print("  ★         : Preferred domain (crawlable, high quality)")
    print("  + (>=80%) : Very high relevance")
    print("  o (>=60%) : High relevance")
    print("  - (<60%)  : Moderate relevance")

    # Save results
    output_dir = Path(__file__).parent / 'output'

    # JSONL for Crawl4AI pipeline
    jsonl_path = output_dir / 'wsj_ranked_results.jsonl'
    with open(jsonl_path, 'w') as f:
        for r in ranked_results:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')

    # TXT for debugging/reading
    txt_path = output_dir / 'wsj_ranked_results.txt'
    with open(txt_path, 'w') as f:
        for r in ranked_results:
            f.write(f"WSJ: {r['wsj'].get('title', 'N/A')}\n")
            f.write(f"Ranked {len(r['ranked'])} articles:\n")
            for art in r['ranked']:
                f.write(f"  [{art['bm25_score']:.2f}] {art.get('source', 'N/A')}: {art.get('title', 'N/A')}\n")
                f.write(f"    {art.get('link', 'N/A')}\n")
            f.write("\n")

    print(f"\nResults saved to:")
    print(f"  {jsonl_path}")
    print(f"  {txt_path}")


if __name__ == "__main__":
    main()
