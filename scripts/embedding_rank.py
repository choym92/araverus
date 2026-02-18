#!/usr/bin/env python3
"""
Embedding-based ranking for WSJ → Google News candidates.

Uses sentence-transformers (all-MiniLM-L6-v2) for semantic similarity.
Ranks backup articles by cosine similarity to WSJ title + description.

Usage:
    python scripts/embedding_rank.py [--top-k 5] [--min-score 0.3]
"""
import json
import re
import sys
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

# Import shared domain utilities
from domain_utils import load_preferred_domains, is_preferred_domain, load_blocked_domains, is_blocked_domain

# Load model (downloads on first run, ~80MB)
print("Loading embedding model...")
MODEL = SentenceTransformer('all-MiniLM-L6-v2')
print("Model loaded.\n")


def normalize_title(title: str) -> str:
    """Remove ' - Publisher' suffix from title."""
    return re.sub(r'\s*[-–]\s*[A-Za-z0-9][A-Za-z0-9 .&\']+$', '', title).strip()


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors."""
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def rank_candidates(
    query_text: str,
    candidates: list[dict],
    preferred_domains: list[str],
    top_k: int = 10,
    min_score: float = 0.3,
) -> list[tuple[dict, float, bool]]:
    """
    Rank candidates by embedding cosine similarity.

    Args:
        query_text: WSJ title + description
        candidates: List of article dicts
        preferred_domains: List of preferred domains (used for score threshold bypass)
        top_k: Maximum results to return
        min_score: Minimum cosine similarity threshold

    Returns:
        List of (article, score, is_preferred) tuples
    """
    if not candidates:
        return []

    # Encode query
    query_vec = MODEL.encode(query_text, normalize_embeddings=True)

    # Encode all candidates at once (batch for efficiency)
    doc_texts = []
    for c in candidates:
        title = normalize_title(c.get('title', ''))
        source = c.get('source', '')
        doc_texts.append(f"{title} {source}")

    doc_vecs = MODEL.encode(doc_texts, normalize_embeddings=True)

    # Compute cosine similarities
    # Since vectors are normalized, dot product = cosine similarity
    scores = np.dot(doc_vecs, query_vec)

    # Pair with scores and preferred status
    scored = []
    for c, score in zip(candidates, scores):
        is_pref = is_preferred_domain(c.get('source_domain', ''), preferred_domains)
        scored.append((c, float(score), is_pref))

    # Sort by score descending
    scored.sort(key=lambda x: x[1], reverse=True)

    # Filter by minimum score and top_k
    results = []
    for article, score, is_pref in scored[:top_k]:
        if score >= min_score or is_pref:
            results.append((article, score, is_pref))

    return results


def main():
    top_k = 5
    min_score = 0.3

    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg == '--top-k' and i + 1 < len(args):
            top_k = int(args[i + 1])
        elif arg == '--min-score' and i + 1 < len(args):
            min_score = float(args[i + 1])

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

    # Load preferred domains (top 10 from DB by weighted_score)
    print("Loading preferred domains...")
    preferred_domains = load_preferred_domains(top_n=10)
    print(f"  Using {len(preferred_domains)} preferred domains")

    # Load blocked domains to filter before ranking
    blocked_domains = load_blocked_domains()
    print(f"  Blocked domains: {len(blocked_domains)}")

    print(f"Ranking with top_k={top_k}, min_score={min_score}\n")

    ranked_results = []

    for i, r in enumerate(results):
        wsj = r['wsj']
        candidates = r['google_news']

        print("=" * 80)
        print(f"[{i+1}/{len(results)}] WSJ: {wsj.get('title', 'N/A')}")

        # Filter out blocked domains before ranking
        candidates = [c for c in candidates
                      if not is_blocked_domain(c.get('source_domain', ''), blocked_domains)]
        print(f"    Candidates: {len(candidates)} (after blocked filter)")

        # Query = WSJ title + description
        query_text = f"{wsj.get('title', '')} {wsj.get('description', '')}"

        # Rank with embeddings
        ranked = rank_candidates(query_text, candidates, preferred_domains, top_k=top_k, min_score=min_score)

        top_score = ranked[0][1] if ranked else 0
        pref_count = sum(1 for _, _, is_pref in ranked if is_pref)
        print(f"    After Embedding (min_score={min_score}, top_score={top_score:.3f}): {len(ranked)} ({pref_count} preferred)")
        print()

        for j, (article, score, is_pref) in enumerate(ranked):
            if is_pref:
                marker = "★"
            elif score >= 0.5:
                marker = "+"
            elif score >= 0.4:
                marker = "o"
            else:
                marker = "-"
            print(f"    {marker} [{j+1}/{len(ranked)}] score={score:.3f}")
            print(f"       {article.get('source', 'N/A')}: {article.get('title', 'N/A')[:60]}...")

        # Build output structure (compatible with resolve_ranked.py)
        ranked_articles = []
        for article, score, is_pref in ranked:
            ranked_articles.append({
                'title': article.get('title', ''),
                'source': article.get('source', ''),
                'source_domain': article.get('source_domain', ''),
                'link': article.get('link', ''),
                'pubDate': article.get('pubDate', ''),
                'embedding_score': round(score, 4),
                'is_preferred': is_pref,
                'crawl_status': 'pending',
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
    print(f"After Embedding filter: {total_ranked} ({total_preferred} from preferred domains)")
    print()

    # Score distribution
    all_scores = [a['embedding_score'] for r in ranked_results for a in r['ranked']]
    if all_scores:
        print("Score distribution:")
        print(f"  Min: {min(all_scores):.3f}")
        print(f"  Max: {max(all_scores):.3f}")
        print(f"  Avg: {sum(all_scores)/len(all_scores):.3f}")

    print()
    print("Score interpretation (cosine similarity):")
    print("  ★         : Preferred domain")
    print("  + (>=0.5) : High similarity")
    print("  o (>=0.4) : Medium similarity")
    print("  - (<0.4)  : Low similarity")

    # Save results (same filename as BM25 for pipeline compatibility)
    output_dir = Path(__file__).parent / 'output'
    jsonl_path = output_dir / 'wsj_ranked_results.jsonl'
    with open(jsonl_path, 'w') as f:
        for r in ranked_results:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')

    # Also save TXT for easy reading
    txt_path = output_dir / 'wsj_ranked_results.txt'
    with open(txt_path, 'w') as f:
        for r in ranked_results:
            f.write(f"WSJ: {r['wsj'].get('title', 'N/A')}\n")
            f.write(f"Ranked {len(r['ranked'])} articles:\n")
            for art in r['ranked']:
                f.write(f"  [{art['embedding_score']:.3f}] {art.get('source', 'N/A')}: {art.get('title', 'N/A')}\n")
                f.write(f"    {art.get('link', 'N/A')}\n")
            f.write("\n")

    print("\nResults saved to:")
    print(f"  {jsonl_path}")
    print(f"  {txt_path}")


if __name__ == "__main__":
    main()
