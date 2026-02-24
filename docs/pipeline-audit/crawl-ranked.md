<!-- Created: 2026-02-22 -->
# Audit: crawl_ranked.py

Phase 3 · Step 1 · Crawl — ~660 LOC (post-refactor, was ~699)

---

## Why This Script Exists

Resolved URLs are worthless without actual article content. This script crawls each URL, runs quality checks (garbage detection → embedding relevance → LLM verification), and saves results to DB. WSJ items need only 1 good article — if the first candidate fails, it tries the next.

**Cost:** Free (local crawling + local model). Runtime: ~5-15 min depending on articles and delay.

---

## CLI Commands (1)

| Command | Pipeline Phase | What It Does |
|---------|---------------|--------------|
| *(default)* | Phase 3 · Step 1 | Load ranked results → crawl → quality check → save |

| Flag | Default | Action |
|------|---------|--------|
| `--delay N` | 1.5 | Delay between requests (seconds) |
| `--from-db` | false | Load pending items from DB (implies --update-db) |
| `--update-db` | false | Save results to `wsj_crawl_results` |
| `--concurrent N` | 1 | Max concurrent WSJ items |

**Pipeline call** (`run_pipeline.sh` L67):
```bash
$VENV "$SCRIPTS/crawl_ranked.py" --delay 1 --update-db || echo "WARN: Crawl had errors (continuing)"
```

Non-fatal (WARN) — pipeline continues if crawling has errors.

---

## Key Design: 3-Gate Quality Check

Each crawled article passes through 3 sequential gates:

```
crawl_article(url) → markdown content
    │
    ├── Gate 1: is_garbage_content()
    │   Check: paywall, CSS/JS, repeated words, empty, copyright
    │   Fail: crawl_status='garbage', try next candidate
    │
    ├── Gate 2: compute_relevance_score()
    │   Check: cosine similarity(WSJ title+desc, crawled content) >= 0.25
    │   Fail: crawl_status='success', relevance_flag='low', try next
    │
    └── Gate 3: analyze_content() (LLM, if GEMINI_API_KEY set)
        Check: same_event=true OR relevance_score >= 6
        Fail: crawl_status='success', relevance_flag='low', try next
```

If all gates pass → `crawl_status='success'`, `relevance_flag='ok'`, mark other candidates as 'skipped'.

---

## Key Design: Async IS Justified Here

Unlike wsj_to_google_news.py and resolve_ranked.py (which were sequential), this script uses **genuine concurrency**:

- `asyncio.gather(*tasks)` — process multiple WSJ items concurrently
- `asyncio.Semaphore(concurrent)` — control parallelism level
- `domain_rate_limit()` with `asyncio.Lock` — prevent hammering same domain
- `crawl_article()` is async (Playwright-based browser automation)

The `--concurrent` flag controls how many WSJ items are crawled simultaneously.

---

## Functions (8)

### `_get_relevance_model()` (L47) `[SIMPLIFIED]`
Lazy singleton for SentenceTransformer. Previously loaded at module level (3-5sec import cost).

### `compute_relevance_score(wsj_text, crawled_text)` (L56) `[KEEP]`
Cosine similarity between WSJ title+description and first 800 chars of crawled content.

### `is_garbage_content(text)` (L83) `[KEEP]`
Detect unusable content: empty, repeated words, CSS/JS, paywall, copyright/unavailable.

### `get_pending_items_from_db(supabase)` (L149) `[KEEP]`
Query `wsj_crawl_results` for pending items, group by WSJ item.

### `save_crawl_result_to_db(supabase, article, wsj)` (L197) `[KEEP]`
Upsert crawl result on `resolved_url` conflict.

### `mark_other_articles_skipped(supabase, wsj_item_id, success_url)` (L238) `[KEEP]`
After success, mark remaining pending articles for same WSJ item as 'skipped'.

### `domain_rate_limit(domain)` (L37) `[KEEP]`
Per-domain asyncio.Lock + minimum interval. Prevents concurrent items from hitting same domain.

### `process_wsj_item(...)` (L260) `[KEEP]`
Core orchestrator per WSJ item. Tries candidates in weighted-score order through 3-gate check.

---

## Data Flow

```
wsj_ranked_results.jsonl (from resolve_ranked.py)
    │ or wsj_crawl_results table (if --from-db)
    ▼ crawl_article() × N per WSJ item
[3-gate quality check: garbage → relevance → LLM]
    │
    ├── ▼ save_crawl_result_to_db()
    │   wsj_crawl_results table (crawl_status, content, scores)
    │
    └── ▼ write to file (if not --from-db)
        wsj_ranked_results.jsonl (overwritten with crawl results)
```

---

## Shared Dependencies

| Module | What's Used | Why |
|--------|-------------|-----|
| `crawl_article` | `crawl_article()` | Playwright-based HTML→markdown crawler |
| `llm_analysis` | `analyze_content()`, `save_analysis_to_db()`, etc. | Gemini LLM relevance verification |
| `domain_utils` | `load_blocked_domains()`, `get_supabase_client()`, `normalize_crawl_error()` | Domain filtering, DB client, error normalization |
| `sentence_transformers` | `SentenceTransformer` | Embedding relevance check (lazy-loaded) |
| `numpy` | `np.dot` | Cosine similarity |

---

## Refactoring Notes

### Done (this session)
- Module-level `RELEVANCE_MODEL = SentenceTransformer(...)` → lazy `_get_relevance_model()` singleton (`--help` now instant)
- Removed duplicate `get_supabase_client()` → `from domain_utils import get_supabase_client`
- Removed duplicate `CRAWL_ERROR_MAP` + `normalize_crawl_error()` → consolidated to `domain_utils.py` (single source of truth)
- Manual `sys.argv` parsing → `argparse`
- Added Step number (Phase 3 · Step 1)
- Removed module-level `from sentence_transformers import SentenceTransformer`

### Also updated in domain_utils.py (consolidation)
- Renamed `HISTORICAL_ERROR_MAP` → `CRAWL_ERROR_MAP` (clearer name)
- Renamed `normalize_historical_error()` → `normalize_crawl_error()` (consistent with crawl_ranked)
- Added missing entries from crawl_ranked: `"Could not resolve Google News URL": "http error"`
- Added social media detection pattern (was only in crawl_ranked)

### Not Changed
| Pattern | Why Kept |
|---------|----------|
| `asyncio.gather` + `Semaphore` | Genuine concurrency (Playwright crawling) |
| `domain_rate_limit()` with `asyncio.Lock` | Correct pattern for concurrent domain access |
| `IS_CI` / `CRAWL_MODE` | Valid configuration, CI return possible |
| `is_garbage_content()` heuristics | Working well, crawl-specific logic |
| `weighted_score` sorting | Good heuristic (embedding × domain rate) |
| `LLM_ENABLED` module-level check | Cheap env var check, not heavy dep |
