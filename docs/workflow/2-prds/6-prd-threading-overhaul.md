<!-- Updated: 2026-03-02 -->
# Threading System Full Overhaul

> **Origin**: `~/.claude/plans/graceful-roaming-coral.md` (Claude plan mode)
> **Notebook**: `notebooks/threading_gridsearch.ipynb`
> **Threading docs**: `docs/1.2-news-threading.md`

## Progress

| Phase | Status | Date | Notes |
|-------|--------|------|-------|
| 1. Status column migration | ✅ Done | 2026-02-27 | `012_thread_status.sql` applied |
| 2. Re-embed everything | ✅ Done | 2026-02-27 | 2,118 articles re-embedded (title+desc+summary) |
| 3. Author signal | ✅ Done | 2026-02-28 | Author boost + LLM prompt enrichment + cross-validation removed |
| 3.5. LLM window + summary | ✅ Done | 2026-03-01 | 102 threads, 348/2,118 threaded (16.4%), 3-day window |
| 4.0. Code changes | ✅ Done | 2026-03-02 | Time-weighted centroid, entity overlap, size penalty/EMA removed. 3 bugs fixed (author boost precision, threshold formula, late re-match centroid) |
| 4.1-4.5. Golden dataset + grid search | 📋 Notebook ready | 2026-03-02 | `notebooks/threading_gridsearch.ipynb` — 14 cells, awaiting execution |
| 5. Docs cleanup | ⏳ Partial | 2026-03-02 | `1.2-news-threading.md` updated; `schema.md`, `1-news-backend.md` pending |
| 6. Parent thread grouping | ⏳ Not started | — | Blocked on Phase 4 completion |

---

## Context

임베딩 입력을 title+desc → title+desc+summary로 변경했지만, 기존 2,089개 임베딩은 옛 방식으로 생성됨 (mixed state). 동시에 threading system의 여러 개선점이 확인됨: status 컬럼 부재, author signal 미활용, threshold 미검증. 이번에 전체를 한번에 정리한다.

### Current State
- 2,124 articles, 2,089 embeddings (title+desc), 106 threads
- Summary coverage: 55% (Feb), 93% creator coverage
- `wsj_story_threads.active`: boolean only (cooling/archived 구분 없음)
- Threshold 0.73: title+desc 기반으로 튜닝됨, 새 임베딩과 mismatched

---

## Phase 1: Status Column Migration — ✅ DONE

DB 스키마 먼저 변경. 코드가 status에 의존하므로.

### 1.1 Migration: `supabase/migrations/012_thread_status.sql`
```sql
-- Drop active boolean, replace with status text
ALTER TABLE wsj_story_threads DROP COLUMN active;
ALTER TABLE wsj_story_threads ADD COLUMN status TEXT NOT NULL DEFAULT 'active';
CREATE INDEX idx_wsj_story_threads_status ON wsj_story_threads(status);
-- No backfill needed — Phase 2 wipes all threads and re-creates with status
```

### 1.2 Why 3-day cooling cutoff? (Data-validated)

Gap analysis on 242 consecutive article pairs across 106 threads:
```
  0-1 days:  152 (62.8%)  ← most articles arrive same/next day
  2-3 days:   55 (22.7%)  ← 3 days covers 86% cumulative
  4-7 days:   29 (12.0%)  ← these get time penalty in cooling state
 8-14 days:    6 ( 2.5%)  ← rare, near-archive territory
   15+ days:   0 ( 0.0%)

  P50: 1 day | P75: 2 days | P90: 4 days | P95: 6 days
```

3 days = P86 — 86% of follow-up articles arrive while thread is still 'active' (base threshold). The remaining 14% arrive in 'cooling' (slightly higher threshold via time penalty), which is intentional: older threads should require more confident matches.

### 1.3 Code: `scripts/7_embed_and_thread.py`
- `get_active_threads()`: `.eq('active', True)` → `.in_('status', ['active', 'cooling'])`
- `deactivate_stale_threads()` → rename to `update_thread_statuses()`: set 'active'/'cooling'/'archived' based on last_seen
- Thread creation: `'active': True` → `'status': 'active'`
- Resurrection: set `status='active'` when archived thread gets new match

### 1.3 Code: `src/lib/news-service.ts`
- `StoryThread` interface: add `status: 'active' | 'cooling' | 'archived'`
- Thread queries: add `status` to select

### 1.4 Verify — CHECKPOINT 1 (requires approval)
1. Run migration SQL
2. Show result:
```sql
SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'wsj_story_threads';
```
3. Run `npm run lint` + `npm run lint:py`
4. **STOP — show results to user, wait for approval before Phase 2**

---

## Phase 2: Re-embed Everything — ✅ DONE (embeddings only, threads will be re-created)

### 2.1 Wipe
```sql
UPDATE wsj_items SET thread_id = NULL;
DELETE FROM wsj_story_threads;
DELETE FROM wsj_embeddings;
```

### 2.2 Code: Best summary selection in `7_embed_and_thread.py`

Add `_pick_best_summary()` helper — 1:N crawl results에서 best summary 선택:
- Priority: `relevance_flag='ok'` > highest `relevance_score` > longest summary
- Update `get_unembedded_articles()` select to include `relevance_flag, relevance_score`

### 2.3 Run
```bash
cd scripts/
python 7_embed_and_thread.py --embed-only          # ~5 min, ~2,124 articles
python 7_embed_and_thread.py --backfill-by-date     # ~30 min, includes LLM grouping
```

### 2.4 Verify — CHECKPOINT 2 (requires approval)
1. Show counts:
```sql
SELECT COUNT(*) FROM wsj_embeddings;
SELECT COUNT(*) FROM wsj_story_threads;
SELECT COUNT(*) FROM wsj_items WHERE thread_id IS NOT NULL;
SELECT status, COUNT(*) FROM wsj_story_threads GROUP BY status;
```
2. Show sample threads (top 5 by member_count):
```sql
SELECT title, member_count, status, first_seen, last_seen FROM wsj_story_threads ORDER BY member_count DESC LIMIT 5;
```
3. **STOP — show results to user, wait for approval before Phase 3**

---

## Phase 3: Author Signal — ✅ DONE (code implemented, not yet re-run)

Author boost code added to match_to_threads(). Constants are placeholders for Phase 4 tuning.

Also completed since original plan:
- LLM prompt enriched: now includes creator (author) + summary (first 2 sentences, max 120 chars) per article
- Cross-validation removed: cosine similarity can't capture causal relationships, was rejecting valid groups
- `LLM_GROUP_MIN_SIMILARITY` and `LLM_GROUP_MIN_PAIR_FLOOR` constants removed
- `get_unthreaded_articles()` and `get_date_range_articles()` now fetch summary from wsj_llm_analysis

---

## Phase 3.5: LLM Window + Thread Summary + Re-backfill — ✅ DONE

### 3.5.1 Migration: `wsj_story_threads` summary column
```sql
ALTER TABLE wsj_story_threads ADD COLUMN summary TEXT;
```

### 3.5.2 3-Day LLM Window
**Problem**: Daily LLM grouping means standalone articles on different days never meet.
**Solution**: Accumulate unmatched articles, run LLM every 3 days instead of every day.

Changes to `backfill_by_date()`:
- Days 1,2: centroid match only, accumulate unmatched
- Day 3: centroid match + LLM groups ALL unmatched from Days 1-3
- **No carryover**: Window resets after each 3-day cycle. Carryover was removed because standalones accumulated unboundedly (392+ articles → Gemini JSON parse error).

### 3.5.3 Thread Summary Generation
- LLM prompt returns `summary` per group (story progression, chronological, recent emphasis)
- Stored in `wsj_story_threads.summary` — 102/102 threads have summaries
- Summary generated ONLY at thread creation time (LLM grouping)
- Centroid-matched articles do NOT trigger summary refresh (cost)

### 3.5.4 Results
```
Total threads: 102
Threaded articles: 348 / 2,118 (16.4%)
Previous: 205 / 2,118 (9.7%) — nearly 2x improvement
JSON errors: 0
Max window size: 168 articles (stable)
Merges: 1 (Warsh → Fed)
```

---

## Phase 4: Golden Dataset + Threshold Tuning

### 4.0 Pre-requisites: Code Changes Before Grid Search

#### 4.0.1 Entity Overlap Boost (NEW)
`wsj_llm_analysis` already has `key_entities`, `people_mentioned`, `keywords`, `tickers_mentioned`.
When matching a new article to a thread, compute entity overlap with IDF weighting:
- **Useful fields**: key_entities (90% coverage, 1604 unique), people_mentioned (65%, 1037 unique), keywords (99%, 2305 unique), tickers_mentioned (21%, 231 unique — bonus signal when present)
- **Not useful**: geographic_region (54% "US"), event_type (51% "other"), sentiment, time_horizon
- **Entity dedup**: Runtime normalization via `normalize_entities()` in `7_embed_and_thread.py`
  - Strip title prefixes: "President Trump" → "Trump", "Secretary Bessent" → "Bessent"
  - Substring merge: ["Trump", "Donald Trump"] → "Donald Trump"; ["Fed", "Federal Reserve"] → "Federal Reserve"
  - Applied at entity overlap calculation time, no DB changes
  - Handles existing data inconsistencies (e.g., "Donald Trump" 54x + "Trump" 26x + "Trump administration" 34x)
- **IDF weighting**: Pre-compute entity frequency table across all articles. Common entities (Trump) get low weight, rare entities (Pete Liegl) get high weight.
- Grid search variable: `entity_weight` — [0.02, 0.04, 0.06]

#### 4.0.2 Time-Weighted Centroid (replaces EMA + Recent Window + Size Penalty)
**Problem**: Current EMA centroid is a snapshot frozen at last insertion time. It doesn't know "how old" each article is relative to NOW. As threads grow, centroid generalizes and over-matches.

**Solution**: Replace EMA with time-weighted centroid. At matching time, recompute centroid with exponential time decay:
```python
# At matching time (e.g., Jan 20):
#   Article A (Jan 1, 20 days ago):  weight = exp(-decay * 20) = 0.14
#   Article B (Jan 2, 19 days ago):  weight = exp(-decay * 19) = 0.15
#   Article C (Jan 10, 10 days ago): weight = exp(-decay * 10) = 0.37
# Centroid naturally tilts toward Article C (most recent)
weighted_centroid = sum(weight_i * embedding_i) / sum(weight_i)
```

**Why this replaces 3 things at once:**
- **EMA** → time-weighted is strictly better (time-based vs insertion-order-based)
- **Recent Window** → time-weighted centroid already reflects recent direction (no separate check needed)
- **Size Penalty** → time-weighted centroid naturally handles large threads (old articles decay, centroid stays focused)

**Implementation:**
- Remove `CENTROID_EMA_BASE_ALPHA` constant
- DB: continue storing centroid for fast approximate matching, but recompute time-weighted for final comparison
- OR: store member article IDs + timestamps per thread, recompute at match time
- Memory cost: ~100 threads × avg 3.4 articles × 768 floats × 4 bytes ≈ 1MB (trivial)
- Grid search variable: `centroid_decay` — [0.05, 0.08, 0.10, 0.15] (per day)

#### 4.0.3 Size Penalty Removal
Time-weighted centroid solves the same problem more precisely. Size penalty was a blunt "bigger thread = higher threshold" rule. Removed.

#### 4.0.4 Fixed Constants (not in grid search)
```
FIXED (validated or low impact):
- THREAD_MATCH_MARGIN = 0.03           (low performance impact, keep fixed)
- AUTHOR_BOOST_WINDOW_HOURS = 48       (P75=2 days validated in Phase 1)
- THREAD_COOLING_DAYS = 3              (P86 validated in Phase 1)
- THREAD_ARCHIVE_DAYS = 14             (reasonable default)
- THREAD_HARD_CAP = 50                 (safety net)
```

### 4.0.5 Constants to tune (grid search)
```
GRID SEARCH (5 variables, 1,536 combinations):
- THREAD_BASE_THRESHOLD:    [0.60, 0.65, 0.68, 0.70, 0.73, 0.75, 0.78, 0.80]
- AUTHOR_BOOST_THRESHOLD:   [0.50, 0.55, 0.60, 0.65]
- THREAD_TIME_PENALTY:      [0.005, 0.01, 0.015, 0.02]
- CENTROID_DECAY:            [0.05, 0.08, 0.10, 0.15] ← NEW (replaces EMA + recent window)
- ENTITY_WEIGHT:            [0.02, 0.04, 0.06]        ← NEW

REMOVED from search:
- SIZE_PENALTY              (replaced by time-weighted centroid)
- MATCH_MARGIN              (fixed at 0.03)
- AUTHOR_BOOST_WINDOW       (fixed at 48h)
- CENTROID_EMA_BASE_ALPHA   (replaced by time-weighted centroid)
- LLM_GROUP_MIN_SIMILARITY  (cross-validation removed in Phase 3)
- LLM_GROUP_MIN_PAIR_FLOOR  (same)
```

### 4.1 Golden Dataset Construction (semi-auto)

**Scope**: All articles with `published_at < '2026-03-01'` (2,118 articles). Excludes 56 post-merge articles that have old-format embeddings.

**Step 1: Run baseline pipeline with LOW threshold**
- Temporarily set THREAD_BASE_THRESHOLD = 0.58, AUTHOR_BOOST_THRESHOLD = 0.45
- Run full backfill with all logic enabled (author boost, entity overlap, recent window, LLM grouping)
- Intentionally over-groups → more articles in threads → fewer standalones
- Target: 30-50% threading rate (current: 16.4%)

**Step 2: Export baseline threads for Gemini review**
- Export each thread: title, member articles (title, description, published_at, creator)
- Also export standalone articles (no thread)
- Save to `notebooks/golden_baseline.json`

**Step 3: Gemini validation (3 passes)**

**Q1 — Thread internal validation** (per thread):
```
This thread was auto-generated by our pipeline.
Thread title: "Fed Rate Hold & Market Impact"
Articles:
  a1: "Fed Holds Rates Steady" (2026-02-15, Amrith Ramkumar)
  a5: "Markets Rally After Fed Decision" (2026-02-16, Tim Higgins)
  a9: "Housing Sector Responds to Rate Pause" (2026-02-18)
  a14: "CPI Data Shows Inflation Cooling" (2026-02-17)

IMPORTANT: Same topic alone is NOT enough. Articles must be about the same SPECIFIC EVENT.
When in doubt, mark as NOT belonging.

Evaluate:
1. CONTAMINATION: Which articles do NOT belong? (different specific event)
2. SPLIT: Should this thread be split into sub-stories?
3. LINKS: For articles that belong, label the relationship:
   - "topical": same event, different angle/source
   - "causal": A caused/led to B (e.g. rate hold → market rally)
   - "analysis": commentary/analysis of the event
Respond in JSON only. Temperature 0.1.
```

**Q2 — Thread-pair comparison** (for similar threads, centroid similarity > 0.65):
```
Should these two threads be merged? Or are they parent-child?
Thread A: [title + articles]
Thread B: [title + articles]
→ "merge" / "parent-child" / "separate"
```
(Also serves as Phase 6 parent-thread ground truth)

**Q3 — Standalone validation** (batches of 30-40):
```
These articles were not assigned to any thread.
Should any form new threads together?
Should any join an existing thread listed above?
When in doubt, keep as standalone.
```

**Step 4: User manual review (CHECKPOINT)**
- Gemini results with confidence levels (high/medium/low)
- confidence=high → auto-accept
- confidence=medium/low → user reviews
- Final golden dataset saved to `notebooks/golden_dataset.json`

**Golden dataset format:**
```json
{
  "threads": [
    {
      "title": "Fed Rate Hold & Market Impact",
      "articles": ["a1", "a5", "a9", "a20"],
      "links": [
        {"from": "a1", "to": "a5", "type": "causal"},
        {"from": "a1", "to": "a9", "type": "analysis"},
        {"from": "a1", "to": "a20", "type": "causal"}
      ]
    }
  ],
  "singletons": ["a3", "a14", "a22"]
}
```

### 4.2 Evaluation Harness

**Three metrics + composite:**
```
Contamination: % of system threads containing articles from different golden threads
  → "Fed" article + "CPI" article in same system thread = contamination

Fragmentation: % of golden threads whose articles are split across multiple system threads
  → Golden thread has 5 articles but system split them into 3 threads = fragmentation

Causal Recall: % of golden causal link pairs in same system thread
  → Golden says a1→a5 is causal; are they in same system thread?

Composite: (1 - contamination) × 0.3 + (1 - fragmentation) × 0.3 + causal_recall × 0.4
```

Multi-membership articles (belonging to 2+ threads in golden) get special handling in evaluation.

Implement as `evaluate_threading(system_threads, golden_dataset) → scores` in notebook.

### 4.3 Grid Search

**Simulation approach**: Run centroid matching in-memory (pure Python), not full backfill 1,152 times. Pre-load all embeddings + entity data, simulate match_to_threads() logic per parameter combo.

**Validation**: Run simulation with CURRENT parameters first. Verify result matches actual backfill output (102 threads, 348 articles). If mismatch, fix simulation before grid search.

**Note**: LLM grouping is NOT simulated (non-deterministic, expensive). Only centroid matching + author boost + entity overlap + recent window are swept. LLM grouping results from the baseline run are treated as fixed.

Optimize for: maximize(composite score)

### 4.4 Re-thread with tuned constants
- Wipe threads (keep embeddings)
- Update constants in 7_embed_and_thread.py
- Re-run backfill-by-date

### 4.5 Verify — CHECKPOINT 4 (requires approval)
1. Show golden dataset stats (thread count, article count, causal link count)
2. Show grid search results: best params + 3 metrics + composite
3. Show threading rate with new constants
4. Compare before/after on specific example threads
5. **STOP — user reviews, decides to accept or re-tune**

---

## Phase 5: Cleanup (~10 min)

- Update docs: `schema.md`, `1.2-news-threading.md`, `2-news-frontend.md`, `1-news-backend.md`

---

## Phase 6: Parent Thread Grouping

### Concept
- **Parent thread** = LLM이 생성한 그룹 제목. 기사를 직접 갖지 않음.
- **Thread (sub)** = 현재의 thread와 동일. 기사, centroid, status 전부 여기.
- 여러 thread가 하나의 parent에 속함. parent 없는 독립 thread도 가능 (parent_id = NULL).

### Example
```
Parent: "Anthropic vs Pentagon AI Battle" (LLM 생성 제목)
  ├── Thread: "Pentagon Embraces OpenAI Over Anthropic" (3 articles)
  ├── Thread: "Anthropic Safety Guardrails Debate" (2 articles)
  └── Thread: "What's at Stake for AI Industry" (1 article)

Parent: "AI Industry Workforce Impact"
  ├── Thread: "Block Cuts 4,000 Jobs" (4 articles)
  └── Thread: "Tech Layoff Wave Concerns" (2 articles)

Thread: "Nvidia New Inference Chip" (3 articles, no parent)
```

### 6.1 Migration: `supabase/migrations/013_parent_threads.sql`
```sql
CREATE TABLE wsj_parent_threads (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    title TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE wsj_story_threads ADD COLUMN parent_id UUID REFERENCES wsj_parent_threads(id);
CREATE INDEX idx_wsj_story_threads_parent ON wsj_story_threads(parent_id);
```

### 6.2 Grouping Logic
- **When**: After Phase 2 backfill creates all threads, run parent grouping as a batch.
- **How**: LLM takes all active/cooling thread titles + centroids → groups related threads → generates parent title.
- **Threshold**: Thread centroid similarity > TBD (needs tuning, likely 0.70-0.80 range) to be candidates for same parent.
- **Daily**: When new thread is created, check if it belongs to an existing parent (centroid similarity to parent's child threads).

### 6.3 Code Changes
- `7_embed_and_thread.py`: New step — `group_threads_into_parents()` after thread assignment
- `news-service.ts`: `ParentThread` interface, query threads grouped by parent
- Frontend: Display parent as collapsible group header

### 6.4 Decisions
- [x] Parent centroid: **YES** — store as avg of child centroids. Efficient for "does new thread belong to existing parent?" (1 comparison vs N).
- [x] Parent title update: **NO** — keep initial LLM-generated title. Frequent changes confuse users.
- [x] Parent status: **NONE** — parent has no status field. Frontend derives from child statuses (any active child → show parent).
- [x] Drift auto-detach: **DEFERRED** — no logic for now. Run parent grouping, observe 2-3 weeks, decide based on real data.
- [x] Frontend UX: **SEPARATE** — handled in frontend plan (accordion UI with StoriesTab component).

### 6.5 Why After Phase 5
- Thread 품질이 안정된 후에 grouping해야 의미 있음
- Phase 4에서 threshold 튜닝이 끝나야 thread 경계가 확정됨
- Parent grouping은 thread 위의 레이어이므로 기존 로직에 영향 없음

---

## Rollback

| Phase | Rollback |
|-------|----------|
| 1 (status) | Drop status column, git revert code |
| 2 (re-embed) | Re-run embed + backfill with old code (~35 min + ~$1-2 LLM) |
| 3 (author) | Git revert code only, no DB change |
| 4 (threshold) | Revert constants |
| 6 (parent threads) | Drop parent_id column, drop wsj_parent_threads table, git revert code |

---

## Critical Files
| File | Changes |
|------|---------|
| `scripts/7_embed_and_thread.py` | All 4 phases |
| `src/lib/news-service.ts` | Phase 1 (StoryThread interface) |
| `supabase/migrations/012_thread_status.sql` | Phase 1 (new) |
| `notebooks/reranker_causal_test.ipynb` | Phase 4 |
| `docs/schema.md` | Phase 5 |
| `docs/1.2-news-threading.md` | Phase 5 |
| `supabase/migrations/013_parent_threads.sql` | Phase 6 (new) |



-----
# Initial Plan
# Threading System Full Overhaul

## Context

임베딩 입력을 title+desc → title+desc+summary로 변경했지만, 기존 2,089개 임베딩은 옛 방식으로 생성됨 (mixed state). 동시에 threading system의 여러 개선점이 확인됨: status 컬럼 부재, author signal 미활용, threshold 미검증. 이번에 전체를 한번에 정리한다.

### Current State
- 2,124 articles, 2,089 embeddings (title+desc), 106 threads
- Summary coverage: 55% (Feb), 93% creator coverage
- `wsj_story_threads.active`: boolean only (cooling/archived 구분 없음)
- Threshold 0.73: title+desc 기반으로 튜닝됨, 새 임베딩과 mismatched

---

## Phase 1: Status Column Migration — ✅ DONE

DB 스키마 먼저 변경. 코드가 status에 의존하므로.

### 1.1 Migration: `supabase/migrations/012_thread_status.sql`
```sql
-- Drop active boolean, replace with status text
ALTER TABLE wsj_story_threads DROP COLUMN active;
ALTER TABLE wsj_story_threads ADD COLUMN status TEXT NOT NULL DEFAULT 'active';
CREATE INDEX idx_wsj_story_threads_status ON wsj_story_threads(status);
-- No backfill needed — Phase 2 wipes all threads and re-creates with status
```

### 1.2 Why 3-day cooling cutoff? (Data-validated)

Gap analysis on 242 consecutive article pairs across 106 threads:
```
  0-1 days:  152 (62.8%)  ← most articles arrive same/next day
  2-3 days:   55 (22.7%)  ← 3 days covers 86% cumulative
  4-7 days:   29 (12.0%)  ← these get time penalty in cooling state
 8-14 days:    6 ( 2.5%)  ← rare, near-archive territory
   15+ days:   0 ( 0.0%)

  P50: 1 day | P75: 2 days | P90: 4 days | P95: 6 days
```

3 days = P86 — 86% of follow-up articles arrive while thread is still 'active' (base threshold). The remaining 14% arrive in 'cooling' (slightly higher threshold via time penalty), which is intentional: older threads should require more confident matches.

### 1.3 Code: `scripts/7_embed_and_thread.py`
- `get_active_threads()`: `.eq('active', True)` → `.in_('status', ['active', 'cooling'])`
- `deactivate_stale_threads()` → rename to `update_thread_statuses()`: set 'active'/'cooling'/'archived' based on last_seen
- Thread creation: `'active': True` → `'status': 'active'`
- Resurrection: set `status='active'` when archived thread gets new match

### 1.3 Code: `src/lib/news-service.ts`
- `StoryThread` interface: add `status: 'active' | 'cooling' | 'archived'`
- Thread queries: add `status` to select

### 1.4 Verify — CHECKPOINT 1 (requires approval)
1. Run migration SQL
2. Show result:
```sql
SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'wsj_story_threads';
```
3. Run `npm run lint` + `npm run lint:py`
4. **STOP — show results to user, wait for approval before Phase 2**

---

## Phase 2: Re-embed Everything — ✅ DONE (embeddings only, threads will be re-created)

### 2.1 Wipe
```sql
UPDATE wsj_items SET thread_id = NULL;
DELETE FROM wsj_story_threads;
DELETE FROM wsj_embeddings;
```

### 2.2 Code: Best summary selection in `7_embed_and_thread.py`

Add `_pick_best_summary()` helper — 1:N crawl results에서 best summary 선택:
- Priority: `relevance_flag='ok'` > highest `relevance_score` > longest summary
- Update `get_unembedded_articles()` select to include `relevance_flag, relevance_score`

### 2.3 Run
```bash
cd scripts/
python 7_embed_and_thread.py --embed-only          # ~5 min, ~2,124 articles
python 7_embed_and_thread.py --backfill-by-date     # ~30 min, includes LLM grouping
```

### 2.4 Verify — CHECKPOINT 2 (requires approval)
1. Show counts:
```sql
SELECT COUNT(*) FROM wsj_embeddings;
SELECT COUNT(*) FROM wsj_story_threads;
SELECT COUNT(*) FROM wsj_items WHERE thread_id IS NOT NULL;
SELECT status, COUNT(*) FROM wsj_story_threads GROUP BY status;
```
2. Show sample threads (top 5 by member_count):
```sql
SELECT title, member_count, status, first_seen, last_seen FROM wsj_story_threads ORDER BY member_count DESC LIMIT 5;
```
3. **STOP — show results to user, wait for approval before Phase 3**

---

## Phase 3: Author Signal — ✅ DONE (code implemented, not yet re-run)

Author boost code added to match_to_threads(). Constants are placeholders for Phase 4 tuning.

Also completed since original plan:
- LLM prompt enriched: now includes creator (author) + summary (first 2 sentences, max 120 chars) per article
- Cross-validation removed: cosine similarity can't capture causal relationships, was rejecting valid groups
- `LLM_GROUP_MIN_SIMILARITY` and `LLM_GROUP_MIN_PAIR_FLOOR` constants removed
- `get_unthreaded_articles()` and `get_date_range_articles()` now fetch summary from wsj_llm_analysis

---

## Phase 3.5: LLM Window + Thread Summary + Re-backfill — ✅ DONE

### 3.5.1 Migration: `wsj_story_threads` summary column
```sql
ALTER TABLE wsj_story_threads ADD COLUMN summary TEXT;
```

### 3.5.2 3-Day LLM Window
**Problem**: Daily LLM grouping means standalone articles on different days never meet.
**Solution**: Accumulate unmatched articles, run LLM every 3 days instead of every day.

Changes to `backfill_by_date()`:
- Days 1,2: centroid match only, accumulate unmatched
- Day 3: centroid match + LLM groups ALL unmatched from Days 1-3
- **No carryover**: Window resets after each 3-day cycle. Carryover was removed because standalones accumulated unboundedly (392+ articles → Gemini JSON parse error).

### 3.5.3 Thread Summary Generation
- LLM prompt returns `summary` per group (story progression, chronological, recent emphasis)
- Stored in `wsj_story_threads.summary` — 102/102 threads have summaries
- Summary generated ONLY at thread creation time (LLM grouping)
- Centroid-matched articles do NOT trigger summary refresh (cost)

### 3.5.4 Results
```
Total threads: 102
Threaded articles: 348 / 2,118 (16.4%)
Previous: 205 / 2,118 (9.7%) — nearly 2x improvement
JSON errors: 0
Max window size: 168 articles (stable)
Merges: 1 (Warsh → Fed)
```

---

## Phase 4: Golden Dataset + Threshold Tuning

### 4.0 Pre-requisites: Code Changes Before Grid Search

#### 4.0.1 Entity Overlap Boost (NEW)
`wsj_llm_analysis` already has `key_entities`, `people_mentioned`, `keywords`, `tickers_mentioned`.
When matching a new article to a thread, compute entity overlap with IDF weighting:
- **Useful fields**: key_entities (90% coverage, 1604 unique), people_mentioned (65%, 1037 unique), keywords (99%, 2305 unique), tickers_mentioned (21%, 231 unique — bonus signal when present)
- **Not useful**: geographic_region (54% "US"), event_type (51% "other"), sentiment, time_horizon
- **Entity dedup**: Runtime normalization via `normalize_entities()` in `7_embed_and_thread.py`
  - Strip title prefixes: "President Trump" → "Trump", "Secretary Bessent" → "Bessent"
  - Substring merge: ["Trump", "Donald Trump"] → "Donald Trump"; ["Fed", "Federal Reserve"] → "Federal Reserve"
  - Applied at entity overlap calculation time, no DB changes
  - Handles existing data inconsistencies (e.g., "Donald Trump" 54x + "Trump" 26x + "Trump administration" 34x)
- **IDF weighting**: Pre-compute entity frequency table across all articles. Common entities (Trump) get low weight, rare entities (Pete Liegl) get high weight.
- Grid search variable: `entity_weight` — [0.02, 0.04, 0.06]

#### 4.0.2 Time-Weighted Centroid (replaces EMA + Recent Window + Size Penalty)
**Problem**: Current EMA centroid is a snapshot frozen at last insertion time. It doesn't know "how old" each article is relative to NOW. As threads grow, centroid generalizes and over-matches.

**Solution**: Replace EMA with time-weighted centroid. At matching time, recompute centroid with exponential time decay:
```python
# At matching time (e.g., Jan 20):
#   Article A (Jan 1, 20 days ago):  weight = exp(-decay * 20) = 0.14
#   Article B (Jan 2, 19 days ago):  weight = exp(-decay * 19) = 0.15
#   Article C (Jan 10, 10 days ago): weight = exp(-decay * 10) = 0.37
# Centroid naturally tilts toward Article C (most recent)
weighted_centroid = sum(weight_i * embedding_i) / sum(weight_i)
```

**Why this replaces 3 things at once:**
- **EMA** → time-weighted is strictly better (time-based vs insertion-order-based)
- **Recent Window** → time-weighted centroid already reflects recent direction (no separate check needed)
- **Size Penalty** → time-weighted centroid naturally handles large threads (old articles decay, centroid stays focused)

**Implementation:**
- Remove `CENTROID_EMA_BASE_ALPHA` constant
- DB: continue storing centroid for fast approximate matching, but recompute time-weighted for final comparison
- OR: store member article IDs + timestamps per thread, recompute at match time
- Memory cost: ~100 threads × avg 3.4 articles × 768 floats × 4 bytes ≈ 1MB (trivial)
- Grid search variable: `centroid_decay` — [0.05, 0.08, 0.10, 0.15] (per day)

#### 4.0.3 Size Penalty Removal
Time-weighted centroid solves the same problem more precisely. Size penalty was a blunt "bigger thread = higher threshold" rule. Removed.

#### 4.0.4 Fixed Constants (not in grid search)
```
FIXED (validated or low impact):
- THREAD_MATCH_MARGIN = 0.03           (low performance impact, keep fixed)
- AUTHOR_BOOST_WINDOW_HOURS = 48       (P75=2 days validated in Phase 1)
- THREAD_COOLING_DAYS = 3              (P86 validated in Phase 1)
- THREAD_ARCHIVE_DAYS = 14             (reasonable default)
- THREAD_HARD_CAP = 50                 (safety net)
```

### 4.0.5 Constants to tune (grid search)
```
GRID SEARCH (5 variables, 1,536 combinations):
- THREAD_BASE_THRESHOLD:    [0.60, 0.65, 0.68, 0.70, 0.73, 0.75, 0.78, 0.80]
- AUTHOR_BOOST_THRESHOLD:   [0.50, 0.55, 0.60, 0.65]
- THREAD_TIME_PENALTY:      [0.005, 0.01, 0.015, 0.02]
- CENTROID_DECAY:            [0.05, 0.08, 0.10, 0.15] ← NEW (replaces EMA + recent window)
- ENTITY_WEIGHT:            [0.02, 0.04, 0.06]        ← NEW

REMOVED from search:
- SIZE_PENALTY              (replaced by time-weighted centroid)
- MATCH_MARGIN              (fixed at 0.03)
- AUTHOR_BOOST_WINDOW       (fixed at 48h)
- CENTROID_EMA_BASE_ALPHA   (replaced by time-weighted centroid)
- LLM_GROUP_MIN_SIMILARITY  (cross-validation removed in Phase 3)
- LLM_GROUP_MIN_PAIR_FLOOR  (same)
```

### 4.1 Golden Dataset Construction (semi-auto)

**Scope**: All articles with `published_at < '2026-03-01'` (2,118 articles). Excludes 56 post-merge articles that have old-format embeddings.

**Step 1: Run baseline pipeline with LOW threshold**
- Temporarily set THREAD_BASE_THRESHOLD = 0.58, AUTHOR_BOOST_THRESHOLD = 0.45
- Run full backfill with all logic enabled (author boost, entity overlap, recent window, LLM grouping)
- Intentionally over-groups → more articles in threads → fewer standalones
- Target: 30-50% threading rate (current: 16.4%)

**Step 2: Export baseline threads for Gemini review**
- Export each thread: title, member articles (title, description, published_at, creator)
- Also export standalone articles (no thread)
- Save to `notebooks/golden_baseline.json`

**Step 3: Gemini validation (3 passes)**

**Q1 — Thread internal validation** (per thread):
```
This thread was auto-generated by our pipeline.
Thread title: "Fed Rate Hold & Market Impact"
Articles:
  a1: "Fed Holds Rates Steady" (2026-02-15, Amrith Ramkumar)
  a5: "Markets Rally After Fed Decision" (2026-02-16, Tim Higgins)
  a9: "Housing Sector Responds to Rate Pause" (2026-02-18)
  a14: "CPI Data Shows Inflation Cooling" (2026-02-17)

IMPORTANT: Same topic alone is NOT enough. Articles must be about the same SPECIFIC EVENT.
When in doubt, mark as NOT belonging.

Evaluate:
1. CONTAMINATION: Which articles do NOT belong? (different specific event)
2. SPLIT: Should this thread be split into sub-stories?
3. LINKS: For articles that belong, label the relationship:
   - "topical": same event, different angle/source
   - "causal": A caused/led to B (e.g. rate hold → market rally)
   - "analysis": commentary/analysis of the event
Respond in JSON only. Temperature 0.1.
```

**Q2 — Thread-pair comparison** (for similar threads, centroid similarity > 0.65):
```
Should these two threads be merged? Or are they parent-child?
Thread A: [title + articles]
Thread B: [title + articles]
→ "merge" / "parent-child" / "separate"
```
(Also serves as Phase 6 parent-thread ground truth)

**Q3 — Standalone validation** (batches of 30-40):
```
These articles were not assigned to any thread.
Should any form new threads together?
Should any join an existing thread listed above?
When in doubt, keep as standalone.
```

**Step 4: User manual review (CHECKPOINT)**
- Gemini results with confidence levels (high/medium/low)
- confidence=high → auto-accept
- confidence=medium/low → user reviews
- Final golden dataset saved to `notebooks/golden_dataset.json`

**Golden dataset format:**
```json
{
  "threads": [
    {
      "title": "Fed Rate Hold & Market Impact",
      "articles": ["a1", "a5", "a9", "a20"],
      "links": [
        {"from": "a1", "to": "a5", "type": "causal"},
        {"from": "a1", "to": "a9", "type": "analysis"},
        {"from": "a1", "to": "a20", "type": "causal"}
      ]
    }
  ],
  "singletons": ["a3", "a14", "a22"]
}
```

### 4.2 Evaluation Harness

**Three metrics + composite:**
```
Contamination: % of system threads containing articles from different golden threads
  → "Fed" article + "CPI" article in same system thread = contamination

Fragmentation: % of golden threads whose articles are split across multiple system threads
  → Golden thread has 5 articles but system split them into 3 threads = fragmentation

Causal Recall: % of golden causal link pairs in same system thread
  → Golden says a1→a5 is causal; are they in same system thread?

Composite: (1 - contamination) × 0.3 + (1 - fragmentation) × 0.3 + causal_recall × 0.4
```

Multi-membership articles (belonging to 2+ threads in golden) get special handling in evaluation.

Implement as `evaluate_threading(system_threads, golden_dataset) → scores` in notebook.

### 4.3 Grid Search

**Simulation approach**: Run centroid matching in-memory (pure Python), not full backfill 1,152 times. Pre-load all embeddings + entity data, simulate match_to_threads() logic per parameter combo.

**Validation**: Run simulation with CURRENT parameters first. Verify result matches actual backfill output (102 threads, 348 articles). If mismatch, fix simulation before grid search.

**Note**: LLM grouping is NOT simulated (non-deterministic, expensive). Only centroid matching + author boost + entity overlap + recent window are swept. LLM grouping results from the baseline run are treated as fixed.

Optimize for: maximize(composite score)

### 4.4 Re-thread with tuned constants
- Wipe threads (keep embeddings)
- Update constants in 7_embed_and_thread.py
- Re-run backfill-by-date

### 4.5 Verify — CHECKPOINT 4 (requires approval)
1. Show golden dataset stats (thread count, article count, causal link count)
2. Show grid search results: best params + 3 metrics + composite
3. Show threading rate with new constants
4. Compare before/after on specific example threads
5. **STOP — user reviews, decides to accept or re-tune**

---

## Phase 5: Cleanup (~10 min)

- Update docs: `schema.md`, `1.2-news-threading.md`, `2-news-frontend.md`, `1-news-backend.md`

---

## Phase 6: Parent Thread Grouping

### Concept
- **Parent thread** = LLM이 생성한 그룹 제목. 기사를 직접 갖지 않음.
- **Thread (sub)** = 현재의 thread와 동일. 기사, centroid, status 전부 여기.
- 여러 thread가 하나의 parent에 속함. parent 없는 독립 thread도 가능 (parent_id = NULL).

### Example
```
Parent: "Anthropic vs Pentagon AI Battle" (LLM 생성 제목)
  ├── Thread: "Pentagon Embraces OpenAI Over Anthropic" (3 articles)
  ├── Thread: "Anthropic Safety Guardrails Debate" (2 articles)
  └── Thread: "What's at Stake for AI Industry" (1 article)

Parent: "AI Industry Workforce Impact"
  ├── Thread: "Block Cuts 4,000 Jobs" (4 articles)
  └── Thread: "Tech Layoff Wave Concerns" (2 articles)

Thread: "Nvidia New Inference Chip" (3 articles, no parent)
```

### 6.1 Migration: `supabase/migrations/013_parent_threads.sql`
```sql
CREATE TABLE wsj_parent_threads (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    title TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE wsj_story_threads ADD COLUMN parent_id UUID REFERENCES wsj_parent_threads(id);
CREATE INDEX idx_wsj_story_threads_parent ON wsj_story_threads(parent_id);
```

### 6.2 Grouping Logic
- **When**: After Phase 2 backfill creates all threads, run parent grouping as a batch.
- **How**: LLM takes all active/cooling thread titles + centroids → groups related threads → generates parent title.
- **Threshold**: Thread centroid similarity > TBD (needs tuning, likely 0.70-0.80 range) to be candidates for same parent.
- **Daily**: When new thread is created, check if it belongs to an existing parent (centroid similarity to parent's child threads).

### 6.3 Code Changes
- `7_embed_and_thread.py`: New step — `group_threads_into_parents()` after thread assignment
- `news-service.ts`: `ParentThread` interface, query threads grouped by parent
- Frontend: Display parent as collapsible group header

### 6.4 Decisions
- [x] Parent centroid: **YES** — store as avg of child centroids. Efficient for "does new thread belong to existing parent?" (1 comparison vs N).
- [x] Parent title update: **NO** — keep initial LLM-generated title. Frequent changes confuse users.
- [x] Parent status: **NONE** — parent has no status field. Frontend derives from child statuses (any active child → show parent).
- [x] Drift auto-detach: **DEFERRED** — no logic for now. Run parent grouping, observe 2-3 weeks, decide based on real data.
- [x] Frontend UX: **SEPARATE** — handled in frontend plan (accordion UI with StoriesTab component).

### 6.5 Why After Phase 5
- Thread 품질이 안정된 후에 grouping해야 의미 있음
- Phase 4에서 threshold 튜닝이 끝나야 thread 경계가 확정됨
- Parent grouping은 thread 위의 레이어이므로 기존 로직에 영향 없음

---

## Rollback

| Phase | Rollback |
|-------|----------|
| 1 (status) | Drop status column, git revert code |
| 2 (re-embed) | Re-run embed + backfill with old code (~35 min + ~$1-2 LLM) |
| 3 (author) | Git revert code only, no DB change |
| 4 (threshold) | Revert constants |
| 6 (parent threads) | Drop parent_id column, drop wsj_parent_threads table, git revert code |

---

## Critical Files
| File | Changes |
|------|---------|
| `scripts/7_embed_and_thread.py` | All 4 phases |
| `src/lib/news-service.ts` | Phase 1 (StoryThread interface) |
| `supabase/migrations/012_thread_status.sql` | Phase 1 (new) |
| `notebooks/reranker_causal_test.ipynb` | Phase 4 |
| `docs/schema.md` | Phase 5 |
| `docs/1.2-news-threading.md` | Phase 5 |
| `supabase/migrations/013_parent_threads.sql` | Phase 6 (new) |

