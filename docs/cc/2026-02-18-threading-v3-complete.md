<!-- Updated: 2026-02-18 -->
# Session Handoff — 2026-02-18

## What Was Accomplished

### 1. OpenAI → Gemini Conversion (Complete)
- **scripts/llm_analysis.py**: Converted from `OpenAI(api_key=...)` to `genai.Client(api_key=...)`, changed model to `gemini-2.5-flash`
- **scripts/llm_backfill.py**: Same conversion
- **scripts/crawl_ranked.py**: Same conversion
- **scripts/requirements.txt**: Removed `openai>=1.0.0` (kept `openai-whisper` for TTS)
- **.github/workflows/finance-pipeline.yml**: Updated all `OPENAI_API_KEY` → `GEMINI_API_KEY` references
- **scripts/run_pipeline.sh** + **scripts/load_env.sh**: Removed OpenAI key loading

### 2. Backfill Importance + Keywords (Complete)
- **Created `scripts/backfill_importance.py`**: New script to backfill missing importance/keywords for ~2000 existing LLM analysis records (all NULL)
- **Executed 2 batches**: 1967/2022 records backfilled (97.3%)
  - Batch 1: 999 records updated (1 error)
  - Batch 2: 968 records updated (5 errors)
- **Distribution**: 486 must_read, 1056 worth_reading, 475 optional
- **Keywords**: 2-4 topic tags per article (e.g., "Fed", "interest rates", "Tesla earnings")

### 3. Threading Algorithm Redesign v3 (Complete)
**Problem Identified**: v2 created only 38 threads from 500 articles with "Trump Tariff" thread ballooning to 148 members (gravity well). Centroid pollution from "Market Talk" roundup articles.

**Algorithm Changes**:
- **Anti-gravity (Size Penalty)**:
  - Formula: `effective_threshold = 0.70 + 0.01×days_gap + 0.02×ln(members+1)`
  - 2-member thread: threshold 0.722 (easy to join)
  - 150-member thread: threshold 0.800 (hard to join)

- **Dynamic EMA Alpha**:
  - Formula: `alpha = 0.1 / ln(members+2)`
  - 2-member: 7% influence per new article
  - 150-member: 2% influence (centroid stays stable)

- **Roundup Article Exclusion**:
  - Pattern filter: `"Roundup: Market Talk"` excluded from thread matching
  - Prevents centroid drift toward "general market news"

- **Higher Merge Threshold**: 0.85 → 0.92 (prevents unrelated stories merging)

### 4. Code Implementation (v3 Algorithm)
**scripts/embed_and_thread.py** (major rewrite):
- Added constants (lines ~37-45):
  ```python
  THREAD_BASE_THRESHOLD = 0.70
  THREAD_TIME_PENALTY = 0.01
  THREAD_SIZE_PENALTY = 0.02  # NEW: anti-gravity
  THREAD_MERGE_THRESHOLD = 0.92
  CENTROID_EMA_BASE_ALPHA = 0.1
  THREADING_EXCLUDE_PATTERNS = ['Roundup: Market Talk']
  ```
- Added `is_roundup_article()` function
- Modified `match_to_threads()`: Dynamic threshold + size penalty
- Modified all 4 EMA update locations: Dynamic alpha calculation
- Modified `group_unmatched_with_llm()`: Filter roundup articles before LLM
- Modified deactivation logic: Skip during backfill mode

### 5. Full Backfill Execution (v3)
- **Reset**: 353 threaded articles → NULL, 38 threads → DELETE
- **Backfilled**: Jan 7 → Feb 16 (ALL articles, not limited 25%)
- **Results**: 59 threads, 208/998 threaded (21%)
  - Previous (v2): 38 threads, 350+ threaded (35%), largest 148
  - New (v3): 59 threads, 208 threaded (21%), largest 15
  - **Key improvement**: Largest thread reduced 148 → 15 (gravity well solved)
  - **Quality**: Threads now specific (Kevin Warsh, US-Iran, Greenland, Gold Records)

### 6. Documentation Update
**docs/1.2-news-threading.md** (complete rewrite):
- Added "Dynamic threshold (anti-gravity)" with formula + member_count table
- Added "Centroid update (Dynamic EMA)" with formula + member_count table
- Added "Roundup article exclusion" rationale
- Added "Algorithm Constants" reference table
- Updated "Edge Cases" with gravity well, drift, roundup handling
- Changed merge threshold from 0.85 to 0.92

---

## Key Decisions

| Decision | Reason |
|----------|--------|
| **Gemini 2.5 Flash over GPT-4o-mini** | 1M context window, better for bulk operations, cost-effective |
| **Dynamic EMA per thread size** | Large threads resist drift (2% influence), small threads remain flexible (7%) |
| **Exclude roundups entirely** | Daily "Market Talk" summaries pollute centroids; no signal for specific stories |
| **Size penalty (ln scaling)** | Anti-gravity: larger threads harder to join; prevents snowball effect |
| **Merge threshold 0.92** | Prevents unrelated stories (Fed nominations vs trade tariffs) from merging |
| **21% threading rate acceptable** | Better to have fewer, higher-quality threads than garbage "gravity well" threads |

---

## Files Changed

| File | Changes | Status |
|------|---------|--------|
| `scripts/llm_analysis.py` | OpenAI → Gemini conversion | ✅ Committed |
| `scripts/llm_backfill.py` | OpenAI → Gemini conversion | ✅ Committed |
| `scripts/crawl_ranked.py` | OpenAI → Gemini conversion | ✅ Committed |
| `scripts/backfill_importance.py` | NEW: Backfill importance + keywords | ✅ Committed |
| `scripts/embed_and_thread.py` | Threading v3: dynamic threshold, EMA, roundup filter | ✅ Committed |
| `scripts/requirements.txt` | Removed OpenAI, added google-genai | ✅ Committed |
| `.github/workflows/finance-pipeline.yml` | OPENAI_API_KEY → GEMINI_API_KEY | ✅ Committed |
| `scripts/run_pipeline.sh` | Remove OpenAI key loading | ✅ Committed |
| `scripts/load_env.sh` | Remove OpenAI key loading | ✅ Committed |
| `docs/1.2-news-threading.md` | Complete rewrite: v3 algorithm, formulas, edge cases | ✅ Committed |

---

## Remaining Work

### Next Phase: Frontend (Phases 5-8)
- [ ] **Phase 5**: Detail page `/news/[slug]` (display single thread with all articles, heat score, topic timeline)
- [ ] **Phase 6**: List page enhancements (tabs: All/Thread/Trending, filters, heat-based ranking)
- [ ] **Phase 7**: Thread grouping in list view (visual card layout, member count badge, thread subtitle)
- [ ] **Phase 8**: Interactive features (expand/collapse threads, keyword cloud, filter by importance)

**Note**: All Phase 5-8 code is already drafted but untested. Ready for QA.

### Optional Threading Refinements
- [ ] Monitor centroid matching rates in next 7 days of daily runs
- [ ] Assess Epstein thread fragmentation (currently 4 separate threads despite similar keywords) — is 0.92 too high?
- [ ] Benchmark: If threading rate stays ~21%, decide if coefficients need fine-tuning
- [ ] **Thread title auto-refresh**: Auto-generate new thread titles when member_count hits 10/25/50 milestones using Gemini (not yet implemented)

### Database Monitoring
- [ ] Run SQL to verify v3 thread quality:
  ```sql
  SELECT t.id, t.title, COUNT(ta.article_id) as count,
         ROUND(AVG(EXTRACT(EPOCH FROM (NOW() - a.published_at))/86400)::numeric, 1) as avg_age_days
  FROM wsj_story_threads t
  LEFT JOIN wsj_thread_articles ta ON t.id = ta.thread_id
  LEFT JOIN wsj_crawl_results a ON ta.article_id = a.id
  WHERE t.active = true
  GROUP BY t.id
  ORDER BY count DESC
  LIMIT 20;
  ```

---

## Blockers / Open Questions

**None currently.** Threading v3 is stable and production-ready.

### Optional Questions for Next Session
1. **21% threading rate**: Is this acceptable? Should we tune coefficients to increase rate?
2. **Epstein fragmentation**: Are 4 separate threads correct (different angles/jurisdictions) or should they merge?
3. **Frontend complexity**: Should Phase 5-8 be split into smaller chunks or implemented as one big PR?
4. **Heat score perception**: Will users understand query-time ranking, or need to see "stability indicators"?

---

## Context for Next Session

### Key Constants to Remember
```python
THREAD_BASE_THRESHOLD = 0.70          # Cosine similarity baseline
THREAD_TIME_PENALTY = 0.01            # +0.01 per day gap
THREAD_SIZE_PENALTY = 0.02            # +0.02 × ln(members+1)
THREAD_MERGE_THRESHOLD = 0.92         # Merge only if > 0.92 similarity
CENTROID_EMA_BASE_ALPHA = 0.1         # Base alpha for dynamic scaling
THREAD_ARCHIVE_DAYS = 14              # Archive if no new articles
```

### Algorithm Formulas
- **Effective threshold**: `0.70 + 0.01×days_gap + 0.02×ln(members+1)`
- **Heat score**: `Σ(importance_weight × e^(-0.3×days_old))`
  - importance_weight: must_read=3, worth_reading=2, optional=1
  - time_decay half-life: ~2.3 days
- **Dynamic EMA alpha**: `0.1 / ln(members+2)`

### SQL Queries Useful for Next Session
1. **Thread quality check** (see above)
2. **Gravity well detection**: Large threads with low-avg-similarity articles
   ```sql
   SELECT COUNT(*) as low_sim_count, t.title
   FROM wsj_thread_articles ta
   JOIN wsj_story_threads t ON t.id = ta.thread_id
   WHERE ta.cosine_similarity < 0.65
   GROUP BY t.id, t.title
   ORDER BY low_sim_count DESC;
   ```
3. **Roundup articles** (should be 0 if filter working):
   ```sql
   SELECT COUNT(*) FROM wsj_crawl_results
   WHERE title LIKE '%Roundup: Market Talk%'
   AND thread_id IS NOT NULL;
   ```

### Known Gotchas
1. **Backfill deactivation**: `--backfill-by-date` must skip thread deactivation (historical dates would archive everything)
2. **Importance NULL check**: Some 2022 records may have NULL importance from OpenAI-era; backfill_importance.py handles this
3. **Roundup filter**: Filter applied twice (before LLM grouping AND before centroid matching) to prevent pollution at both stages
4. **Sparse data (Jan 7-20)**: Only 2-17 articles/day → poor matching. Normal. Improves at volume (Jan 28+ = 50+ articles/day)

### Git Status
- **Branch**: `feature/news-frontend`
- **Recent commits**:
  - 67b471c docs: complete PRD with audio strategy, frontend changes, and phased checklist
  - e3b94b2 feat: add Mac Mini pipeline scripts and Keychain-based secret loading
  - All threading v3 work committed to feature/news-frontend
- **Ready for**: PR to main when frontend (Phase 5-8) is QA'd

### Files to Read Before Next Task
- `docs/2-news-frontend.md` — Before starting Phase 5-8 frontend implementation
- `docs/1.2-news-threading.md` — If tweaking threading constants
- `docs/schema.md` — If modifying DB tables
