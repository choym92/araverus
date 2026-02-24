#!/usr/bin/env python3
"""
Phase 2 · Step 1 · Embedding Rank — Embedding-based ranking for WSJ → Google News candidates.

Uses sentence-transformers (BAAI/bge-base-en-v1.5) for semantic similarity.
Ranks backup articles by cosine similarity to WSJ title + description.

Usage:
    python scripts/embedding_rank.py [--top-k 10] [--min-score 0.3]
"""
import json
import re
import sys
from pathlib import Path

import numpy as np

_model = None


def _get_model():
    """Lazy-load sentence-transformer model (first call only)."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        print("Loading embedding model...")
        _model = SentenceTransformer('BAAI/bge-base-en-v1.5')
        print("Model loaded.\n")
    return _model


def normalize_title(title: str) -> str:
    """Remove ' - Publisher' suffix from title."""
    return re.sub(r'\s*[-–]\s*[A-Za-z0-9][A-Za-z0-9 .&\']+$', '', title).strip()


def rank_candidates(
    query_text: str,
    candidates: list[dict],
    top_k: int = 10,
    min_score: float = 0.3,
) -> list[tuple[dict, float]]:
    """
    Rank candidates by embedding cosine similarity.

    Args:
        query_text: WSJ title + description
        candidates: List of article dicts
        top_k: Maximum results to return
        min_score: Minimum cosine similarity threshold

    Returns:
        List of (article, score) tuples
    """
    if not candidates:
        return []

    # Encode query
    query_vec = _get_model().encode(query_text, normalize_embeddings=True)

    # Encode all candidates at once (batch for efficiency)
    doc_texts = []
    for c in candidates:
        title = normalize_title(c.get('title', ''))
        source = c.get('source', '')
        doc_texts.append(f"{title} {source}")

    doc_vecs = _get_model().encode(doc_texts, normalize_embeddings=True)

    # Compute cosine similarities (normalized vectors → dot product = cosine)
    scores = np.dot(doc_vecs, query_vec)

    # Pair with scores
    scored = [(c, float(score)) for c, score in zip(candidates, scores)]

    # Sort by score descending
    scored.sort(key=lambda x: x[1], reverse=True)

    # Filter by minimum score and top_k
    return [(article, score) for article, score in scored[:top_k] if score >= min_score]


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Embedding-based ranking for WSJ → Google News candidates")
    parser.add_argument('--top-k', type=int, default=30, help='Max results per WSJ item')
    parser.add_argument('--min-score', type=float, default=0.3, help='Minimum cosine similarity')
    args = parser.parse_args()

    top_k = args.top_k
    min_score = args.min_score

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
    print(f"Ranking with top_k={top_k}, min_score={min_score}\n")

    ranked_results = []

    for i, r in enumerate(results):
        wsj = r['wsj']
        candidates = r['google_news']

        print("=" * 80)
        print(f"[{i+1}/{len(results)}] WSJ: {wsj.get('title', 'N/A')}")

        print(f"    Candidates: {len(candidates)}")

        # Query = WSJ title + description
        query_text = f"{wsj.get('title', '')} {wsj.get('description', '')}"

        # Rank with embeddings
        ranked = rank_candidates(query_text, candidates, top_k=top_k, min_score=min_score)

        top_score = ranked[0][1] if ranked else 0
        print(f"    After Embedding (min_score={min_score}, top_score={top_score:.3f}): {len(ranked)}")
        print()

        for j, (article, score) in enumerate(ranked):
            if score >= 0.5:
                marker = "+"
            elif score >= 0.4:
                marker = "o"
            else:
                marker = "-"
            print(f"    {marker} [{j+1}/{len(ranked)}] score={score:.3f}")
            print(f"       {article.get('source', 'N/A')}: {article.get('title', 'N/A')[:60]}...")

        # Build output structure (compatible with resolve_ranked.py)
        ranked_articles = []
        for article, score in ranked:
            ranked_articles.append({
                'title': article.get('title', ''),
                'source': article.get('source', ''),
                'source_domain': article.get('source_domain', ''),
                'link': article.get('link', ''),
                'pubDate': article.get('pubDate', ''),
                'embedding_score': round(score, 4),
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

    print(f"Total candidates: {total_candidates}")
    print(f"After Embedding filter: {total_ranked}")
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
    print("  + (>=0.5) : High similarity")
    print("  o (>=0.4) : Medium similarity")
    print("  - (<0.4)  : Low similarity")

    # Save results
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
