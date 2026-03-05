#!/usr/bin/env python3
"""
Phase 4.5 · Embed & Thread — Embed articles and assign to story threads.

Pipeline step: runs after crawl phase.
1. Embeds title+description+summary for articles missing embeddings (BAAI/bge-base-en-v1.5)
2. Matches each embedding to active/cooling thread centroids (time-weighted centroid + entity overlap)
3. Unmatched articles → LLM groups them + generates thread headlines
4. Updates centroids incrementally (running mean stored, time-weighted at match time)
5. Updates thread statuses: active (0-3d) / cooling (3-14d) / archived (14d+)
6. Post-hoc CE merge — cross-encoder scoring on centroid-prefiltered thread pairs

Usage:
    python scripts/7_embed_and_thread.py
    python scripts/7_embed_and_thread.py --embed-only    # Skip thread matching
    python scripts/7_embed_and_thread.py --dry-run       # No DB writes
    python scripts/7_embed_and_thread.py --seed-golden ../notebooks/golden_dataset_v2.1.json

"""
import argparse
import json
import math
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import numpy as np
from dotenv import load_dotenv
from sentence_transformers import CrossEncoder, SentenceTransformer
from supabase import create_client, Client

load_dotenv(Path(__file__).parent.parent / '.env.local')

# ============================================================
# Config
# ============================================================

EMBEDDING_MODEL = 'BAAI/bge-base-en-v1.5'
EMBEDDING_DIM = 768
THREAD_BASE_THRESHOLD = 0.60       # v2.1 grid search (was 0.73)
THREAD_TIME_PENALTY = 0.005        # v2.1 grid search (was 0.01)
THREAD_MERGE_THRESHOLD = 0.92      # Above this, new thread merges into existing
CENTROID_DECAY = 0.10              # Exponential decay per day for time-weighted centroid (Phase 4 grid search)
ENTITY_WEIGHT = 0.04               # Weight for IDF-weighted entity overlap score (Phase 4 grid search)
THREAD_COOLING_DAYS = 3             # Days of inactivity before cooling (P86 validated)
THREAD_ARCHIVE_DAYS = 14           # Days of inactivity before archiving
LLM_GROUP_MAX_SIZE = 8             # Max articles per LLM group
THREAD_HARD_CAP = 50               # Threads above this enter "frozen" mode
THREAD_FROZEN_THRESHOLD = 0.87     # Required similarity for frozen threads
THREAD_MATCH_MARGIN = 0.03         # Best must beat runner-up by this margin
AUTHOR_BOOST_THRESHOLD = 0.55      # v2.1 grid search (was 0.60)
AUTHOR_BOOST_WINDOW_HOURS = 48     # Time window for author boost (P75=2 days validated)
LLM_WINDOW_DAYS = 3                # Accumulate unmatched articles for N days before LLM grouping
BATCH_SIZE = 100

# CE merge pass (Phase 4.7 — post-hoc thread merge via cross-encoder)
CE_MODEL_NAME = 'Alibaba-NLP/gte-reranker-modernbert-base'
CE_CENTROID_PREFILTER = 0.60       # Centroid cosine threshold to generate CE candidates
CE_MERGE_THRESHOLD = 0.85          # CE score threshold to approve merge

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
        try:
            _model = SentenceTransformer(EMBEDDING_MODEL, local_files_only=True)
        except Exception:
            print("  Local cache miss, downloading from Hub...")
            _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model


_ce_model: Optional[CrossEncoder] = None


def get_ce_model() -> CrossEncoder:
    """Lazy-load GTE-ModernBERT cross-encoder for thread merge scoring."""
    global _ce_model
    if _ce_model is None:
        import torch
        device = 'mps' if torch.backends.mps.is_available() else 'cpu'
        print(f"Loading CE model: {CE_MODEL_NAME} (device={device})")
        _ce_model = CrossEncoder(CE_MODEL_NAME, device=device)
    return _ce_model


def embed_texts(texts: list[str]) -> np.ndarray:
    """Embed a list of texts. Returns (N, 768) array."""
    model = get_embedding_model()
    return model.encode(texts, normalize_embeddings=True, show_progress_bar=False)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two normalized vectors."""
    return float(np.dot(a, b))


# ============================================================
# Entity helpers (Phase 4.0.1)
# ============================================================

_TITLE_PREFIXES = {
    'president', 'secretary', 'ceo', 'cfo', 'coo', 'cto', 'dr', 'mr', 'ms',
    'mrs', 'sen', 'rep', 'gov', 'gen', 'col', 'lt', 'chairman', 'director',
}


def normalize_entities(entities: list[str]) -> list[str]:
    """Strip title prefixes and merge substring duplicates.

    e.g. ["President Trump", "Trump", "Donald Trump"] → ["Donald Trump"]
    """
    cleaned = []
    for e in (entities or []):
        if not e or not e.strip():
            continue
        words = e.strip().split()
        while words and words[0].rstrip('.').lower() in _TITLE_PREFIXES:
            words = words[1:]
        if words:
            cleaned.append(' '.join(words))

    # Substring merge: remove e if a longer form already contains it
    cleaned_lower = [c.lower() for c in cleaned]
    kept = []
    for i, e_lower in enumerate(cleaned_lower):
        dominated = any(
            e_lower != other and e_lower in other
            for other in cleaned_lower
        )
        if not dominated:
            kept.append(cleaned[i])

    # Deduplicate preserving first occurrence
    seen: set[str] = set()
    result = []
    for e in kept:
        key = e.lower()
        if key not in seen:
            seen.add(key)
            result.append(e)
    return result


def precompute_idf(all_member_data: dict[str, list[dict]]) -> dict[str, float]:
    """Compute smoothed IDF weights for entities across all thread members."""
    entity_doc_count: dict[str, int] = {}
    total_docs = 0

    for members in all_member_data.values():
        for m in members:
            unique_entities = set(
                e.lower() for e in normalize_entities(m.get('entities', []))
            )
            for e in unique_entities:
                entity_doc_count[e] = entity_doc_count.get(e, 0) + 1
            total_docs += 1

    if total_docs == 0:
        return {}

    return {
        e: math.log((total_docs + 1) / (count + 1)) + 1
        for e, count in entity_doc_count.items()
    }


def entity_overlap_score(
    article_entities: list[str],
    thread_entities: list[str],
    idf: dict[str, float] | None = None,
) -> float:
    """IDF-weighted Jaccard overlap between article and thread entity sets."""
    a_norm = set(e.lower() for e in normalize_entities(article_entities))
    t_norm = set(e.lower() for e in normalize_entities(thread_entities))

    if not a_norm or not t_norm:
        return 0.0

    intersection = a_norm & t_norm
    union = a_norm | t_norm

    if idf:
        inter_weight = sum(idf.get(e, 1.0) for e in intersection)
        union_weight = sum(idf.get(e, 1.0) for e in union)
    else:
        inter_weight = float(len(intersection))
        union_weight = float(len(union))

    return inter_weight / union_weight if union_weight > 0 else 0.0


def compute_time_weighted_centroid(
    members: list[dict],
    reference_date: str,
    decay: float,
) -> np.ndarray | None:
    """Compute exponentially time-decayed centroid from member embeddings.

    weight_i = exp(-decay * days_since_article_i)
    Replaces EMA centroid (insertion-order-based) with time-based weighting.
    """
    try:
        ref = datetime.strptime(reference_date[:10], '%Y-%m-%d')
    except ValueError:
        ref = datetime.now(timezone.utc).replace(tzinfo=None)

    embeddings = []
    weights = []
    for m in members:
        emb = m.get('embedding')
        if emb is None:
            continue
        try:
            days_old = max(0, (ref - datetime.strptime(m['published_at'][:10], '%Y-%m-%d')).days)
        except (ValueError, KeyError):
            days_old = 0
        embeddings.append(emb)
        weights.append(math.exp(-decay * days_old))

    if not embeddings:
        return None

    embs = np.array(embeddings, dtype=np.float32)
    w = np.array(weights, dtype=np.float32)
    centroid = np.average(embs, axis=0, weights=w)
    norm = np.linalg.norm(centroid)
    return centroid / norm if norm > 0 else centroid


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
    # Get IDs already embedded (paginated to avoid 1000-row limit)
    embedded_ids = set()
    emb_offset = 0
    while True:
        embedded_response = supabase.table('wsj_embeddings') \
            .select('wsj_item_id') \
            .range(emb_offset, emb_offset + 999) \
            .execute()
        batch = embedded_response.data or []
        embedded_ids.update(row['wsj_item_id'] for row in batch)
        if len(batch) < 1000:
            break
        emb_offset += 1000

    # Get all items with summary from LLM analysis (joined via crawl_results)
    all_items = []
    page_size = 1000
    offset = 0
    while True:
        items_response = supabase.table('wsj_items') \
            .select('id, title, description, published_at, wsj_crawl_results(relevance_flag, relevance_score, wsj_llm_analysis(summary))') \
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


def _pick_best_summary(article: dict) -> str | None:
    """Pick the best summary from 1:N crawl results per article.

    Priority: relevance_flag='ok' > highest relevance_score > longest summary.
    """
    crawl_results = article.get('wsj_crawl_results') or []
    if not isinstance(crawl_results, list):
        crawl_results = [crawl_results]

    candidates = []
    for cr in crawl_results:
        if not cr:
            continue
        analyses = cr.get('wsj_llm_analysis') or []
        if not isinstance(analyses, list):
            analyses = [analyses]
        flag = cr.get('relevance_flag')
        score = cr.get('relevance_score') or 0
        for analysis in analyses:
            if analysis and analysis.get('summary'):
                candidates.append({
                    'summary': analysis['summary'],
                    'flag': flag,
                    'score': score,
                    'length': len(analysis['summary']),
                })

    if not candidates:
        return None

    # Sort: relevance_flag='ok' first, then by score desc, then by length desc
    candidates.sort(key=lambda c: (
        c['flag'] == 'ok',
        c['score'],
        c['length'],
    ), reverse=True)
    return candidates[0]['summary']


def embed_articles(supabase: Client, dry_run: bool = False) -> int:
    """Embed all unembedded processed articles. Returns count."""
    articles = get_unembedded_articles(supabase)
    if not articles:
        print("No articles to embed.")
        return 0

    print(f"Embedding {len(articles)} articles...")

    # Prepare texts: title + description + best summary (from LLM analysis)
    texts = []
    for a in articles:
        parts = [a['title']]
        if a.get('description'):
            parts.append(a['description'])
        summary = _pick_best_summary(a)
        if summary:
            parts.append(summary)
        texts.append(' '.join(parts))

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
    """Get active and cooling threads with their centroids."""
    response = supabase.table('wsj_story_threads') \
        .select('id, title, centroid, member_count, first_seen, last_seen, status') \
        .in_('status', ['active', 'cooling']) \
        .execute()
    return response.data or []


def get_unthreaded_articles(supabase: Client) -> list[dict]:
    """Get articles with embeddings but no thread assignment.
    Includes keywords from LLM analysis for better thread grouping.
    """
    response = supabase.table('wsj_items') \
        .select('id, title, published_at, creator, wsj_embeddings(embedding), wsj_crawl_results(wsj_llm_analysis(keywords, summary, key_entities, people_mentioned, tickers_mentioned))') \
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

            # Extract keywords, summary, and entities from nested join
            keywords = []
            summary = None
            entities: list[str] = []
            crawl = item.get('wsj_crawl_results')
            if crawl:
                for cr in (crawl if isinstance(crawl, list) else [crawl]):
                    if not cr:
                        continue
                    analyses = cr.get('wsj_llm_analysis') or []
                    if not isinstance(analyses, list):
                        analyses = [analyses]
                    for ll in analyses:
                        if not ll:
                            continue
                        if not keywords and ll.get('keywords'):
                            keywords = ll['keywords']
                        if not summary and ll.get('summary'):
                            summary = ll['summary']
                        if ll.get('key_entities'):
                            entities.extend(ll['key_entities'])
                        if ll.get('people_mentioned'):
                            entities.extend(ll['people_mentioned'])
                        if ll.get('tickers_mentioned'):
                            entities.extend(ll['tickers_mentioned'])
                        break  # first analysis per crawl result is sufficient

            # Include keywords in entity set for overlap scoring
            entities.extend(keywords)

            results.append({
                'id': item['id'],
                'title': item['title'],
                'published_at': item['published_at'],
                'creator': item.get('creator'),
                'keywords': keywords,
                'summary': summary,
                'entities': entities,
                'embedding': np.array(raw_emb, dtype=np.float32),
            })

    return results




def match_to_threads(
    articles: list[dict],
    threads: list[dict],
    thread_member_data: dict[str, list[dict]] | None = None,
    entity_idf: dict[str, float] | None = None,
) -> tuple[dict[str, str], list[dict]]:
    """Match articles to threads using time-weighted centroid + entity overlap.

    Threshold: base + time_penalty (size penalty removed — handled by time-weighted centroid).
    Author boost: same creator within AUTHOR_BOOST_WINDOW_HOURS → lower threshold.
    Entity boost: IDF-weighted entity Jaccard added to cosine similarity.

    Args:
        thread_member_data: {thread_id: [{creator, published_at, embedding, entities}]}
            Used for time-weighted centroid, author boost, and entity overlap.
            If None, falls back to stored centroid; author boost and entity overlap disabled.
        entity_idf: Pre-computed IDF weights for entities. If None, unweighted Jaccard used.

    Returns:
        (matched: {article_id: thread_id}, unmatched: [articles])
    """
    matched = {}
    unmatched = []

    # Parse thread centroids (stored centroid = fallback when no member data)
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
        best_sim = 0.0
        second_best_sim = 0.0
        best_thread_id = None
        article_date = article.get('published_at', '')[:10]
        article_creator = article.get('creator')
        article_entities = article.get('entities', [])

        for tc in thread_centroids:
            members = (thread_member_data or {}).get(tc['id'])

            # Time-weighted centroid: recompute from members when available
            if members:
                twc = compute_time_weighted_centroid(members, article_date, CENTROID_DECAY)
                effective_centroid = twc if twc is not None else tc['centroid']
            else:
                effective_centroid = tc['centroid']

            sim = cosine_similarity(article['embedding'], effective_centroid)

            # Entity overlap boost
            if ENTITY_WEIGHT > 0 and members and article_entities:
                thread_entities: list[str] = []
                for m in members:
                    thread_entities.extend(m.get('entities', []))
                if thread_entities:
                    overlap = entity_overlap_score(article_entities, thread_entities, entity_idf)
                    sim = sim + ENTITY_WEIGHT * overlap

            # Time penalty
            days_gap = 0
            if article_date and tc['last_seen']:
                try:
                    a_date = datetime.strptime(article_date, '%Y-%m-%d')
                    t_date = datetime.strptime(tc['last_seen'], '%Y-%m-%d')
                    days_gap = abs((a_date - t_date).days)
                except ValueError:
                    pass

            # Dynamic threshold: base + time (no size penalty)
            time_pen = THREAD_TIME_PENALTY * days_gap
            effective_threshold = THREAD_BASE_THRESHOLD + time_pen

            # Hard cap: frozen threads require very high similarity
            if tc['count'] >= THREAD_HARD_CAP:
                effective_threshold = max(effective_threshold, THREAD_FROZEN_THRESHOLD)

            # Author boost: same creator in thread within window → lower threshold
            if article_creator and members:
                for member in members:
                    if member.get('creator') != article_creator:
                        continue
                    try:
                        # Use full datetime for precise hour-level comparison
                        m_dt = datetime.strptime(member['published_at'][:19], '%Y-%m-%dT%H:%M:%S')
                        a_dt_full = datetime.strptime(article.get('published_at', '')[:19], '%Y-%m-%dT%H:%M:%S')
                        hours_gap = abs((a_dt_full - m_dt).total_seconds()) / 3600
                        if hours_gap <= AUTHOR_BOOST_WINDOW_HOURS:
                            effective_threshold = min(effective_threshold, AUTHOR_BOOST_THRESHOLD)
                            break
                    except ValueError:
                        pass

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

    if len(articles) < 2:
        return []

    cap = min(len(articles), 500)

    def _truncate_summary(text: str | None, max_sentences: int = 2) -> str:
        """Return first N sentences, max 120 chars."""
        if not text:
            return ""
        sentences = text.split('. ')
        truncated = '. '.join(sentences[:max_sentences])
        if len(truncated) > 120:
            truncated = truncated[:117] + '...'
        return truncated

    lines = []
    for i, a in enumerate(articles[:cap]):
        creator = a.get('creator') or 'Unknown'
        line = f"{i+1}. [{a['id'][:8]}] [{a.get('published_at', '')[:10]}] ({creator}) {a['title']}"
        if a.get('keywords'):
            line += f" [{', '.join(a['keywords'])}]"
        brief = _truncate_summary(a.get('summary'))
        if brief:
            line += f"\n   > {brief}"
        lines.append(line)
    article_list = "\n".join(lines)

    prompt = f"""Group these news articles into story threads. Each thread = articles about the SAME specific event or developing story.

Articles (format: index. [id] [date] (author) title [keywords] + summary):
{article_list}

Return ONLY valid JSON object with a "groups" key. Each group should have 2-8 articles.
Articles that don't fit any group should be omitted.

{{"groups": [
  {{"title": "Short descriptive thread headline", "summary": "2-3 sentence story progression summary, chronological, emphasize recent developments", "indices": [1, 3, 7]}},
  ...
]}}

STRICT RULES:
- A thread must be about ONE specific event/story (e.g. "Toyota CEO Resignation" not "Automotive Industry")
- NEVER create generic/broad topic threads like "Economic Trends", "Market Reactions", "Company Performance", "Policy Changes"
- Thread titles must name specific entities, events, or actions (who did what)
- Only group articles that are clearly about the same developing story, not just the same broad topic
- Use author as a HINT: same author writing about the same topic across days likely belongs together
- 5-10 word titles, be specific: "Fed Holds Rates at 4.5%" not "Interest Rate Decisions"
- Summary must describe how the story progressed chronologically, with emphasis on the most recent development
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
                if isinstance(idx, int) and 1 <= idx <= len(articles):
                    article_ids.append(articles[idx - 1]['id'])
            if len(article_ids) >= 2:
                output.append({
                    'title': group.get('title', 'Untitled Thread'),
                    'summary': group.get('summary'),
                    'article_ids': article_ids,
                })

        return output

    except Exception as e:
        print(f"  LLM grouping error: {e}")
        return []


def _fetch_thread_member_data(supabase: Client, thread_ids: list[str]) -> dict[str, list[dict]]:
    """Fetch member data per thread: embedding, published_at, creator, entities.

    Used for:
    - Time-weighted centroid recomputation at match time
    - Author boost (creator + published_at)
    - Entity overlap scoring
    """
    if not thread_ids:
        return {}

    members: dict[str, list[dict]] = {}

    for i in range(0, len(thread_ids), 50):
        batch_ids = thread_ids[i:i + 50]
        response = supabase.table('wsj_items') \
            .select('thread_id, creator, published_at, wsj_embeddings(embedding), wsj_crawl_results(wsj_llm_analysis(key_entities, people_mentioned, keywords, tickers_mentioned))') \
            .in_('thread_id', batch_ids) \
            .execute()

        for row in (response.data or []):
            tid = row['thread_id']
            if tid not in members:
                members[tid] = []

            # Parse embedding
            emb: np.ndarray | None = None
            emb_data = row.get('wsj_embeddings')
            if isinstance(emb_data, list) and emb_data:
                emb_data = emb_data[0]
            if isinstance(emb_data, dict) and emb_data.get('embedding'):
                raw = emb_data['embedding']
                if isinstance(raw, str):
                    raw = json.loads(raw)
                emb = np.array(raw, dtype=np.float32)

            # Parse entities
            entities: list[str] = []
            crawl = row.get('wsj_crawl_results')
            for cr in (crawl if isinstance(crawl, list) else [crawl] if crawl else []):
                if not cr:
                    continue
                analyses = cr.get('wsj_llm_analysis') or []
                if not isinstance(analyses, list):
                    analyses = [analyses]
                for ll in analyses:
                    if not ll:
                        continue
                    if ll.get('key_entities'):
                        entities.extend(ll['key_entities'])
                    if ll.get('people_mentioned'):
                        entities.extend(ll['people_mentioned'])
                    if ll.get('keywords'):
                        entities.extend(ll['keywords'])
                    if ll.get('tickers_mentioned'):
                        entities.extend(ll['tickers_mentioned'])
                    break

            members[tid].append({
                'creator': row.get('creator'),
                'published_at': row['published_at'],
                'embedding': emb,
                'entities': entities,
            })

    return members


def assign_threads(supabase: Client, dry_run: bool = False) -> dict:
    """Match unthreaded articles to existing or new threads."""
    articles = get_unthreaded_articles(supabase)
    if not articles:
        print("No unthreaded articles.")
        return {'matched': 0, 'new_threads': 0}

    print(f"Processing {len(articles)} unthreaded articles...")

    threads = get_active_threads(supabase)
    print(f"Active threads: {len(threads)}")

    # Fetch thread member data (embeddings + entities + creator for time-weighted centroid / entity overlap / author boost)
    thread_member_data = _fetch_thread_member_data(supabase, [t['id'] for t in threads])
    entity_idf = precompute_idf(thread_member_data)

    # Step 1: Match to existing threads
    matched, unmatched = match_to_threads(articles, threads, thread_member_data=thread_member_data, entity_idf=entity_idf)
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

        # Update thread centroids (running mean) and member counts
        thread_updates: dict[str, dict] = {}
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

            # Running mean centroid update (EMA removed; time-weighted computed at match time)
            old_c = thread.get('centroid')
            if old_c:
                if isinstance(old_c, str):
                    old_c = json.loads(old_c)
                old_c = np.array(old_c, dtype=np.float32)
                n = thread['member_count']
                new_embs = np.array(update['embeddings'], dtype=np.float32)
                new_centroid = (old_c * n + new_embs.sum(axis=0)) / (n + len(update['embeddings']))
            else:
                new_centroid = np.mean(update['embeddings'], axis=0)
            norm = np.linalg.norm(new_centroid)
            new_centroid = new_centroid / norm if norm > 0 else new_centroid

            last_seen = max(update['dates']) if update['dates'] else datetime.now(timezone.utc).strftime('%Y-%m-%d')

            try:
                supabase.table('wsj_story_threads') \
                    .update({
                        'member_count': thread['member_count'] + update['count'],
                        'centroid': new_centroid.tolist(),
                        'last_seen': last_seen,
                        'status': 'active',  # resurrection: cooling/archived → active
                        'updated_at': datetime.now(timezone.utc).isoformat(),
                    }) \
                    .eq('id', thread_id) \
                    .execute()
            except Exception as e:
                print(f"  ERROR updating thread {thread_id}: {e}")

    # Step 2: Group unmatched articles into new threads via LLM
    new_thread_count = 0
    merged_count = 0

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

                    # Running mean centroid update for merged thread
                    old_c = merge_target.get('centroid')
                    if isinstance(old_c, str):
                        old_c = json.loads(old_c)
                    old_c = np.array(old_c, dtype=np.float32)
                    n = merge_target['member_count']
                    new_embs = np.array([a['embedding'] for a in member_articles], dtype=np.float32)
                    merged_c = (old_c * n + new_embs.sum(axis=0)) / (n + len(member_articles))
                    norm = np.linalg.norm(merged_c)
                    merged_c = merged_c / norm if norm > 0 else merged_c

                    supabase.table('wsj_story_threads').update({
                        'member_count': merge_target['member_count'] + len(group['article_ids']),
                        'centroid': merged_c.tolist(),
                        'last_seen': last_seen,
                        'status': 'active',  # resurrection on merge
                        'updated_at': datetime.now(timezone.utc).isoformat(),
                    }).eq('id', merge_id).execute()

                    merged_count += 1
                    continue

                try:
                    insert_data = {
                        'title': group['title'],
                        'centroid': centroid.tolist(),
                        'member_count': len(group['article_ids']),
                        'first_seen': first_seen,
                        'last_seen': last_seen,
                        'status': 'active',
                    }
                    if group.get('summary'):
                        insert_data['summary'] = group['summary']
                    thread_response = supabase.table('wsj_story_threads').insert(insert_data).execute()

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
    return {'matched': len(matched), 'new_threads': new_thread_count, 'merged': merged_count}


# ============================================================
# Step 3: Deactivate stale threads
# ============================================================

def update_thread_statuses(supabase: Client, dry_run: bool = False) -> dict:
    """Update thread statuses: active (0-3d) / cooling (3-14d) / archived (14d+)."""
    now = datetime.now(timezone.utc)
    cooling_cutoff = (now - timedelta(days=THREAD_COOLING_DAYS)).strftime('%Y-%m-%d')
    archive_cutoff = (now - timedelta(days=THREAD_ARCHIVE_DAYS)).strftime('%Y-%m-%d')

    response = supabase.table('wsj_story_threads') \
        .select('id, title, last_seen, status') \
        .in_('status', ['active', 'cooling']) \
        .execute()

    threads = response.data or []
    if not threads:
        return {'cooling': 0, 'archived': 0}

    counts = {'cooling': 0, 'archived': 0}

    for t in threads:
        last_seen = t['last_seen']
        if last_seen < archive_cutoff:
            new_status = 'archived'
        elif last_seen < cooling_cutoff:
            new_status = 'cooling'
        else:
            continue  # still active, no change needed

        if new_status == t['status']:
            continue

        counts[new_status] = counts.get(new_status, 0) + 1

        if dry_run:
            print(f"  [DRY] {t['title']} → {new_status} (last: {last_seen})")
            continue

        try:
            supabase.table('wsj_story_threads') \
                .update({'status': new_status, 'updated_at': now.isoformat()}) \
                .eq('id', t['id']) \
                .execute()
        except Exception as e:
            print(f"  ERROR updating {t['id']}: {e}")

    return counts


# ============================================================
# Main
# ============================================================

def get_date_range_articles(supabase: Client, date_str: str) -> list[dict]:
    """Get unthreaded articles with embeddings for a specific date."""
    next_date = (datetime.strptime(date_str, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')

    response = supabase.table('wsj_items') \
        .select('id, title, published_at, creator, wsj_embeddings(embedding), wsj_crawl_results(wsj_llm_analysis(keywords, summary, key_entities, people_mentioned, tickers_mentioned))') \
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
            summary = None
            entities: list[str] = []
            crawl = item.get('wsj_crawl_results')
            if crawl:
                for cr in (crawl if isinstance(crawl, list) else [crawl]):
                    if not cr:
                        continue
                    analyses = cr.get('wsj_llm_analysis') or []
                    if not isinstance(analyses, list):
                        analyses = [analyses]
                    for ll in analyses:
                        if not ll:
                            continue
                        if not keywords and ll.get('keywords'):
                            keywords = ll['keywords']
                        if not summary and ll.get('summary'):
                            summary = ll['summary']
                        if ll.get('key_entities'):
                            entities.extend(ll['key_entities'])
                        if ll.get('people_mentioned'):
                            entities.extend(ll['people_mentioned'])
                        if ll.get('tickers_mentioned'):
                            entities.extend(ll['tickers_mentioned'])
                        break

            entities.extend(keywords)

            results.append({
                'id': item['id'],
                'title': item['title'],
                'published_at': item['published_at'],
                'creator': item.get('creator'),
                'keywords': keywords,
                'summary': summary,
                'entities': entities,
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
    window_day = 0
    # Accumulate unmatched within current window only (no cross-window carryover)
    window_unmatched: list[dict] = []

    while current <= end:
        date_str = current.strftime('%Y-%m-%d')
        articles = get_date_range_articles(supabase, date_str)

        if articles:
            print(f"\n--- {date_str}: {len(articles)} articles ---")

            threads = get_active_threads(supabase)
            print(f"  Active threads: {len(threads)}")

            # Fetch thread member data (time-weighted centroid / entity overlap / author boost)
            thread_member_data = _fetch_thread_member_data(supabase, [t['id'] for t in threads])
            entity_idf = precompute_idf(thread_member_data)

            # Match to existing
            matched, unmatched = match_to_threads(articles, threads, thread_member_data=thread_member_data, entity_idf=entity_idf)
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

                # Running mean centroid updates for matched
                thread_updates: dict[str, dict] = {}
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
                    n = thread['member_count']
                    new_embs = np.array(update['embeddings'], dtype=np.float32)
                    new_c = (old_c * n + new_embs.sum(axis=0)) / (n + len(update['embeddings']))
                    norm = np.linalg.norm(new_c)
                    new_c = new_c / norm if norm > 0 else new_c
                    last_seen = max(update['dates'])
                    new_member_count = thread['member_count'] + len(update['embeddings'])
                    try:
                        supabase.table('wsj_story_threads').update({
                            'member_count': new_member_count,
                            'centroid': new_c.tolist(),
                            'last_seen': last_seen,
                            'updated_at': datetime.now(timezone.utc).isoformat(),
                        }).eq('id', thread_id).execute()
                        thread['member_count'] = new_member_count
                        thread['centroid'] = new_c.tolist()
                        thread['last_seen'] = last_seen
                    except Exception as e:
                        print(f"  ERROR updating thread: {e}")

            # Accumulate unmatched for this window
            window_unmatched.extend(unmatched)
            window_day += 1
            day_count += 1

        # LLM grouping every LLM_WINDOW_DAYS or on last day
        is_window_end = window_day >= LLM_WINDOW_DAYS or current >= end
        if is_window_end and len(window_unmatched) >= 2 and not dry_run:
            # Re-try centroid match (threads may have been created earlier in this window)
            threads = get_active_threads(supabase)
            win_member_data = _fetch_thread_member_data(supabase, [t['id'] for t in threads])
            win_idf = precompute_idf(win_member_data)
            late_matched, still_unmatched = match_to_threads(window_unmatched, threads, thread_member_data=win_member_data, entity_idf=win_idf)

            if late_matched:
                print(f"  Window re-match: {len(late_matched)} articles matched to threads")
                for article_id, thread_id in late_matched.items():
                    supabase.table('wsj_items').update({'thread_id': thread_id}).eq('id', article_id).execute()

                # Batch centroid updates per thread (correct running mean with multiple matches)
                late_updates: dict[str, dict] = {}
                for article_id, thread_id in late_matched.items():
                    article = next((a for a in window_unmatched if a['id'] == article_id), None)
                    if not article:
                        continue
                    if thread_id not in late_updates:
                        late_updates[thread_id] = {'embeddings': [], 'dates': []}
                    late_updates[thread_id]['embeddings'].append(article['embedding'])
                    late_updates[thread_id]['dates'].append(article.get('published_at', '')[:10])

                for thread_id, update in late_updates.items():
                    thread = next((t for t in threads if t['id'] == thread_id), None)
                    if not thread:
                        continue
                    old_c = thread.get('centroid')
                    if isinstance(old_c, str):
                        old_c = json.loads(old_c)
                    old_c = np.array(old_c, dtype=np.float32)
                    n = thread['member_count']
                    new_embs = np.array(update['embeddings'], dtype=np.float32)
                    new_c = (old_c * n + new_embs.sum(axis=0)) / (n + len(update['embeddings']))
                    norm = np.linalg.norm(new_c)
                    new_c = new_c / norm if norm > 0 else new_c
                    new_count = thread['member_count'] + len(update['embeddings'])
                    last_seen = max(thread.get('last_seen', ''), max(update['dates']))
                    supabase.table('wsj_story_threads').update({
                        'member_count': new_count,
                        'centroid': new_c.tolist(),
                        'last_seen': last_seen,
                        'updated_at': datetime.now(timezone.utc).isoformat(),
                    }).eq('id', thread_id).execute()
                    # Update in-memory for subsequent operations
                    thread['member_count'] = new_count
                    thread['centroid'] = new_c.tolist()
                    thread['last_seen'] = last_seen

            if len(still_unmatched) >= 2:
                print(f"  Window LLM grouping: {len(still_unmatched)} articles")
                groups = group_unmatched_with_llm(still_unmatched)
                print(f"  LLM groups: {len(groups)}")

                all_threads = get_active_threads(supabase)
                new_count = 0
                merge_count = 0
                for group in groups:
                    member_articles = [a for a in still_unmatched if a['id'] in group['article_ids']]
                    if not member_articles or len(member_articles) < 2:
                        continue

                    embs = np.array([a['embedding'] for a in member_articles])
                    centroid = np.mean(embs, axis=0)
                    centroid = centroid / np.linalg.norm(centroid)
                    dates = [a['published_at'][:10] for a in member_articles if a.get('published_at')]

                    # Merge check
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
                        n = merge_target['member_count']
                        new_embs = np.array([a['embedding'] for a in member_articles], dtype=np.float32)
                        merged_c = (old_c * n + new_embs.sum(axis=0)) / (n + len(member_articles))
                        norm = np.linalg.norm(merged_c)
                        merged_c = merged_c / norm if norm > 0 else merged_c
                        supabase.table('wsj_story_threads').update({
                            'member_count': merge_target['member_count'] + len(group['article_ids']),
                            'centroid': merged_c.tolist(),
                            'last_seen': max(dates) if dates else date_str,
                            'status': 'active',
                            'updated_at': datetime.now(timezone.utc).isoformat(),
                        }).eq('id', mid).execute()
                        merge_count += 1
                    else:
                        try:
                            insert_data = {
                                'title': group['title'],
                                'centroid': centroid.tolist(),
                                'member_count': len(group['article_ids']),
                                'first_seen': min(dates) if dates else date_str,
                                'last_seen': max(dates) if dates else date_str,
                                'status': 'active',
                            }
                            if group.get('summary'):
                                insert_data['summary'] = group['summary']
                            resp = supabase.table('wsj_story_threads').insert(insert_data).execute()
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

                print(f"  New threads: {new_count}, Merged: {merge_count}")

            # Reset window — no carryover
            window_unmatched = []
            window_day = 0
        elif is_window_end:
            window_unmatched = []
            window_day = 0

        current += timedelta(days=1)
        if limit_days and day_count >= limit_days:
            print(f"\n  Stopped after {limit_days} active days (--limit-days)")
            break

    # Summary
    thread_count = supabase.table('wsj_story_threads').select('id', count='exact').in_('status', ['active', 'cooling']).execute()
    threaded = supabase.table('wsj_items').select('id', count='exact').not_.is_('thread_id', 'null').execute()
    print(f"\nTotal active threads: {thread_count.count}")
    print(f"Total threaded articles: {threaded.count}")


def merge_similar_threads_ce(supabase: Client, dry_run: bool = False) -> dict:
    """Post-hoc merge of similar threads using cross-encoder scoring.

    1. Get all active/cooling multi-article threads with centroids
    2. Find thread pairs with centroid cosine >= CE_CENTROID_PREFILTER
    3. Build representative text for each thread (title + 3 recent article titles)
    4. Score candidate pairs with GTE-ModernBERT cross-encoder
    5. Merge pairs above CE_MERGE_THRESHOLD (highest CE score first, skip absorbed)
    """
    threads = get_active_threads(supabase)
    multi_threads = [t for t in threads if t.get('member_count', 0) >= 2 and t.get('centroid')]
    print(f"  Multi-article threads: {len(multi_threads)}")

    if len(multi_threads) < 2:
        return {'merged': 0, 'candidates': 0}

    # Parse centroids
    for t in multi_threads:
        c = t['centroid']
        if isinstance(c, str):
            c = json.loads(c)
        t['_centroid'] = np.array(c, dtype=np.float32)

    # Build representative text: thread title + up to 3 recent member article titles
    thread_texts = {}
    for t in multi_threads:
        members = supabase.table('wsj_items') \
            .select('title') \
            .eq('thread_id', t['id']) \
            .order('published_at', desc=True) \
            .limit(3) \
            .execute()
        article_titles = [m['title'] for m in (members.data or []) if m.get('title')]
        rep_text = t['title'] + '. ' + '. '.join(article_titles)
        thread_texts[t['id']] = rep_text

    # Find candidate merge pairs: centroid cosine >= threshold
    candidates = []
    for i in range(len(multi_threads)):
        for j in range(i + 1, len(multi_threads)):
            t1, t2 = multi_threads[i], multi_threads[j]
            cos = float(np.dot(t1['_centroid'], t2['_centroid']))
            if cos >= CE_CENTROID_PREFILTER:
                candidates.append((t1['id'], t2['id'], cos))

    print(f"  Centroid candidate pairs (>= {CE_CENTROID_PREFILTER}): {len(candidates)}")
    if not candidates:
        return {'merged': 0, 'candidates': 0}

    # Score with CE model
    ce_model = get_ce_model()
    pairs_text = [(thread_texts[t1], thread_texts[t2]) for t1, t2, _ in candidates]
    ce_scores = ce_model.predict(pairs_text, batch_size=32)

    # Build scored pairs, sort by CE score descending
    scored = []
    for idx, (t1, t2, cos) in enumerate(candidates):
        ce_score = float(ce_scores[idx])
        if ce_score >= CE_MERGE_THRESHOLD:
            scored.append((t1, t2, cos, ce_score))
    scored.sort(key=lambda x: -x[3])

    print(f"  Merge-worthy pairs (CE >= {CE_MERGE_THRESHOLD}): {len(scored)}")

    # Merge: highest CE first, skip already-absorbed threads
    thread_lookup = {t['id']: t for t in multi_threads}
    absorbed = set()
    merged_count = 0

    for t1_id, t2_id, cos, ce_score in scored:
        if t1_id in absorbed or t2_id in absorbed:
            continue

        # Keep the larger thread, absorb the smaller
        t1, t2 = thread_lookup[t1_id], thread_lookup[t2_id]
        if t1['member_count'] >= t2['member_count']:
            keeper, donor = t1, t2
        else:
            keeper, donor = t2, t1

        print(f"    Merge: '{donor['title'][:50]}' → '{keeper['title'][:50]}' "
              f"(CE={ce_score:.3f}, cos={cos:.3f})")

        if not dry_run:
            # Move articles from donor to keeper
            supabase.table('wsj_items') \
                .update({'thread_id': keeper['id']}) \
                .eq('thread_id', donor['id']) \
                .execute()

            # Update keeper centroid (running mean)
            old_c = keeper['_centroid']
            donor_c = donor['_centroid']
            n_keep = keeper['member_count']
            n_donor = donor['member_count']
            new_c = (old_c * n_keep + donor_c * n_donor) / (n_keep + n_donor)
            norm = np.linalg.norm(new_c)
            new_c = new_c / norm if norm > 0 else new_c

            new_last = max(keeper.get('last_seen', ''), donor.get('last_seen', ''))
            new_first = min(keeper.get('first_seen', ''), donor.get('first_seen', ''))

            supabase.table('wsj_story_threads').update({
                'member_count': n_keep + n_donor,
                'centroid': new_c.tolist(),
                'first_seen': new_first,
                'last_seen': new_last,
                'updated_at': datetime.now(timezone.utc).isoformat(),
            }).eq('id', keeper['id']).execute()

            # Delete donor thread
            supabase.table('wsj_story_threads') \
                .delete() \
                .eq('id', donor['id']) \
                .execute()

        absorbed.add(donor['id'])
        merged_count += 1

    return {'merged': merged_count, 'candidates': len(candidates)}


def seed_from_golden(supabase: Client, golden_path: str, dry_run: bool = False) -> None:
    """Seed wsj_story_threads from a golden dataset JSON file.

    Resets all existing thread assignments, then creates threads from golden data
    with proper centroids computed from member article embeddings.
    """
    with open(golden_path) as f:
        golden = json.load(f)

    threads = golden['threads']
    version = golden.get('version', '?')
    print(f"  Golden dataset v{version}: {len(threads)} threads")

    # Collect all article IDs from golden threads
    all_article_ids = []
    for t in threads:
        all_article_ids.extend(t['articles'])
    print(f"  Total articles in golden threads: {len(all_article_ids)}")

    if dry_run:
        print("  [DRY RUN] Would reset all thread_id assignments and delete all wsj_story_threads")
        print(f"  [DRY RUN] Would create {len(threads)} threads")
        # Show a few sample threads
        for t in threads[:5]:
            print(f"    - '{t['title']}' ({len(t['articles'])} articles)")
        if len(threads) > 5:
            print(f"    ... and {len(threads) - 5} more")
        return

    # Step 1: Reset all existing thread assignments
    print("  Resetting thread assignments...")
    # Clear thread_id from all articles — loop until none remain (avoids pagination issues)
    cleared = 0
    while True:
        batch = supabase.table('wsj_items') \
            .select('id') \
            .not_.is_('thread_id', 'null') \
            .limit(500) \
            .execute()
        if not batch.data:
            break
        for r in batch.data:
            supabase.table('wsj_items').update({'thread_id': None}).eq('id', r['id']).execute()
        cleared += len(batch.data)
    if cleared:
        print(f"    Cleared {cleared} article thread assignments")

    # Delete all existing threads (safe now — no FK references remain)
    deleted = 0
    while True:
        batch = supabase.table('wsj_story_threads').select('id').limit(200).execute()
        if not batch.data:
            break
        for r in batch.data:
            supabase.table('wsj_story_threads').delete().eq('id', r['id']).execute()
        deleted += len(batch.data)
    if deleted:
        print(f"    Deleted {deleted} existing threads")

    # Step 2: Create golden threads
    print("  Creating golden threads...")
    created = 0
    skipped = 0

    for t in threads:
        article_ids = t['articles']

        # Fetch embeddings for member articles
        embeddings = []
        published_dates = []
        for aid in article_ids:
            emb_resp = supabase.table('wsj_embeddings') \
                .select('embedding') \
                .eq('wsj_item_id', aid) \
                .limit(1) \
                .execute()
            if emb_resp.data:
                emb = emb_resp.data[0]['embedding']
                if isinstance(emb, str):
                    emb = json.loads(emb)
                embeddings.append(np.array(emb, dtype=np.float32))

            date_resp = supabase.table('wsj_items') \
                .select('published_at') \
                .eq('id', aid) \
                .limit(1) \
                .execute()
            if date_resp.data and date_resp.data[0].get('published_at'):
                published_dates.append(date_resp.data[0]['published_at'][:10])

        if not embeddings:
            print(f"    SKIP: '{t['title'][:50]}' — no embeddings found")
            skipped += 1
            continue

        # Compute centroid
        centroid = np.mean(np.array(embeddings), axis=0)
        norm = np.linalg.norm(centroid)
        centroid = centroid / norm if norm > 0 else centroid

        first_seen = min(published_dates) if published_dates else '2026-01-01'
        last_seen = max(published_dates) if published_dates else '2026-01-01'

        # Insert thread
        insert_data = {
            'title': t['title'],
            'centroid': centroid.tolist(),
            'member_count': len(article_ids),
            'first_seen': first_seen,
            'last_seen': last_seen,
            'status': 'active',
        }
        resp = supabase.table('wsj_story_threads').insert(insert_data).execute()

        if resp.data:
            tid = resp.data[0]['id']
            for aid in article_ids:
                supabase.table('wsj_items').update({'thread_id': tid}).eq('id', aid).execute()
            created += 1
        else:
            print(f"    ERROR inserting thread: '{t['title'][:50]}'")

    print(f"\n  Summary: {created} threads created, {skipped} skipped")

    # Verify
    thread_count = supabase.table('wsj_story_threads').select('id', count='exact').execute()
    threaded_count = supabase.table('wsj_items').select('id', count='exact').not_.is_('thread_id', 'null').execute()
    print(f"  DB state: {thread_count.count} threads, {threaded_count.count} threaded articles")


def main():
    parser = argparse.ArgumentParser(description='Embed articles and assign to story threads')
    parser.add_argument('--dry-run', action='store_true', help='No DB writes')
    parser.add_argument('--embed-only', action='store_true', help='Skip thread matching')
    parser.add_argument('--backfill-by-date', action='store_true', help='Chronological backfill mode')
    parser.add_argument('--limit-days', type=int, default=None, help='Max days to process in backfill')
    parser.add_argument('--start-date', type=str, default=None, help='Start date for backfill (YYYY-MM-DD)')
    parser.add_argument('--skip-merge', action='store_true', help='Skip post-hoc CE thread merge pass')
    parser.add_argument('--seed-golden', type=str, default=None,
                        help='Seed threads from golden dataset JSON, then exit')
    args = parser.parse_args()

    print("=" * 60)
    print("Embed & Thread Pipeline")
    print("=" * 60)

    supabase = get_supabase_client()

    # Golden seed mode — reset + create threads from golden dataset, then exit
    if args.seed_golden:
        print(f"\n[SEED] Seeding from golden dataset: {args.seed_golden}")
        t0 = time.time()
        seed_from_golden(supabase, args.seed_golden, dry_run=args.dry_run)
        print(f"  [TIMING] seed: {time.time() - t0:.1f}s")
        print("\n" + "=" * 60)
        print("Done (seed only).")
        return

    # Step 1: Embed
    print("\n[1/4] Embedding articles...")
    t0 = time.time()
    embedded = embed_articles(supabase, dry_run=args.dry_run)
    print(f"  Embedded: {embedded}")
    print(f"  [TIMING] embed: {time.time() - t0:.1f}s")

    if args.embed_only:
        print("\n--embed-only flag set, skipping thread matching.")
        return

    if args.backfill_by_date:
        # Chronological backfill mode — skip deactivation (historical data)
        print("\n[2/4] Backfill by date (chronological)...")
        t0 = time.time()
        backfill_by_date(supabase, dry_run=args.dry_run, limit_days=args.limit_days, start_date=args.start_date)
        print(f"  [TIMING] backfill: {time.time() - t0:.1f}s")
        print("\n[3/4] Skipping deactivation (backfill mode)")
    else:
        # Normal daily mode
        print("\n[2/4] Assigning threads...")
        t0 = time.time()
        result = assign_threads(supabase, dry_run=args.dry_run)
        print(f"  Matched: {result['matched']}, New threads: {result['new_threads']}, Merged: {result.get('merged', 0)}")
        print(f"  [TIMING] assign: {time.time() - t0:.1f}s")

        # Step 3: Update thread statuses
        print("\n[3/4] Updating thread statuses...")
        t0 = time.time()
        status_counts = update_thread_statuses(supabase, dry_run=args.dry_run)
        print(f"  Cooling: {status_counts['cooling']}, Archived: {status_counts['archived']}")
        print(f"  [TIMING] status_update: {time.time() - t0:.1f}s")

    # Step 4: CE merge pass
    if args.skip_merge:
        print("\n[4/4] Skipping CE merge (--skip-merge)")
    else:
        print("\n[4/4] CE thread merge...")
        t0 = time.time()
        merge_result = merge_similar_threads_ce(supabase, dry_run=args.dry_run)
        print(f"  Merged: {merge_result['merged']} threads ({merge_result['candidates']} candidates)")
        print(f"  [TIMING] ce_merge: {time.time() - t0:.1f}s")

    print("\n" + "=" * 60)
    print("Done.")


if __name__ == "__main__":
    main()
