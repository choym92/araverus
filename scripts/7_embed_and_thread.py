#!/usr/bin/env python3
"""
Phase 4.5 · Embed & Thread — Embed articles and assign to story threads.

Pipeline step: runs after crawl phase.
1. Embeds title+description+summary for articles missing embeddings (BAAI/bge-base-en-v1.5)
2. Assigns each embedding to active/cooling threads via LLM Judge (cosine pre-filter → Gemini)
3. Unmatched articles → LLM groups them + generates thread headlines
4. Updates centroids incrementally (running mean stored)
5. Updates thread statuses: active (0-3d) / cooling (3-14d) / archived (14d+)
6. Analyzes threads with new articles (impacts, narrative, drivers)
7. Groups threads into parent macro-events

Usage:
    python scripts/7_embed_and_thread.py
    python scripts/7_embed_and_thread.py --embed-only    # Skip thread matching
    python scripts/7_embed_and_thread.py --dry-run       # No DB writes
    python scripts/7_embed_and_thread.py --legacy        # Use old heuristic matching
    python scripts/7_embed_and_thread.py --skip-analysis # Skip thread analysis (step B)
    python scripts/7_embed_and_thread.py --skip-parents  # Skip parent grouping (step C)
    python scripts/7_embed_and_thread.py --days 7          # Process last 7 days (catch-up)
    python scripts/7_embed_and_thread.py --days 0          # Process all unthreaded (no date limit)
    python scripts/7_embed_and_thread.py --rejudge         # Re-evaluate already-judged articles
    python scripts/7_embed_and_thread.py --seed-golden ../notebooks/golden_dataset_v2.1.json

"""
import argparse
import json
import os
import time
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
BATCH_SIZE = 100

# LLM Judge (Step A)
CANDIDATE_THRESHOLD = 0.40         # Loose cosine pre-filter for LLM Judge candidates
CANDIDATE_TOP_K = 5                # Max candidate threads per article
JUDGE_MODEL = 'gemini-2.5-flash'
JUDGE_PROMPT_VERSION = 'v1'

# Thread lifecycle
THREAD_MERGE_THRESHOLD = 0.92     # Above this, new thread merges into existing
THREAD_COOLING_DAYS = 3           # Days of inactivity before cooling
THREAD_ARCHIVE_DAYS = 14          # Days of inactivity before archiving
LLM_GROUP_MAX_SIZE = 8            # Max articles per LLM group

# Thread analysis (Step B)
ANALYSIS_MODEL = 'gemini-2.5-flash'
ANALYSIS_MIN_NEW_ARTICLES = 3     # Min new articles since last analysis to trigger re-analysis

# Parent grouping (Step C)
PARENT_MODEL = 'gemini-2.5-flash'

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


def embed_texts(texts: list[str]) -> np.ndarray:
    """Embed a list of texts. Returns (N, 768) array."""
    model = get_embedding_model()
    return model.encode(texts, normalize_embeddings=True, show_progress_bar=False)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two normalized vectors."""
    return float(np.dot(a, b))


# ============================================================
# Gemini client (shared)
# ============================================================

def _call_gemini_json(prompt: str, model: str) -> Optional[dict]:
    """Call Gemini and parse JSON response. Returns dict or None."""
    import re
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("GEMINI_API_KEY not set")
        return None

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)

    try:
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0,
                response_mime_type="application/json",
            ),
        )
        result = json.loads(response.text)
        usage = response.usage_metadata
        result["_input_tokens"] = usage.prompt_token_count if usage else None
        result["_output_tokens"] = usage.candidates_token_count if usage else None
        return result

    except json.JSONDecodeError:
        match = re.search(r'\{[\s\S]*\}', response.text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        print(f"LLM JSON parse error for model={model}")
        return None
    except Exception as e:
        print(f"LLM error ({model}): {e}")
        return None


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
    """Pick the best summary from 1:N crawl results per article."""
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

    texts = []
    for a in articles:
        parts = [a['title']]
        if a.get('description'):
            parts.append(a['description'])
        summary = _pick_best_summary(a)
        if summary:
            parts.append(summary)
        texts.append(' '.join(parts))

    total_saved = 0
    for i in range(0, len(articles), BATCH_SIZE):
        batch_articles = articles[i:i + BATCH_SIZE]
        batch_texts = texts[i:i + BATCH_SIZE]

        embeddings = embed_texts(batch_texts)

        if dry_run:
            total_saved += len(batch_articles)
            print(f"  [DRY] Batch {i // BATCH_SIZE + 1}: {len(batch_articles)} embeddings")
            continue

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
# Step 2: Thread matching — LLM Judge
# ============================================================

def get_active_threads(supabase: Client) -> list[dict]:
    """Get active and cooling threads with their centroids."""
    response = supabase.table('wsj_story_threads') \
        .select('id, title, centroid, member_count, first_seen, last_seen, status') \
        .in_('status', ['active', 'cooling']) \
        .execute()
    return response.data or []


def get_unthreaded_articles(supabase: Client, days: int = 3, skip_judged: bool = True) -> list[dict]:
    """Get articles with embeddings but no thread assignment.

    Args:
        days: Only consider articles published within this many days (default 3).
              Use 0 or negative for no date filter.
        skip_judged: Skip articles that already have a judgment record (default True).
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat() if days > 0 else None

    query = supabase.table('wsj_items') \
        .select('id, title, published_at, creator, description, wsj_embeddings(embedding), wsj_crawl_results(wsj_llm_analysis(keywords, summary, key_entities, sentiment))') \
        .is_('thread_id', 'null') \
        .order('published_at', desc=True) \
        .limit(500)

    if cutoff:
        query = query.gte('published_at', cutoff)

    response = query.execute()

    results = []
    for item in (response.data or []):
        emb = item.get('wsj_embeddings')
        if isinstance(emb, list) and emb:
            emb_data = emb[0]
        elif isinstance(emb, dict):
            emb_data = emb
        else:
            continue

        if not (emb_data and emb_data.get('embedding')):
            continue

        raw_emb = emb_data['embedding']
        if isinstance(raw_emb, str):
            raw_emb = json.loads(raw_emb)

        # Extract LLM analysis data
        keywords = []
        summary = None
        entities: list[str] = []
        sentiment = None
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
                    if not sentiment and ll.get('sentiment'):
                        sentiment = ll['sentiment']
                    break

        results.append({
            'id': item['id'],
            'title': item['title'],
            'published_at': item['published_at'],
            'creator': item.get('creator'),
            'description': item.get('description'),
            'keywords': keywords,
            'summary': summary,
            'entities': entities,
            'sentiment': sentiment,
            'embedding': np.array(raw_emb, dtype=np.float32),
        })

    # Filter out articles that already have a judgment record
    if skip_judged and results:
        article_ids = [r['id'] for r in results]
        # Batch query in chunks of 100 to avoid URL length limits
        judged_ids: set[str] = set()
        for i in range(0, len(article_ids), 100):
            chunk = article_ids[i:i + 100]
            resp = supabase.table('wsj_thread_judgments') \
                .select('article_id') \
                .in_('article_id', chunk) \
                .execute()
            judged_ids.update(j['article_id'] for j in (resp.data or []))
        if judged_ids:
            before = len(results)
            results = [r for r in results if r['id'] not in judged_ids]
            print(f"  Skipped {before - len(results)} already-judged articles ({len(results)} remaining)")

    return results


def get_candidate_threads(
    article: dict,
    threads: list[dict],
) -> list[dict]:
    """Cosine pre-filter: return top-K threads above CANDIDATE_THRESHOLD."""
    scored = []
    for t in threads:
        centroid = t.get('centroid')
        if not centroid:
            continue
        if isinstance(centroid, str):
            centroid = json.loads(centroid)
        sim = cosine_similarity(article['embedding'], np.array(centroid, dtype=np.float32))
        if sim >= CANDIDATE_THRESHOLD:
            scored.append({**t, '_cosine': sim})

    scored.sort(key=lambda x: -x['_cosine'])
    return scored[:CANDIDATE_TOP_K]


def _fetch_thread_recent_titles(supabase: Client, thread_ids: list[str]) -> dict[str, list[dict]]:
    """Fetch 3 most recent article titles per thread for Judge context."""
    if not thread_ids:
        return {}

    result: dict[str, list[dict]] = {}
    for i in range(0, len(thread_ids), 50):
        batch_ids = thread_ids[i:i + 50]
        response = supabase.table('wsj_items') \
            .select('thread_id, title, published_at') \
            .in_('thread_id', batch_ids) \
            .order('published_at', desc=True) \
            .execute()

        for row in (response.data or []):
            tid = row['thread_id']
            if tid not in result:
                result[tid] = []
            if len(result[tid]) < 3:
                result[tid].append({
                    'title': row['title'],
                    'published_at': row['published_at'][:10],
                })

    return result


# ============================================================
# LLM Judge prompt
# ============================================================

JUDGE_PROMPT = """You are a news story thread analyst. Decide whether this article belongs to one of the candidate threads, or should start a new thread.

## Article
- Title: {article_title}
- Date: {article_date}
- Author: {article_author}
- Summary: {article_summary}
- Keywords: {article_keywords}

## Candidate Threads
{candidate_list}

## Instructions
- "direct": The article reports on the SAME specific event/story as the thread.
- "causal": The article is about a DIFFERENT event that is caused by or directly impacts the thread's story (e.g., "Fed Rate Cut" causing "Housing Market Shift"). In this case, also specify the related_thread_id.
- "none": The article does not belong to any candidate. A new thread should be created.

IMPORTANT:
- Do NOT assign to a thread just because the topic is broadly similar. The article must be about the SAME developing story.
- "causal" is for clear cause-effect chains, not vague thematic similarity.
- When in doubt, choose "none" — it's better to create a new thread than contaminate an existing one.

Return ONLY valid JSON:
{{
  "action": "assign" or "new_thread",
  "thread_id": "<chosen thread ID or null>",
  "reason": "<1-2 sentence explanation>",
  "confidence": "high" or "medium" or "low",
  "match_type": "direct" or "causal" or "none",
  "related_thread_id": "<thread ID if causal, else null>"
}}"""


def _format_candidate_list(candidates: list[dict], recent_titles: dict[str, list[dict]]) -> str:
    """Format candidate threads for the Judge prompt."""
    lines = []
    for i, c in enumerate(candidates, 1):
        titles = recent_titles.get(c['id'], [])
        title_str = '; '.join(t['title'] for t in titles) if titles else '(no recent articles)'
        lines.append(
            f"{i}. [ID: {c['id']}] \"{c['title']}\" "
            f"(members: {c['member_count']}, cosine: {c['_cosine']:.3f})\n"
            f"   Recent articles: {title_str}"
        )
    return '\n'.join(lines) if lines else "(no candidates — create new thread)"


def match_article_with_llm_judge(
    article: dict,
    candidates: list[dict],
    recent_titles: dict[str, list[dict]],
    supabase: Client,
    dry_run: bool = False,
) -> Optional[str]:
    """Call LLM Judge to decide thread assignment.

    Returns thread_id if assigned, None if new_thread/no_match.
    Saves judgment to wsj_thread_judgments table.
    """
    prompt = JUDGE_PROMPT.format(
        article_title=article['title'],
        article_date=article.get('published_at', '')[:10],
        article_author=article.get('creator') or 'Unknown',
        article_summary=article.get('summary') or article.get('description') or '(no summary)',
        article_keywords=', '.join(article.get('keywords', [])) or '(none)',
        candidate_list=_format_candidate_list(candidates, recent_titles),
    )

    result = _call_gemini_json(prompt, JUDGE_MODEL)
    if not result:
        return None

    action = result.get('action', 'new_thread')
    chosen_id = result.get('thread_id')
    reason = result.get('reason', '')
    confidence = result.get('confidence', 'low')
    match_type = result.get('match_type', 'none')
    related_id = result.get('related_thread_id')

    # Validate chosen_id is actually a candidate
    candidate_ids = {c['id'] for c in candidates}
    if action == 'assign' and chosen_id not in candidate_ids:
        print(f"    Judge returned invalid thread_id {chosen_id}, treating as new_thread")
        action = 'new_thread'
        chosen_id = None

    # Map action to decision enum
    if action == 'assign':
        decision = 'assign'
    elif not candidates:
        decision = 'no_match'
    else:
        decision = 'new_thread'

    # Save judgment record
    if not dry_run:
        judgment_record = {
            'article_id': article['id'],
            'candidate_threads_json': [
                {'id': c['id'], 'title': c['title'], 'cosine': round(c['_cosine'], 4)}
                for c in candidates
            ],
            'decision': decision,
            'chosen_thread_id': chosen_id if decision == 'assign' else None,
            'decision_reason': reason[:500],
            'confidence': confidence if confidence in ('high', 'medium', 'low') else 'low',
            'match_type': match_type if match_type in ('direct', 'causal', 'none') else 'none',
            'related_thread_id': related_id if match_type == 'causal' and related_id in candidate_ids else None,
            'judge_model': JUDGE_MODEL,
            'prompt_version': JUDGE_PROMPT_VERSION,
        }
        try:
            supabase.table('wsj_thread_judgments').insert(judgment_record).execute()
        except Exception as e:
            print(f"    ERROR saving judgment: {e}")

    if decision == 'assign':
        conf_label = f"[{confidence}]" if confidence != 'high' else ''
        print(f"    → Assign to '{next((c['title'] for c in candidates if c['id'] == chosen_id), '?')[:40]}' {conf_label}")
        return chosen_id

    print(f"    → {decision}: {reason[:60]}")
    return None


def _update_thread_centroid(supabase: Client, thread: dict, new_embeddings: list[np.ndarray], last_seen: str):
    """Update thread centroid with running mean and metadata."""
    old_c = thread.get('centroid')
    if old_c:
        if isinstance(old_c, str):
            old_c = json.loads(old_c)
        old_c = np.array(old_c, dtype=np.float32)
        n = thread['member_count']
        new_embs = np.array(new_embeddings, dtype=np.float32)
        new_centroid = (old_c * n + new_embs.sum(axis=0)) / (n + len(new_embeddings))
    else:
        new_centroid = np.mean(new_embeddings, axis=0)
    norm = np.linalg.norm(new_centroid)
    new_centroid = new_centroid / norm if norm > 0 else new_centroid

    supabase.table('wsj_story_threads').update({
        'member_count': thread['member_count'] + len(new_embeddings),
        'centroid': new_centroid.tolist(),
        'last_seen': last_seen,
        'status': 'active',  # resurrection: cooling/archived → active
        'updated_at': datetime.now(timezone.utc).isoformat(),
    }).eq('id', thread['id']).execute()


def assign_threads(supabase: Client, dry_run: bool = False, legacy: bool = False,
                    days: int = 3, skip_judged: bool = True) -> dict:
    """Match unthreaded articles to existing or new threads."""
    articles = get_unthreaded_articles(supabase, days=days, skip_judged=skip_judged)
    if not articles:
        print("No unthreaded articles.")
        return {'matched': 0, 'new_threads': 0, 'merged': 0}

    print(f"Processing {len(articles)} unthreaded articles...")

    threads = get_active_threads(supabase)
    print(f"Active threads: {len(threads)}")

    if legacy:
        return _assign_threads_legacy(articles, threads, supabase, dry_run)

    # --- LLM Judge path ---
    # Pre-fetch recent titles for all threads (batch)
    thread_ids = [t['id'] for t in threads]
    recent_titles = _fetch_thread_recent_titles(supabase, thread_ids) if thread_ids else {}

    matched: dict[str, str] = {}  # article_id → thread_id
    unmatched: list[dict] = []

    for article in articles:
        candidates = get_candidate_threads(article, threads)

        if not candidates:
            # No cosine candidates at all → goes to LLM grouping
            unmatched.append(article)
            print(f"  [{article['title'][:50]}] → no candidates (below {CANDIDATE_THRESHOLD})")
            continue

        print(f"  [{article['title'][:50]}] → {len(candidates)} candidates")
        chosen_id = match_article_with_llm_judge(
            article, candidates, recent_titles, supabase, dry_run=dry_run,
        )

        if chosen_id:
            matched[article['id']] = chosen_id
        else:
            unmatched.append(article)

    print(f"  LLM Judge matched: {len(matched)}")
    print(f"  Unmatched: {len(unmatched)}")

    # Save matched assignments + update centroids
    if not dry_run:
        thread_updates: dict[str, dict] = {}
        for article_id, thread_id in matched.items():
            article = next(a for a in articles if a['id'] == article_id)
            try:
                supabase.table('wsj_items') \
                    .update({'thread_id': thread_id}) \
                    .eq('id', article_id) \
                    .execute()
            except Exception as e:
                print(f"  ERROR assigning {article_id}: {e}")

            if thread_id not in thread_updates:
                thread_updates[thread_id] = {'embeddings': [], 'dates': []}
            thread_updates[thread_id]['embeddings'].append(article['embedding'])
            thread_updates[thread_id]['dates'].append(article.get('published_at', '')[:10])

        for thread_id, update in thread_updates.items():
            thread = next((t for t in threads if t['id'] == thread_id), None)
            if not thread:
                continue
            try:
                _update_thread_centroid(
                    supabase, thread, update['embeddings'],
                    max(update['dates']) if update['dates'] else datetime.now(timezone.utc).strftime('%Y-%m-%d'),
                )
            except Exception as e:
                print(f"  ERROR updating thread {thread_id}: {e}")

    # Group unmatched articles into new threads via LLM
    new_thread_count = 0
    merged_count = 0

    group_cutoff = (datetime.now(timezone.utc) - timedelta(days=min(days, 3))).strftime('%Y-%m-%d')
    recent_unmatched = [a for a in unmatched if a.get('published_at', '')[:10] >= group_cutoff]

    if len(recent_unmatched) >= 2:
        print(f"  Grouping {len(recent_unmatched)} recent unmatched articles with LLM (cutoff: {group_cutoff})...")
        groups = group_unmatched_with_llm(recent_unmatched)
        print(f"  LLM created {len(groups)} new thread groups")

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

                # Merge check
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
                    merge_id = merge_target['id']
                    print(f"    Merging '{group['title']}' → existing '{merge_target['title']}'")
                    for aid in group['article_ids']:
                        supabase.table('wsj_items') \
                            .update({'thread_id': merge_id}) \
                            .eq('id', aid) \
                            .execute()
                    _update_thread_centroid(
                        supabase, merge_target,
                        [a['embedding'] for a in member_articles],
                        last_seen,
                    )
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


def _assign_threads_legacy(
    articles: list[dict],
    threads: list[dict],
    supabase: Client,
    dry_run: bool,
) -> dict:
    """Legacy heuristic matching (--legacy flag). Simple cosine threshold."""
    base_threshold = 0.60
    matched: dict[str, str] = {}
    unmatched: list[dict] = []

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
        best_thread_id = None

        for tc in thread_centroids:
            sim = cosine_similarity(article['embedding'], tc['centroid'])
            if sim >= base_threshold and sim > best_sim:
                best_sim = sim
                best_thread_id = tc['id']

        if best_thread_id:
            matched[article['id']] = best_thread_id
        else:
            unmatched.append(article)

    print(f"  Legacy matched: {len(matched)}")
    print(f"  Unmatched: {len(unmatched)}")

    if not dry_run:
        for article_id, thread_id in matched.items():
            try:
                supabase.table('wsj_items') \
                    .update({'thread_id': thread_id}) \
                    .eq('id', article_id) \
                    .execute()
            except Exception as e:
                print(f"  ERROR assigning {article_id}: {e}")

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
            try:
                _update_thread_centroid(
                    supabase, thread, update['embeddings'],
                    max(update['dates']) if update['dates'] else datetime.now(timezone.utc).strftime('%Y-%m-%d'),
                )
            except Exception as e:
                print(f"  ERROR updating thread {thread_id}: {e}")

    return {'matched': len(matched), 'new_threads': 0, 'merged': 0}


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

    cap = min(len(articles), 500)

    def _truncate_summary(text: str | None, max_sentences: int = 2) -> str:
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
  {{"title": "Max 8-word headline", "summary": "2-3 sentence story progression summary, chronological, emphasize recent developments", "indices": [1, 3, 7]}},
  ...
]}}

STRICT RULES:
- A thread must be about ONE specific event/story (e.g. "Toyota CEO Resignation" not "Automotive Industry")
- NEVER create generic/broad topic threads like "Economic Trends", "Market Reactions", "Company Performance", "Policy Changes"
- Thread titles must name specific entities, events, or actions (who did what)
- Only group articles that are clearly about the same developing story, not just the same broad topic
- Use author as a HINT: same author writing about the same topic across days likely belongs together
- TITLES: Maximum 8 words. Front-load key entities (company, person, number). No subordinate clauses (no "amid", "as", "posing", "signaling"). Active voice, present tense. Example: "Apple Launches $599 MacBook Neo" NOT "Apple Launches $599 MacBook Neo, Broadening Market Access and Ecosystem Entry"
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

        output = []
        for group in groups:
            indices = group.get('indices', [])
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
            continue

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
# Step 4: Thread Analysis (Step B)
# ============================================================

THREAD_ANALYSIS_PROMPT = """You are a senior financial analyst. Analyze this story thread and produce a structured analysis.

## Thread: "{thread_title}"

## Articles (most recent first):
{article_list}

Return ONLY valid JSON:
{{
  "updated_title": "<improved thread title if the story has evolved, max 8 words, or same as current>",
  "summary": "<3-5 sentence narrative: what happened, how it evolved, what's the latest>",
  "catalyst": "<the triggering event that started this story>",
  "drivers": ["<key factor 1>", "<key factor 2>", "<key factor 3>"],
  "impacts": [
    {{
      "name": "<asset/sector/commodity name>",
      "type": "stock" or "sector" or "commodity" or "currency" or "index",
      "confidence": "direct" or "indirect",
      "direction": "positive" or "negative" or "mixed",
      "reason": "<1 sentence why>",
      "rank": 1
    }}
  ],
  "narrative_strength": <1-10 integer, how coherent/developing is this story>,
  "narrative_velocity": "accelerating" or "stable" or "decelerating",
  "dominant_theme": "<geopolitical_conflict|trade_war|monetary_policy|earnings|regulation|tech_disruption|energy|healthcare|real_estate|labor|legal|other>",
  "dominant_sector": "<energy|technology|finance|healthcare|defense|consumer|industrial|materials|utilities|real_estate|other>",
  "dominant_macro": "<geopolitics|interest_rates|inflation|trade|employment|fiscal_policy|supply_chain|climate|demographics|other>"
}}

Rules:
- impacts: max 5, ranked by directness. Include stocks, sectors, commodities, currencies affected.
- narrative_strength: 1=random collection, 5=clear theme, 8=strong developing story, 10=dominant market narrative
- updated_title: only change if the story has meaningfully shifted (e.g., "peace talks" → "ceasefire deal"). Max 8 words, active voice."""


def analyze_threads(supabase: Client, dry_run: bool = False) -> int:
    """Analyze threads that have enough new articles since last analysis.

    Returns count of threads analyzed.
    """
    response = supabase.table('wsj_story_threads') \
        .select('id, title, member_count, analysis_article_count, analysis_json') \
        .in_('status', ['active', 'cooling']) \
        .execute()

    threads = response.data or []
    analyzed = 0

    for t in threads:
        current_count = t['member_count']
        last_analyzed_count = t.get('analysis_article_count') or 0

        # Skip if not enough new articles since last analysis
        if current_count - last_analyzed_count < ANALYSIS_MIN_NEW_ARTICLES:
            continue

        # Fetch recent articles with LLM analysis data
        articles_resp = supabase.table('wsj_items') \
            .select('title, published_at, wsj_crawl_results(wsj_llm_analysis(summary, sentiment, key_entities, geographic_region))') \
            .eq('thread_id', t['id']) \
            .order('published_at', desc=True) \
            .limit(10) \
            .execute()

        article_data = articles_resp.data or []
        if len(article_data) < 2:
            continue

        # Format article list for prompt
        lines = []
        for i, a in enumerate(article_data, 1):
            summary = None
            sentiment = None
            entities = []
            region = None
            crawl = a.get('wsj_crawl_results')
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
                        if not summary and ll.get('summary'):
                            summary = ll['summary']
                        if not sentiment and ll.get('sentiment'):
                            sentiment = ll['sentiment']
                        if ll.get('key_entities'):
                            entities = ll['key_entities']
                        if not region and ll.get('geographic_region'):
                            region = ll['geographic_region']
                        break

            line = f"{i}. [{a.get('published_at', '')[:10]}] {a['title']}"
            if sentiment:
                line += f" (sentiment: {sentiment})"
            if entities:
                line += f" [entities: {', '.join(entities[:5])}]"
            if region:
                line += f" [region: {region}]"
            if summary:
                # Truncate to ~100 chars
                s = summary[:100] + '...' if len(summary) > 100 else summary
                line += f"\n   > {s}"
            lines.append(line)

        article_list = '\n'.join(lines)

        prompt = THREAD_ANALYSIS_PROMPT.format(
            thread_title=t['title'],
            article_list=article_list,
        )

        print(f"  Analyzing: '{t['title'][:50]}' ({current_count} articles, {current_count - last_analyzed_count} new)")

        result = _call_gemini_json(prompt, ANALYSIS_MODEL)
        if not result:
            continue

        # Clean metadata keys before storing
        analysis_json = {k: v for k, v in result.items() if not k.startswith('_')}

        if dry_run:
            print(f"    [DRY] Would save analysis: narrative_strength={result.get('narrative_strength')}")
            analyzed += 1
            continue

        # Update thread
        update_data: dict = {
            'analysis_json': analysis_json,
            'analysis_updated_at': datetime.now(timezone.utc).isoformat(),
            'analysis_article_count': current_count,
            'updated_at': datetime.now(timezone.utc).isoformat(),
        }

        # Update title if changed
        updated_title = result.get('updated_title')
        if updated_title and updated_title != t['title']:
            update_data['title'] = updated_title
            update_data['title_updated_at'] = datetime.now(timezone.utc).isoformat()
            print(f"    Title updated: '{t['title'][:40]}' → '{updated_title[:40]}'")

        # Update summary from analysis
        if result.get('summary'):
            update_data['summary'] = result['summary']

        try:
            supabase.table('wsj_story_threads') \
                .update(update_data) \
                .eq('id', t['id']) \
                .execute()

            # Save history snapshot
            supabase.table('wsj_thread_analysis_history').insert({
                'thread_id': t['id'],
                'article_count': current_count,
                'analysis_json': analysis_json,
            }).execute()

            analyzed += 1
        except Exception as e:
            print(f"    ERROR saving analysis: {e}")

    return analyzed


# ============================================================
# Step 5: Parent Grouping (Step C)
# ============================================================

PARENT_GROUPING_PROMPT = """You are a macro-event analyst. Group these story threads into parent macro-events.
Only group threads that are clearly part of the SAME macro event or crisis.

## Active Threads:
{thread_list}

Return ONLY valid JSON:
{{
  "groups": [
    {{
      "title": "<macro event name, max 6 words>",
      "thread_ids": ["id1", "id2", "id3"]
    }}
  ]
}}

Rules:
- Only create a parent group if 2+ threads clearly belong together (e.g., "Iran Crisis" grouping military, oil, and diplomatic threads)
- Do NOT group threads just because they're in the same sector or topic area
- Threads that don't fit any group should be omitted
- Max 10 groups
- Parent titles should be clear macro-event names, not vague categories"""


def group_threads_into_parents(supabase: Client, dry_run: bool = False) -> int:
    """Group threads into parent macro-events via LLM.

    Returns count of parent groups created/updated.
    """
    response = supabase.table('wsj_story_threads') \
        .select('id, title, member_count, status') \
        .in_('status', ['active', 'cooling']) \
        .order('member_count', desc=True) \
        .limit(80) \
        .execute()

    threads = response.data or []
    if len(threads) < 4:
        print("  Too few threads for parent grouping")
        return 0

    # Format thread list
    lines = []
    for t in threads:
        lines.append(f"- [ID: {t['id']}] \"{t['title']}\" ({t['member_count']} articles, {t['status']})")
    thread_list = '\n'.join(lines)

    prompt = PARENT_GROUPING_PROMPT.format(thread_list=thread_list)

    result = _call_gemini_json(prompt, PARENT_MODEL)
    if not result:
        return 0

    groups = result.get('groups', [])
    if not groups:
        print("  No parent groups identified")
        return 0

    thread_id_set = {t['id'] for t in threads}
    created = 0

    if dry_run:
        for g in groups:
            valid_ids = [tid for tid in g.get('thread_ids', []) if tid in thread_id_set]
            if len(valid_ids) >= 2:
                print(f"    [DRY] Parent: '{g['title']}' → {len(valid_ids)} threads")
                created += 1
        return created

    # Clear existing parent assignments (re-compute each run)
    supabase.table('wsj_story_threads') \
        .update({'parent_id': None}) \
        .in_('status', ['active', 'cooling']) \
        .execute()

    for g in groups:
        valid_ids = [tid for tid in g.get('thread_ids', []) if tid in thread_id_set]
        if len(valid_ids) < 2:
            continue

        title = g.get('title', 'Unnamed Group')

        try:
            # Upsert parent thread
            parent_resp = supabase.table('wsj_parent_threads').insert({
                'title': title,
                'status': 'active',
            }).execute()

            if parent_resp.data:
                parent_id = parent_resp.data[0]['id']
                for tid in valid_ids:
                    supabase.table('wsj_story_threads') \
                        .update({'parent_id': parent_id}) \
                        .eq('id', tid) \
                        .execute()
                created += 1
                print(f"    Parent: '{title}' → {len(valid_ids)} threads")
        except Exception as e:
            print(f"    ERROR creating parent '{title}': {e}")

    return created


# ============================================================
# Seed from golden dataset
# ============================================================

def seed_from_golden(supabase: Client, golden_path: str, dry_run: bool = False) -> None:
    """Seed wsj_story_threads from a golden dataset JSON file."""
    with open(golden_path) as f:
        golden = json.load(f)

    threads = golden['threads']
    version = golden.get('version', '?')
    print(f"  Golden dataset v{version}: {len(threads)} threads")

    all_article_ids = []
    for t in threads:
        all_article_ids.extend(t['articles'])
    print(f"  Total articles in golden threads: {len(all_article_ids)}")

    if dry_run:
        print("  [DRY RUN] Would reset all thread_id assignments and delete all wsj_story_threads")
        print(f"  [DRY RUN] Would create {len(threads)} threads")
        for t in threads[:5]:
            print(f"    - '{t['title']}' ({len(t['articles'])} articles)")
        if len(threads) > 5:
            print(f"    ... and {len(threads) - 5} more")
        return

    # Step 1: Reset all existing thread assignments
    print("  Resetting thread assignments...")
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

        centroid = np.mean(np.array(embeddings), axis=0)
        norm = np.linalg.norm(centroid)
        centroid = centroid / norm if norm > 0 else centroid

        first_seen = min(published_dates) if published_dates else '2026-01-01'
        last_seen = max(published_dates) if published_dates else '2026-01-01'

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

    thread_count = supabase.table('wsj_story_threads').select('id', count='exact').execute()
    threaded_count = supabase.table('wsj_items').select('id', count='exact').not_.is_('thread_id', 'null').execute()
    print(f"  DB state: {thread_count.count} threads, {threaded_count.count} threaded articles")


# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(description='Embed articles and assign to story threads')
    parser.add_argument('--dry-run', action='store_true', help='No DB writes')
    parser.add_argument('--embed-only', action='store_true', help='Skip thread matching')
    parser.add_argument('--legacy', action='store_true', help='Use old heuristic matching (fallback)')
    parser.add_argument('--skip-analysis', action='store_true', help='Skip thread analysis (step B)')
    parser.add_argument('--skip-parents', action='store_true', help='Skip parent grouping (step C)')
    parser.add_argument('--days', type=int, default=3,
                        help='Only process articles from last N days (default 3, 0=all)')
    parser.add_argument('--rejudge', action='store_true',
                        help='Re-evaluate already-judged articles')
    parser.add_argument('--seed-golden', type=str, default=None,
                        help='Seed threads from golden dataset JSON, then exit')
    args = parser.parse_args()

    print("=" * 60)
    print("Embed & Thread Pipeline")
    print("=" * 60)

    supabase = get_supabase_client()

    # Golden seed mode
    if args.seed_golden:
        print(f"\n[SEED] Seeding from golden dataset: {args.seed_golden}")
        t0 = time.time()
        seed_from_golden(supabase, args.seed_golden, dry_run=args.dry_run)
        print(f"  [TIMING] seed: {time.time() - t0:.1f}s")
        print("\n" + "=" * 60)
        print("Done (seed only).")
        return

    # Step 1: Embed
    print("\n[1/5] Embedding articles...")
    t0 = time.time()
    embedded = embed_articles(supabase, dry_run=args.dry_run)
    print(f"  Embedded: {embedded}")
    print(f"  [TIMING] embed: {time.time() - t0:.1f}s")

    if args.embed_only:
        print("\n--embed-only flag set, skipping thread matching.")
        return

    # Step 2: Assign threads
    mode_label = "legacy heuristic" if args.legacy else "LLM Judge"
    days_label = f"last {args.days}d" if args.days > 0 else "all"
    judged_label = "rejudge" if args.rejudge else "skip-judged"
    print(f"\n[2/5] Assigning threads ({mode_label}, {days_label}, {judged_label})...")
    t0 = time.time()
    result = assign_threads(supabase, dry_run=args.dry_run, legacy=args.legacy,
                            days=args.days, skip_judged=not args.rejudge)
    print(f"  Matched: {result['matched']}, New threads: {result['new_threads']}, Merged: {result.get('merged', 0)}")
    print(f"  [TIMING] assign: {time.time() - t0:.1f}s")

    # Step 3: Update thread statuses
    print("\n[3/5] Updating thread statuses...")
    t0 = time.time()
    status_counts = update_thread_statuses(supabase, dry_run=args.dry_run)
    print(f"  Cooling: {status_counts['cooling']}, Archived: {status_counts['archived']}")
    print(f"  [TIMING] status_update: {time.time() - t0:.1f}s")

    # Step 4: Analyze threads (Step B)
    if args.skip_analysis:
        print("\n[4/5] Skipping thread analysis (--skip-analysis)")
    else:
        print("\n[4/5] Analyzing threads...")
        t0 = time.time()
        analyzed = analyze_threads(supabase, dry_run=args.dry_run)
        print(f"  Analyzed: {analyzed} threads")
        print(f"  [TIMING] analysis: {time.time() - t0:.1f}s")

    # Step 5: Parent grouping (Step C)
    if args.skip_parents:
        print("\n[5/5] Skipping parent grouping (--skip-parents)")
    else:
        print("\n[5/5] Grouping threads into parents...")
        t0 = time.time()
        parent_count = group_threads_into_parents(supabase, dry_run=args.dry_run)
        print(f"  Parent groups: {parent_count}")
        print(f"  [TIMING] parents: {time.time() - t0:.1f}s")

    print("\n" + "=" * 60)
    print("Done.")


if __name__ == "__main__":
    main()
