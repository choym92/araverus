#!/usr/bin/env python3
"""
Embed articles and assign to story threads.

Pipeline step: runs after crawl phase.
1. Embeds title+description for articles missing embeddings (BAAI/bge-base-en-v1.5)
2. Matches each embedding to active thread centroids (cosine > 0.70 → assign)
3. Unmatched articles → LLM groups them + generates thread headlines
4. Updates centroids incrementally
5. Marks threads with last_seen > 7 days as inactive

Usage:
    python scripts/embed_and_thread.py
    python scripts/embed_and_thread.py --embed-only    # Skip thread matching
    python scripts/embed_and_thread.py --dry-run       # No DB writes
"""
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import numpy as np
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from supabase import create_client, Client

load_dotenv(Path(__file__).parent.parent / '.env.local')

# ============================================================
# Config
# ============================================================

EMBEDDING_MODEL = 'BAAI/bge-base-en-v1.5'
EMBEDDING_DIM = 768
THREAD_SIMILARITY_THRESHOLD = 0.70
THREAD_INACTIVE_DAYS = 7
BATCH_SIZE = 100

# ============================================================
# Supabase
# ============================================================

def get_supabase_client() -> Client:
    url = os.getenv('NEXT_PUBLIC_SUPABASE_URL') or os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    if not url or not key:
        raise ValueError("Missing Supabase credentials")
    return create_client(url, key)


# ============================================================
# Embedding
# ============================================================

_model: Optional[SentenceTransformer] = None


def get_embedding_model() -> SentenceTransformer:
    global _model
    if _model is None:
        print(f"Loading embedding model: {EMBEDDING_MODEL}")
        _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model


def embed_texts(texts: list[str]) -> np.ndarray:
    """Embed a list of texts. Returns (N, 768) array."""
    model = get_embedding_model()
    return model.encode(texts, normalize_embeddings=True, show_progress_bar=False)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two normalized vectors."""
    return float(np.dot(a, b))


# ============================================================
# Step 1: Embed unembedded articles
# ============================================================

def get_unembedded_articles(supabase: Client, limit: int = 500) -> list[dict]:
    """Get processed articles that don't have embeddings yet."""
    try:
        response = supabase.rpc('get_unembedded_articles', {'row_limit': limit}).execute()
        if response.data:
            return response.data
    except Exception:
        pass  # RPC may not exist yet, use fallback

    # Fallback: manual query
    # Get IDs already embedded
    embedded_response = supabase.table('wsj_embeddings') \
        .select('wsj_item_id') \
        .execute()
    embedded_ids = {row['wsj_item_id'] for row in (embedded_response.data or [])}

    # Get all processed items (fetch in pages to avoid limit issues)
    all_items = []
    page_size = 1000
    offset = 0
    while True:
        items_response = supabase.table('wsj_items') \
            .select('id, title, description, published_at') \
            .eq('processed', True) \
            .order('published_at', desc=True) \
            .range(offset, offset + page_size - 1) \
            .execute()
        batch = items_response.data or []
        all_items.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size

    return [
        item for item in all_items
        if item['id'] not in embedded_ids
    ][:limit]


def embed_articles(supabase: Client, dry_run: bool = False) -> int:
    """Embed all unembedded processed articles. Returns count."""
    articles = get_unembedded_articles(supabase)
    if not articles:
        print("No articles to embed.")
        return 0

    print(f"Embedding {len(articles)} articles...")

    # Prepare texts: title + description
    texts = []
    for a in articles:
        text = a['title']
        if a.get('description'):
            text += ' ' + a['description']
        texts.append(text)

    # Batch embed
    total_saved = 0
    for i in range(0, len(articles), BATCH_SIZE):
        batch_articles = articles[i:i + BATCH_SIZE]
        batch_texts = texts[i:i + BATCH_SIZE]

        embeddings = embed_texts(batch_texts)

        if dry_run:
            total_saved += len(batch_articles)
            print(f"  [DRY] Batch {i // BATCH_SIZE + 1}: {len(batch_articles)} embeddings")
            continue

        # Insert embeddings
        records = []
        for j, article in enumerate(batch_articles):
            records.append({
                'wsj_item_id': article['id'],
                'embedding': embeddings[j].tolist(),
                'model': EMBEDDING_MODEL,
            })

        try:
            supabase.table('wsj_embeddings').upsert(
                records, on_conflict='wsj_item_id'
            ).execute()
            total_saved += len(records)
            print(f"  Batch {i // BATCH_SIZE + 1}: saved {len(records)} embeddings")
        except Exception as e:
            print(f"  ERROR saving batch: {e}")

    return total_saved


# ============================================================
# Step 2: Thread matching
# ============================================================

def get_active_threads(supabase: Client) -> list[dict]:
    """Get active threads with their centroids."""
    response = supabase.table('wsj_story_threads') \
        .select('id, title, centroid, member_count, first_seen, last_seen') \
        .eq('active', True) \
        .execute()
    return response.data or []


def get_unthreaded_articles(supabase: Client) -> list[dict]:
    """Get articles with embeddings but no thread assignment."""
    response = supabase.table('wsj_items') \
        .select('id, title, published_at, wsj_embeddings(embedding)') \
        .eq('processed', True) \
        .is_('thread_id', 'null') \
        .order('published_at', desc=True) \
        .limit(500) \
        .execute()

    # Filter to only those with embeddings
    results = []
    for item in (response.data or []):
        emb = item.get('wsj_embeddings')
        if isinstance(emb, list) and emb:
            emb_data = emb[0]
        elif isinstance(emb, dict):
            emb_data = emb
        else:
            continue

        if emb_data and emb_data.get('embedding'):
            raw_emb = emb_data['embedding']
            # pgvector returns embedding as string "[0.1,0.2,...]"
            if isinstance(raw_emb, str):
                raw_emb = json.loads(raw_emb)
            results.append({
                'id': item['id'],
                'title': item['title'],
                'published_at': item['published_at'],
                'embedding': np.array(raw_emb, dtype=np.float32),
            })

    return results


def match_to_threads(
    articles: list[dict],
    threads: list[dict],
    threshold: float = THREAD_SIMILARITY_THRESHOLD,
) -> tuple[dict[str, str], list[dict]]:
    """Match articles to threads by centroid similarity.

    Returns:
        (matched: {article_id: thread_id}, unmatched: [articles])
    """
    matched = {}
    unmatched = []

    # Parse thread centroids
    thread_centroids = []
    for t in threads:
        centroid = t.get('centroid')
        if centroid:
            if isinstance(centroid, str):
                # Parse pgvector string format "[0.1,0.2,...]"
                centroid = json.loads(centroid.replace('[', '[').replace(']', ']'))
            thread_centroids.append({
                'id': t['id'],
                'centroid': np.array(centroid),
                'count': t['member_count'],
            })

    for article in articles:
        best_sim = 0.0
        best_thread_id = None

        for tc in thread_centroids:
            sim = cosine_similarity(article['embedding'], tc['centroid'])
            if sim > best_sim:
                best_sim = sim
                best_thread_id = tc['id']

        if best_sim >= threshold and best_thread_id:
            matched[article['id']] = best_thread_id
        else:
            unmatched.append(article)

    return matched, unmatched


def group_unmatched_with_llm(articles: list[dict]) -> list[dict]:
    """Use Gemini to group unmatched articles into new threads.

    Returns list of groups: [{title: str, article_ids: [str]}]
    """
    if not articles or len(articles) < 2:
        return []

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("  GEMINI_API_KEY not set, skipping LLM grouping")
        return []

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)

    # Prepare article list — Gemini Pro has 1M context, send all unmatched
    cap = min(len(articles), 500)
    article_list = "\n".join(
        f"{i+1}. [{a['id'][:8]}] {a['title']}"
        for i, a in enumerate(articles[:cap])
    )

    prompt = f"""Group these news articles into story threads (clusters of articles about the same ongoing story/topic).

Articles:
{article_list}

Return ONLY valid JSON object with a "groups" key. Each group should have 2+ articles.
Articles that don't fit any group should be omitted.

{{"groups": [
  {{"title": "Short descriptive thread headline", "indices": [1, 3, 7]}},
  ...
]}}

Rules:
- Group articles about the same specific news story/event
- Thread titles should be concise (5-10 words)
- Only create groups with 2+ articles
- It's OK to leave articles ungrouped"""

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0,
                response_mime_type="application/json",
            ),
        )

        raw = response.text
        result = json.loads(raw)
        groups = result if isinstance(result, list) else result.get('groups', [])
        print(f"  LLM returned {len(groups)} groups from {cap} articles")

        # Map indices back to article IDs
        output = []
        for group in groups:
            indices = group.get('indices', [])
            article_ids = []
            for idx in indices:
                if 1 <= idx <= len(articles):
                    article_ids.append(articles[idx - 1]['id'])
            if len(article_ids) >= 2:
                output.append({
                    'title': group.get('title', 'Untitled Thread'),
                    'article_ids': article_ids,
                })

        return output

    except Exception as e:
        print(f"  LLM grouping error: {e}")
        return []


def assign_threads(supabase: Client, dry_run: bool = False) -> dict:
    """Match unthreaded articles to existing or new threads."""
    articles = get_unthreaded_articles(supabase)
    if not articles:
        print("No unthreaded articles.")
        return {'matched': 0, 'new_threads': 0}

    print(f"Processing {len(articles)} unthreaded articles...")

    threads = get_active_threads(supabase)
    print(f"Active threads: {len(threads)}")

    # Step 1: Match to existing threads
    matched, unmatched = match_to_threads(articles, threads)
    print(f"  Matched to existing threads: {len(matched)}")
    print(f"  Unmatched: {len(unmatched)}")

    if not dry_run:
        # Assign matched articles to threads
        for article_id, thread_id in matched.items():
            try:
                supabase.table('wsj_items') \
                    .update({'thread_id': thread_id}) \
                    .eq('id', article_id) \
                    .execute()
            except Exception as e:
                print(f"  ERROR assigning {article_id}: {e}")

        # Update thread member counts and last_seen
        thread_updates = {}
        for article_id, thread_id in matched.items():
            article = next(a for a in articles if a['id'] == article_id)
            if thread_id not in thread_updates:
                thread_updates[thread_id] = {'count': 0, 'embeddings': []}
            thread_updates[thread_id]['count'] += 1
            thread_updates[thread_id]['embeddings'].append(article['embedding'])

        for thread_id, update in thread_updates.items():
            thread = next((t for t in threads if t['id'] == thread_id), None)
            if not thread:
                continue

            # Update centroid incrementally
            old_centroid = None
            if thread.get('centroid'):
                c = thread['centroid']
                if isinstance(c, str):
                    c = json.loads(c)
                old_centroid = np.array(c)

            if old_centroid is not None:
                old_count = thread['member_count']
                for emb in update['embeddings']:
                    old_count += 1
                    old_centroid = (old_centroid * (old_count - 1) + emb) / old_count
                new_centroid = old_centroid / np.linalg.norm(old_centroid)
            else:
                new_centroid = np.mean(update['embeddings'], axis=0)
                new_centroid = new_centroid / np.linalg.norm(new_centroid)

            try:
                supabase.table('wsj_story_threads') \
                    .update({
                        'member_count': thread['member_count'] + update['count'],
                        'centroid': new_centroid.tolist(),
                        'last_seen': datetime.utcnow().strftime('%Y-%m-%d'),
                        'updated_at': datetime.utcnow().isoformat(),
                    }) \
                    .eq('id', thread_id) \
                    .execute()
            except Exception as e:
                print(f"  ERROR updating thread {thread_id}: {e}")

    # Step 2: Group unmatched articles into new threads via LLM
    new_thread_count = 0
    if len(unmatched) >= 2:
        print("  Grouping unmatched articles with LLM...")
        groups = group_unmatched_with_llm(unmatched)
        print(f"  LLM created {len(groups)} new thread groups")

        if not dry_run:
            for group in groups:
                # Compute centroid from member embeddings
                member_articles = [a for a in unmatched if a['id'] in group['article_ids']]
                if not member_articles:
                    continue

                embeddings = np.array([a['embedding'] for a in member_articles])
                centroid = np.mean(embeddings, axis=0)
                centroid = centroid / np.linalg.norm(centroid)

                dates = [a['published_at'][:10] for a in member_articles if a.get('published_at')]
                first_seen = min(dates) if dates else datetime.utcnow().strftime('%Y-%m-%d')
                last_seen = max(dates) if dates else datetime.utcnow().strftime('%Y-%m-%d')

                try:
                    # Create thread
                    thread_response = supabase.table('wsj_story_threads').insert({
                        'title': group['title'],
                        'centroid': centroid.tolist(),
                        'member_count': len(group['article_ids']),
                        'first_seen': first_seen,
                        'last_seen': last_seen,
                        'active': True,
                    }).execute()

                    if thread_response.data:
                        new_thread_id = thread_response.data[0]['id']
                        # Assign articles
                        for aid in group['article_ids']:
                            supabase.table('wsj_items') \
                                .update({'thread_id': new_thread_id}) \
                                .eq('id', aid) \
                                .execute()
                        new_thread_count += 1

                except Exception as e:
                    print(f"  ERROR creating thread '{group['title']}': {e}")

    return {'matched': len(matched), 'new_threads': new_thread_count}


# ============================================================
# Step 3: Deactivate stale threads
# ============================================================

def deactivate_stale_threads(supabase: Client, days: int = THREAD_INACTIVE_DAYS, dry_run: bool = False) -> int:
    """Mark threads with last_seen > N days ago as inactive."""
    cutoff = (datetime.utcnow() - timedelta(days=days)).strftime('%Y-%m-%d')

    response = supabase.table('wsj_story_threads') \
        .select('id, title, last_seen') \
        .eq('active', True) \
        .lt('last_seen', cutoff) \
        .execute()

    stale = response.data or []
    if not stale:
        return 0

    print(f"Deactivating {len(stale)} stale threads (last_seen < {cutoff})")

    if dry_run:
        for t in stale:
            print(f"  [DRY] {t['title']} (last: {t['last_seen']})")
        return len(stale)

    for t in stale:
        try:
            supabase.table('wsj_story_threads') \
                .update({'active': False, 'updated_at': datetime.utcnow().isoformat()}) \
                .eq('id', t['id']) \
                .execute()
        except Exception as e:
            print(f"  ERROR deactivating {t['id']}: {e}")

    return len(stale)


# ============================================================
# Main
# ============================================================

def main():
    dry_run = '--dry-run' in sys.argv
    embed_only = '--embed-only' in sys.argv

    print("=" * 60)
    print("Embed & Thread Pipeline")
    print("=" * 60)

    supabase = get_supabase_client()

    # Step 1: Embed
    print("\n[1/3] Embedding articles...")
    embedded = embed_articles(supabase, dry_run=dry_run)
    print(f"  Embedded: {embedded}")

    if embed_only:
        print("\n--embed-only flag set, skipping thread matching.")
        return

    # Step 2: Thread matching
    print("\n[2/3] Assigning threads...")
    result = assign_threads(supabase, dry_run=dry_run)
    print(f"  Matched: {result['matched']}, New threads: {result['new_threads']}")

    # Step 3: Deactivate stale
    print("\n[3/3] Deactivating stale threads...")
    deactivated = deactivate_stale_threads(supabase, dry_run=dry_run)
    print(f"  Deactivated: {deactivated}")

    print("\n" + "=" * 60)
    print("Done.")


if __name__ == "__main__":
    main()
