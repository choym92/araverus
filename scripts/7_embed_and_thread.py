#!/usr/bin/env python3
"""
Phase 4.5 · Embed & Thread — Embed articles and assign to story threads.

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
from datetime import datetime, timedelta, timezone
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
THREAD_BASE_THRESHOLD = 0.73       # Base cosine similarity for thread matching (tuned from 0.62, see docs/1.2.1)
THREAD_TIME_PENALTY = 0.01         # +0.01 per day gap between article and thread last_seen
THREAD_SIZE_PENALTY = 0.04         # Anti-gravity: 0.04 × ln(member_count + 1) — doubled from 0.02
THREAD_MERGE_THRESHOLD = 0.92      # Above this, new thread merges into existing
CENTROID_EMA_BASE_ALPHA = 0.1      # EMA alpha base, divided by ln(member_count + 2)
THREAD_ARCHIVE_DAYS = 14           # Days of inactivity before archiving
LLM_GROUP_MIN_SIMILARITY = 0.60    # Min avg pairwise cosine similarity for LLM group validation (tuned from 0.42, see docs/1.2.1)
LLM_GROUP_MIN_PAIR_FLOOR = 0.25    # No pair in LLM group can be below this
LLM_GROUP_MAX_SIZE = 8             # Max articles per LLM group
THREAD_HARD_CAP = 50               # Threads above this enter "frozen" mode
THREAD_FROZEN_THRESHOLD = 0.87     # Required similarity for frozen threads
THREAD_MATCH_MARGIN = 0.03         # Best must beat runner-up by this margin
BATCH_SIZE = 100

# Articles matching these patterns are excluded from threading (daily roundups pollute centroids)
THREADING_EXCLUDE_PATTERNS = ['Roundup: Market Talk']

import math

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

    # Get all items with description (title+description is enough to embed)
    all_items = []
    page_size = 1000
    offset = 0
    while True:
        items_response = supabase.table('wsj_items') \
            .select('id, title, description, published_at') \
            .not_.is_('description', 'null') \
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
    """Get articles with embeddings but no thread assignment.
    Includes keywords from LLM analysis for better thread grouping.
    """
    response = supabase.table('wsj_items') \
        .select('id, title, published_at, wsj_embeddings(embedding), wsj_crawl_results(wsj_llm_analysis(keywords))') \
        .not_.is_('description', 'null') \
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

            # Extract keywords from nested join
            keywords = []
            crawl = item.get('wsj_crawl_results')
            if crawl:
                cr = crawl[0] if isinstance(crawl, list) else crawl
                llm = cr.get('wsj_llm_analysis') if cr else None
                if llm:
                    ll = llm[0] if isinstance(llm, list) else llm
                    keywords = ll.get('keywords') or [] if ll else []

            results.append({
                'id': item['id'],
                'title': item['title'],
                'published_at': item['published_at'],
                'keywords': keywords,
                'embedding': np.array(raw_emb, dtype=np.float32),
            })

    return results


def is_roundup_article(title: str) -> bool:
    """Check if article is a daily roundup that should be excluded from threading."""
    return any(pattern in title for pattern in THREADING_EXCLUDE_PATTERNS)


def validate_llm_group(member_articles: list[dict], min_similarity: float = LLM_GROUP_MIN_SIMILARITY) -> tuple[bool, float]:
    """Check if LLM-proposed group members are actually similar via embeddings.

    Validates both average pairwise similarity and minimum pair floor.
    Returns (is_valid, avg_similarity).
    """
    if len(member_articles) < 2:
        return False, 0.0
    embeddings = np.array([a['embedding'] for a in member_articles])
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    normalized = embeddings / norms
    sim_matrix = normalized @ normalized.T
    n = len(embeddings)
    pairs = []
    for i in range(n):
        for j in range(i + 1, n):
            pairs.append(float(sim_matrix[i, j]))
    avg_sim = np.mean(pairs)
    min_pair = min(pairs)
    if avg_sim < min_similarity:
        return False, float(avg_sim)
    if min_pair < LLM_GROUP_MIN_PAIR_FLOOR:
        return False, float(avg_sim)
    return True, float(avg_sim)


def match_to_threads(
    articles: list[dict],
    threads: list[dict],
) -> tuple[dict[str, str], list[dict]]:
    """Match articles to threads with dynamic threshold (time + size penalty).

    Anti-gravity: larger threads require higher similarity to join.
    Roundup articles are excluded from matching entirely.

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
                centroid = json.loads(centroid)
            thread_centroids.append({
                'id': t['id'],
                'centroid': np.array(centroid, dtype=np.float32),
                'count': t['member_count'],
                'last_seen': t.get('last_seen', ''),
            })

    for article in articles:
        # Skip roundup articles — they pollute centroids
        if is_roundup_article(article.get('title', '')):
            unmatched.append(article)
            continue

        best_sim = 0.0
        second_best_sim = 0.0
        best_thread_id = None
        article_date = article.get('published_at', '')[:10]

        for tc in thread_centroids:
            sim = cosine_similarity(article['embedding'], tc['centroid'])

            # Time penalty
            days_gap = 0
            if article_date and tc['last_seen']:
                try:
                    a_date = datetime.strptime(article_date, '%Y-%m-%d')
                    t_date = datetime.strptime(tc['last_seen'], '%Y-%m-%d')
                    days_gap = abs((a_date - t_date).days)
                except ValueError:
                    pass

            # Dynamic threshold: base + time + size (anti-gravity)
            time_pen = THREAD_TIME_PENALTY * days_gap
            size_pen = THREAD_SIZE_PENALTY * math.log(tc['count'] + 1)
            effective_threshold = THREAD_BASE_THRESHOLD + time_pen + size_pen

            # Hard cap: frozen threads require very high similarity
            if tc['count'] >= THREAD_HARD_CAP:
                effective_threshold = max(effective_threshold, THREAD_FROZEN_THRESHOLD)

            if sim >= effective_threshold:
                if sim > best_sim:
                    second_best_sim = best_sim
                    best_sim = sim
                    best_thread_id = tc['id']
                elif sim > second_best_sim:
                    second_best_sim = sim

        # Margin check: best must clearly beat runner-up
        if best_thread_id and (best_sim - second_best_sim) >= THREAD_MATCH_MARGIN:
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

    # Filter out roundup articles before sending to LLM
    threadable = [a for a in articles if not is_roundup_article(a.get('title', ''))]
    if len(threadable) < 2:
        return []

    cap = min(len(threadable), 500)
    article_list = "\n".join(
        f"{i+1}. [{a['id'][:8]}] [{a.get('published_at', '')[:10]}] {a['title']}"
        + (f" [{', '.join(a.get('keywords', []))}]" if a.get('keywords') else "")
        for i, a in enumerate(threadable[:cap])
    )

    prompt = f"""Group these news articles into story threads. Each thread = articles about the SAME specific event or developing story.

Articles (format: index. [id] [date] title [keywords]):
{article_list}

Return ONLY valid JSON object with a "groups" key. Each group should have 2-8 articles.
Articles that don't fit any group should be omitted.

{{"groups": [
  {{"title": "Short descriptive thread headline", "indices": [1, 3, 7]}},
  ...
]}}

STRICT RULES:
- A thread must be about ONE specific event/story (e.g. "Toyota CEO Resignation" not "Automotive Industry")
- NEVER create generic/broad topic threads like "Economic Trends", "Market Reactions", "Company Performance", "Policy Changes"
- Thread titles must name specific entities, events, or actions (who did what)
- Only group articles that are clearly about the same developing story, not just the same broad topic
- 5-10 word titles, be specific: "Fed Holds Rates at 4.5%" not "Interest Rate Decisions"
- Maximum 8 articles per group. If more articles belong together, create separate sub-groups by specific angle
- Prefer grouping articles published within 3 days of each other
- It's better to leave articles ungrouped than to force them into a vague thread
- Only create groups with 2+ articles"""

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
            # Cap group size to prevent oversized initial threads
            indices = indices[:LLM_GROUP_MAX_SIZE]
            article_ids = []
            for idx in indices:
                if isinstance(idx, int) and 1 <= idx <= len(threadable):
                    article_ids.append(threadable[idx - 1]['id'])
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

        # Update thread centroids with EMA and member counts
        thread_updates = {}
        for article_id, thread_id in matched.items():
            article = next(a for a in articles if a['id'] == article_id)
            if thread_id not in thread_updates:
                thread_updates[thread_id] = {'count': 0, 'embeddings': [], 'dates': []}
            thread_updates[thread_id]['count'] += 1
            thread_updates[thread_id]['embeddings'].append(article['embedding'])
            thread_updates[thread_id]['dates'].append(article.get('published_at', '')[:10])

        for thread_id, update in thread_updates.items():
            thread = next((t for t in threads if t['id'] == thread_id), None)
            if not thread:
                continue

            # EMA centroid update: new_centroid = α*new + (1-α)*old
            old_centroid = None
            if thread.get('centroid'):
                c = thread['centroid']
                if isinstance(c, str):
                    c = json.loads(c)
                old_centroid = np.array(c, dtype=np.float32)

            if old_centroid is not None:
                new_centroid = old_centroid.copy()
                _ema_alpha = CENTROID_EMA_BASE_ALPHA / math.log(thread['member_count'] + 2)
                for emb in update['embeddings']:
                    new_centroid = _ema_alpha * emb + (1 - _ema_alpha) * new_centroid
                new_centroid = new_centroid / np.linalg.norm(new_centroid)
            else:
                new_centroid = np.mean(update['embeddings'], axis=0)
                new_centroid = new_centroid / np.linalg.norm(new_centroid)

            last_seen = max(update['dates']) if update['dates'] else datetime.now(timezone.utc).strftime('%Y-%m-%d')

            try:
                supabase.table('wsj_story_threads') \
                    .update({
                        'member_count': thread['member_count'] + update['count'],
                        'centroid': new_centroid.tolist(),
                        'last_seen': last_seen,
                        'updated_at': datetime.now(timezone.utc).isoformat(),
                    }) \
                    .eq('id', thread_id) \
                    .execute()
            except Exception as e:
                print(f"  ERROR updating thread {thread_id}: {e}")

    # Step 2: Group unmatched articles into new threads via LLM
    new_thread_count = 0
    merged_count = 0
    rejected_count = 0

    # For daily mode, limit LLM input to recent articles (last 2 days)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=2)).strftime('%Y-%m-%d')
    recent_unmatched = [a for a in unmatched if a.get('published_at', '')[:10] >= cutoff]

    if len(recent_unmatched) >= 2:
        print(f"  Grouping {len(recent_unmatched)} recent unmatched articles with LLM (cutoff: {cutoff})...")
        groups = group_unmatched_with_llm(recent_unmatched)
        print(f"  LLM created {len(groups)} new thread groups")

        # Refresh active threads for merge detection
        all_threads = get_active_threads(supabase) if not dry_run else threads

        if not dry_run:
            for group in groups:
                member_articles = [a for a in recent_unmatched if a['id'] in group['article_ids']]
                if not member_articles or len(member_articles) < 2:
                    continue

                # Cross-validate: reject if group members aren't actually similar
                is_valid, avg_sim = validate_llm_group(member_articles)
                if not is_valid:
                    print(f"    Rejected '{group['title']}' — avg similarity {avg_sim:.3f} < {LLM_GROUP_MIN_SIMILARITY}")
                    rejected_count += 1
                    continue

                embeddings = np.array([a['embedding'] for a in member_articles])
                centroid = np.mean(embeddings, axis=0)
                centroid = centroid / np.linalg.norm(centroid)

                dates = [a['published_at'][:10] for a in member_articles if a.get('published_at')]
                first_seen = min(dates) if dates else datetime.now(timezone.utc).strftime('%Y-%m-%d')
                last_seen = max(dates) if dates else datetime.now(timezone.utc).strftime('%Y-%m-%d')

                # Merge check: find best matching existing thread above threshold
                merge_target = None
                best_merge_sim = 0.0
                for t in all_threads:
                    t_centroid = t.get('centroid')
                    if not t_centroid:
                        continue
                    if isinstance(t_centroid, str):
                        t_centroid = json.loads(t_centroid)
                    sim = cosine_similarity(centroid, np.array(t_centroid, dtype=np.float32))
                    if sim >= THREAD_MERGE_THRESHOLD and sim > best_merge_sim:
                        best_merge_sim = sim
                        merge_target = t

                if merge_target:
                    # Merge into existing thread
                    merge_id = merge_target['id']
                    print(f"    Merging '{group['title']}' → existing '{merge_target['title']}'")
                    for aid in group['article_ids']:
                        supabase.table('wsj_items') \
                            .update({'thread_id': merge_id}) \
                            .eq('id', aid) \
                            .execute()

                    # EMA centroid update for merged thread
                    old_c = merge_target.get('centroid')
                    if isinstance(old_c, str):
                        old_c = json.loads(old_c)
                    old_c = np.array(old_c, dtype=np.float32)
                    _ema_alpha = CENTROID_EMA_BASE_ALPHA / math.log(merge_target['member_count'] + 2)
                    for emb in [a['embedding'] for a in member_articles]:
                        old_c = _ema_alpha * emb + (1 - _ema_alpha) * old_c
                    old_c = old_c / np.linalg.norm(old_c)

                    supabase.table('wsj_story_threads').update({
                        'member_count': merge_target['member_count'] + len(group['article_ids']),
                        'centroid': old_c.tolist(),
                        'last_seen': last_seen,
                        'updated_at': datetime.now(timezone.utc).isoformat(),
                    }).eq('id', merge_id).execute()

                    merged_count += 1
                    continue

                try:
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
                        for aid in group['article_ids']:
                            supabase.table('wsj_items') \
                                .update({'thread_id': new_thread_id}) \
                                .eq('id', aid) \
                                .execute()
                        new_thread_count += 1
                        # Add to all_threads for subsequent merge checks
                        all_threads.append({
                            'id': new_thread_id,
                            'title': group['title'],
                            'centroid': centroid.tolist(),
                            'member_count': len(group['article_ids']),
                            'last_seen': last_seen,
                        })

                except Exception as e:
                    print(f"  ERROR creating thread '{group['title']}': {e}")

    if merged_count:
        print(f"  Merged into existing: {merged_count}")
    if rejected_count:
        print(f"  Rejected by cross-validation: {rejected_count}")
    return {'matched': len(matched), 'new_threads': new_thread_count, 'merged': merged_count}


# ============================================================
# Step 3: Deactivate stale threads
# ============================================================

def deactivate_stale_threads(supabase: Client, days: int = THREAD_ARCHIVE_DAYS, dry_run: bool = False) -> int:
    """Mark threads with last_seen > N days ago as archived (inactive)."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime('%Y-%m-%d')

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
                .update({'active': False, 'updated_at': datetime.now(timezone.utc).isoformat()}) \
                .eq('id', t['id']) \
                .execute()
        except Exception as e:
            print(f"  ERROR deactivating {t['id']}: {e}")

    return len(stale)


# ============================================================
# Main
# ============================================================

def get_date_range_articles(supabase: Client, date_str: str) -> list[dict]:
    """Get unthreaded articles with embeddings for a specific date."""
    next_date = (datetime.strptime(date_str, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')

    response = supabase.table('wsj_items') \
        .select('id, title, published_at, wsj_embeddings(embedding), wsj_crawl_results(wsj_llm_analysis(keywords))') \
        .eq('processed', True) \
        .is_('thread_id', 'null') \
        .gte('published_at', date_str) \
        .lt('published_at', next_date) \
        .order('published_at', desc=False) \
        .limit(500) \
        .execute()

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
            if isinstance(raw_emb, str):
                raw_emb = json.loads(raw_emb)

            keywords = []
            crawl = item.get('wsj_crawl_results')
            if crawl:
                cr = crawl[0] if isinstance(crawl, list) else crawl
                llm = cr.get('wsj_llm_analysis') if cr else None
                if llm:
                    ll = llm[0] if isinstance(llm, list) else llm
                    keywords = ll.get('keywords') or [] if ll else []

            results.append({
                'id': item['id'],
                'title': item['title'],
                'published_at': item['published_at'],
                'keywords': keywords,
                'embedding': np.array(raw_emb, dtype=np.float32),
            })

    return results


def backfill_by_date(supabase: Client, dry_run: bool = False, limit_days: int | None = None, start_date: str | None = None):
    """Process articles chronologically, day by day, building threads incrementally."""

    if not start_date:
        # Get earliest unthreaded article date
        response = supabase.table('wsj_items') \
            .select('published_at') \
            .eq('processed', True) \
            .is_('thread_id', 'null') \
            .order('published_at', desc=False) \
            .limit(1) \
            .execute()

        if not response.data:
            print("No unthreaded articles.")
            return

        start_date = response.data[0]['published_at'][:10]

    response = supabase.table('wsj_items') \
        .select('published_at') \
        .eq('processed', True) \
        .is_('thread_id', 'null') \
        .order('published_at', desc=True) \
        .limit(1) \
        .execute()

    end_date = response.data[0]['published_at'][:10]

    print(f"Date range: {start_date} → {end_date}")

    current = datetime.strptime(start_date, '%Y-%m-%d')
    end = datetime.strptime(end_date, '%Y-%m-%d')
    day_count = 0

    while current <= end:
        date_str = current.strftime('%Y-%m-%d')
        articles = get_date_range_articles(supabase, date_str)

        if articles:
            print(f"\n--- {date_str}: {len(articles)} articles ---")

            threads = get_active_threads(supabase)
            print(f"  Active threads: {len(threads)}")

            # Match to existing
            matched, unmatched = match_to_threads(articles, threads)
            print(f"  Centroid matched: {len(matched)}")
            print(f"  Unmatched: {len(unmatched)}")

            if not dry_run:
                # Save matched
                for article_id, thread_id in matched.items():
                    try:
                        supabase.table('wsj_items') \
                            .update({'thread_id': thread_id}) \
                            .eq('id', article_id) \
                            .execute()
                    except Exception as e:
                        print(f"  ERROR: {e}")

                # EMA centroid updates for matched
                thread_updates = {}
                for article_id, thread_id in matched.items():
                    article = next(a for a in articles if a['id'] == article_id)
                    if thread_id not in thread_updates:
                        thread_updates[thread_id] = {'embeddings': [], 'dates': []}
                    thread_updates[thread_id]['embeddings'].append(article['embedding'])
                    thread_updates[thread_id]['dates'].append(article.get('published_at', '')[:10])

                for thread_id, update in thread_updates.items():
                    thread = next((t for t in threads if t['id'] == thread_id), None)
                    if not thread:
                        continue
                    old_c = thread.get('centroid')
                    if isinstance(old_c, str):
                        old_c = json.loads(old_c)
                    old_c = np.array(old_c, dtype=np.float32)
                    _ema_alpha = CENTROID_EMA_BASE_ALPHA / math.log(thread['member_count'] + 2)
                    for emb in update['embeddings']:
                        old_c = _ema_alpha * emb + (1 - _ema_alpha) * old_c
                    old_c = old_c / np.linalg.norm(old_c)
                    last_seen = max(update['dates'])
                    new_count = thread['member_count'] + len(update['embeddings'])
                    try:
                        supabase.table('wsj_story_threads').update({
                            'member_count': new_count,
                            'centroid': old_c.tolist(),
                            'last_seen': last_seen,
                            'updated_at': datetime.now(timezone.utc).isoformat(),
                        }).eq('id', thread_id).execute()
                        # Update in-memory count so subsequent days use correct size penalty
                        thread['member_count'] = new_count
                        thread['centroid'] = old_c.tolist()
                        thread['last_seen'] = last_seen
                    except Exception as e:
                        print(f"  ERROR updating thread: {e}")

            # LLM group unmatched
            if len(unmatched) >= 2:
                groups = group_unmatched_with_llm(unmatched)
                print(f"  LLM groups: {len(groups)}")

                if not dry_run:
                    all_threads = get_active_threads(supabase)
                    new_count = 0
                    merge_count = 0
                    reject_count = 0
                    for group in groups:
                        member_articles = [a for a in unmatched if a['id'] in group['article_ids']]
                        if not member_articles or len(member_articles) < 2:
                            continue

                        # Cross-validate: reject if group members aren't actually similar
                        is_valid, avg_sim = validate_llm_group(member_articles)
                        if not is_valid:
                            print(f"    Rejected '{group['title']}' — avg similarity {avg_sim:.3f} < {LLM_GROUP_MIN_SIMILARITY}")
                            reject_count += 1
                            continue

                        embs = np.array([a['embedding'] for a in member_articles])
                        centroid = np.mean(embs, axis=0)
                        centroid = centroid / np.linalg.norm(centroid)
                        dates = [a['published_at'][:10] for a in member_articles if a.get('published_at')]

                        # Merge check: find best matching existing thread
                        merge_target = None
                        best_merge_sim = 0.0
                        for t in all_threads:
                            t_c = t.get('centroid')
                            if not t_c:
                                continue
                            if isinstance(t_c, str):
                                t_c = json.loads(t_c)
                            sim = cosine_similarity(centroid, np.array(t_c, dtype=np.float32))
                            if sim >= THREAD_MERGE_THRESHOLD and sim > best_merge_sim:
                                best_merge_sim = sim
                                merge_target = t

                        if merge_target:
                            mid = merge_target['id']
                            print(f"    Merge: '{group['title']}' → '{merge_target['title']}'")
                            for aid in group['article_ids']:
                                supabase.table('wsj_items').update({'thread_id': mid}).eq('id', aid).execute()
                            old_c = merge_target.get('centroid')
                            if isinstance(old_c, str):
                                old_c = json.loads(old_c)
                            old_c = np.array(old_c, dtype=np.float32)
                            _ema_alpha = CENTROID_EMA_BASE_ALPHA / math.log(merge_target['member_count'] + 2)
                            for emb in [a['embedding'] for a in member_articles]:
                                old_c = _ema_alpha * emb + (1 - _ema_alpha) * old_c
                            old_c = old_c / np.linalg.norm(old_c)
                            supabase.table('wsj_story_threads').update({
                                'member_count': merge_target['member_count'] + len(group['article_ids']),
                                'centroid': old_c.tolist(),
                                'last_seen': max(dates) if dates else date_str,
                                'updated_at': datetime.now(timezone.utc).isoformat(),
                            }).eq('id', mid).execute()
                            merge_count += 1
                        else:
                            try:
                                resp = supabase.table('wsj_story_threads').insert({
                                    'title': group['title'],
                                    'centroid': centroid.tolist(),
                                    'member_count': len(group['article_ids']),
                                    'first_seen': min(dates) if dates else date_str,
                                    'last_seen': max(dates) if dates else date_str,
                                    'active': True,
                                }).execute()
                                if resp.data:
                                    tid = resp.data[0]['id']
                                    for aid in group['article_ids']:
                                        supabase.table('wsj_items').update({'thread_id': tid}).eq('id', aid).execute()
                                    new_count += 1
                                    all_threads.append({
                                        'id': tid, 'title': group['title'],
                                        'centroid': centroid.tolist(),
                                        'member_count': len(group['article_ids']),
                                        'last_seen': max(dates) if dates else date_str,
                                    })
                            except Exception as e:
                                print(f"    ERROR: {e}")

                    print(f"  New threads: {new_count}, Merged: {merge_count}, Rejected: {reject_count}")

        current += timedelta(days=1)
        if articles:
            day_count += 1
            if limit_days and day_count >= limit_days:
                print(f"\n  Stopped after {limit_days} active days (--limit-days)")
                break

    # Summary
    thread_count = supabase.table('wsj_story_threads').select('id', count='exact').eq('active', True).execute()
    threaded = supabase.table('wsj_items').select('id', count='exact').not_.is_('thread_id', 'null').execute()
    print(f"\nTotal active threads: {thread_count.count}")
    print(f"Total threaded articles: {threaded.count}")


def main():
    dry_run = '--dry-run' in sys.argv
    embed_only = '--embed-only' in sys.argv
    backfill = '--backfill-by-date' in sys.argv

    # Parse --limit-days N and --start-date YYYY-MM-DD
    limit_days = None
    start_date = None
    for i, arg in enumerate(sys.argv):
        if arg == '--limit-days' and i + 1 < len(sys.argv):
            limit_days = int(sys.argv[i + 1])
        if arg == '--start-date' and i + 1 < len(sys.argv):
            start_date = sys.argv[i + 1]

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

    if backfill:
        # Chronological backfill mode — skip deactivation (historical data)
        print("\n[2/3] Backfill by date (chronological)...")
        backfill_by_date(supabase, dry_run=dry_run, limit_days=limit_days, start_date=start_date)
        print("\n[3/3] Skipping deactivation (backfill mode)")
    else:
        # Normal daily mode
        print("\n[2/3] Assigning threads...")
        result = assign_threads(supabase, dry_run=dry_run)
        print(f"  Matched: {result['matched']}, New threads: {result['new_threads']}, Merged: {result.get('merged', 0)}")

        # Step 3: Deactivate stale
        print("\n[3/3] Deactivating stale threads...")
        deactivated = deactivate_stale_threads(supabase, dry_run=dry_run)
        print(f"  Deactivated: {deactivated}")

    print("\n" + "=" * 60)
    print("Done.")


if __name__ == "__main__":
    main()
