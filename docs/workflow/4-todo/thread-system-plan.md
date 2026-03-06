<!-- Created: 2026-03-06 -->
# Thread System — Master Plan

Overall execution plan for the thread system overhaul.
Informed by: contamination analysis (`notebooks/thread_parent_analysis.ipynb`), discussion on data reuse, and `threading-refactor.md`.

---

## Key Findings (from analysis)

1. **Contamination is pipeline drift, not golden seed** — broad-topic threads (Restaurant Q4, AI Transformation) absorb unrelated articles via positive feedback loop at threshold 0.60
2. **Specific-event threads work fine** — Iran Military (72 articles, 100% on-topic), Gas Prices (50, 100% on-topic)
3. **Thread centroids converge** — 95.5% of thread pairs have sim >= 0.45, making centroid-based thread comparison useless
4. **LLM-only parent grouping works** — Gemini found 7 clean parent groups from 80 threads
5. **Per-article data is rich** — `wsj_llm_analysis` already has sentiment, tickers, entities, geographic_region, event_type, time_horizon, key_takeaway per article. Thread-level impacts can be **aggregated from article data** instead of separate LLM calls.

---

## Phase Order

```
Phase 1: LLM Judge refactor          ← START HERE
Phase 2: Parent grouping + title refresh
Phase 3: Frontend (Threads tab + detail page)
Phase 4: Impact analysis + portfolio  (later, needs user validation)
```

---

## Phase 1: LLM Judge Refactor

**Goal**: Replace heuristic matching with LLM judgment. Fixes contamination at the root.

### 1a. Schema Migration

```sql
-- New columns on wsj_story_threads
ALTER TABLE wsj_story_threads ADD COLUMN
  parent_id UUID,                    -- FK added after parent table exists
  summary TEXT,                      -- thread-level summary
  title_updated_at TIMESTAMPTZ;      -- when title was last refreshed

-- New table for parent threads
CREATE TABLE wsj_parent_threads (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title TEXT NOT NULL,
  status TEXT DEFAULT 'active',
  created_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE wsj_story_threads
  ADD CONSTRAINT fk_parent FOREIGN KEY (parent_id) REFERENCES wsj_parent_threads(id);
```

No `impacts` JSONB column yet — thread impacts will be aggregated from existing article-level data (`wsj_llm_analysis`).

### 1b. LLM Judge Implementation

Replace `match_to_threads()` in `7_embed_and_thread.py`:

**New flow per article:**
```
embedding → cosine pre-filter (top 5, threshold 0.40)
  → LLM Judge: article + candidates → assign or new_thread
  → output: { action, thread_id, reason, confidence, causal_link, title_still_accurate }
```

**LLM Judge output:**
```json
{
  "action": "assign",
  "thread_id": "abc-123",
  "reason": "Direct coverage of Iran military operations",
  "confidence": 0.92,
  "causal_link": {
    "related_thread_id": "def-456",
    "relationship": "caused_by",
    "note": "Oil price surge driven by Iran tensions"
  },
  "title_still_accurate": true
}
```

- `confidence` + `causal_link` — capture now because they require assignment-time context (can't regenerate later)
- No impact generation in the LLM call — existing article data covers it

**Keep:**
- Embedding generation, centroid storage, lifecycle logic, golden seed, merge threshold (0.92)

**Remove:**
- Time-weighted centroid, entity overlap, dynamic threshold, author boost, margin check, hard cap/frozen, CE merge pass
- ~15 constants → 5 constants
- Cross-encoder dependency

**Constants after:**
```python
CANDIDATE_THRESHOLD = 0.40
CANDIDATE_TOP_K = 5
THREAD_MERGE_THRESHOLD = 0.92
THREAD_COOLING_DAYS = 3
THREAD_ARCHIVE_DAYS = 14
```

### 1c. Validation

- Run old + new on same day's articles, compare
- Golden dataset v2.1: target >= 88% match accuracy
- Check: do contaminated threads (Restaurant Q4, AI Transformation) get fixed?
- `--legacy` flag to keep old logic as fallback

### 1d. Dead Code Removal

After validation passes:
- Delete `match_to_threads()`, `compute_time_weighted_centroid()`, `entity_overlap_score()`, CE merge code
- Remove `sentence_transformers.CrossEncoder` dependency
- Remove `Alibaba-NLP/gte-reranker-modernbert-base` model

---

## Phase 2: Parent Grouping + Title Refresh

**Goal**: Group threads into parents, refresh stale titles.

### 2a. Thread Intelligence Pass (one-time backfill)

For each active/cooling thread (~80):
- Fetch last 10 articles
- LLM call: "Given these articles, generate: updated title + one-line summary"
- Update `wsj_story_threads.title`, `summary`, `title_updated_at`

### 2b. Parent Grouping

Single LLM batch call with all active/cooling thread titles:
- "Group threads about the SAME macro event from different angles"
- Create `wsj_parent_threads` rows, set `parent_id` on children
- Run each pipeline execution (new threads may need parent assignment)

### 2c. Service Layer Update

`src/lib/news-service.ts`:
- `getActiveThreadsGrouped()` — JOIN `wsj_parent_threads`, return real parent groups
- Add thread-level aggregated data from `wsj_llm_analysis`:
  - Top tickers (from children articles' `tickers_mentioned`)
  - Dominant sentiment (from children articles' `sentiment`)
  - Geographic scope (from children articles' `geographic_region`)
- These aggregations replace the need for a separate `impacts` JSONB column

---

## Phase 3: Frontend

**Goal**: Build Threads tab + detail page. All data ready from Phases 1-2.

### Available data at this point

| Data | Source | Level |
|------|--------|-------|
| Thread title (fresh) | LLM refresh (Phase 2a) | thread |
| Thread summary | LLM refresh (Phase 2a) | thread |
| Parent grouping | LLM grouping (Phase 2b) | parent |
| Heat score | Existing computation | thread |
| Tickers mentioned | Aggregate from `wsj_llm_analysis.tickers_mentioned` | thread (from articles) |
| Sentiment | Aggregate from `wsj_llm_analysis.sentiment` | thread (from articles) |
| Geographic region | Aggregate from `wsj_llm_analysis.geographic_region` | thread (from articles) |
| Event type | Aggregate from `wsj_llm_analysis.event_type` | thread (from articles) |
| Key entities | Aggregate from `wsj_llm_analysis.key_entities` | thread (from articles) |

### 3a. Thread Detail Page `/news/thread/[id]`

- Thread title + summary
- Parent context ("Part of: Iran Crisis")
- Article timeline (paginated)
- Aggregated tickers, sentiment, entities
- Related threads (same parent)

### 3b. Threads Tab `/news?tab=threads`

- Hub Cards: parent group → child thread pills
- Per-thread: title, heat badge, article count, top tickers
- Tab rename: Stories → Threads

### 3c. Existing UI Updates

- ArticleCard carousel: thread title → link to detail page
- TimelineSection: link to full thread

---

## Phase 4: Impact Analysis + Portfolio (Later)

**Prerequisite**: User validation — talk to 5-10 target users before building.

### 4a. Thread-Level Impact Analysis

If article-level aggregation isn't rich enough:
- Add `impacts JSONB` to `wsj_story_threads`
- `exposure_rules.py` (~50 rules) for confidence validation
- LLM generates thread-level causal impacts (crude_oil ▲, airlines ▼)
- Only pursue if aggregated data proves insufficient

### 4b. Portfolio Relevance

- `user_watchlist` table
- `ticker_sectors.py` mapping (sector → tickers)
- "Market Exposure" badges on thread cards
- "Your Portfolio Intelligence" section

### 4c. Regulatory

- All copy: "relevance" / "exposure", never "recommendation"
- Review SEC publisher's exclusion criteria before launch

---

## Risk Management

| Risk | Mitigation |
|------|-----------|
| LLM Judge accuracy | Golden dataset A/B, `--legacy` fallback flag |
| Gemini API down | Fallback to cosine-only matching (legacy) |
| Backfill takes too long | 80 threads × 1 LLM call ≈ 2-3 min |
| Parent grouping quality | Manual review first batch, iterate prompt |
| Impact data insufficient from aggregation | Phase 4a adds dedicated impacts if needed |

---

## Files Affected

| File | Change | Phase |
|------|--------|-------|
| `supabase/migrations/` | parent_id, summary, title_updated_at, wsj_parent_threads | 1a |
| `scripts/7_embed_and_thread.py` | Major refactor: LLM Judge, remove heuristics | 1b |
| `scripts/7_embed_and_thread.py` | Title refresh + parent grouping steps | 2a, 2b |
| `src/lib/news-service.ts` | Parent JOIN, article-level aggregation | 2c |
| `src/app/news/thread/[id]/page.tsx` | New: thread detail page | 3a |
| `src/app/news/_components/StoriesTab.tsx` | Redesign → Hub Cards | 3b |
| `docs/1.3-news-threading.md` | Rewrite for new architecture | after Phase 1 |
| `docs/schema.md` | New columns/tables | after Phase 1 |

---

## Open Questions

1. **Pre-filter threshold (0.40)**: Test if too low (noise) or too high (misses causal links)
2. **Title refresh frequency**: Every pipeline run? Only when `title_still_accurate = false` from LLM Judge?
3. **Parent grouping frequency**: Every pipeline run or daily?
4. **Phase 4 validation**: How many users to talk to before building portfolio features?
