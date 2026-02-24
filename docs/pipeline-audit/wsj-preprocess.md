<!-- Created: 2026-02-22 -->
# Audit: 2_wsj_preprocess.py

Phase 1 · Pre-process — 196 LOC (post-refactor)

---

## Why This Script Exists

WSJ RSS feeds give us headlines + descriptions, but searching Google News with raw titles has low accuracy (~40-50% relevant results). This script uses Gemini Flash-Lite to extract structured metadata (entities, keywords, tickers) and generate optimized search queries **before** the Google News search step.

With LLM-generated queries, search accuracy jumps to ~70-80%. Cost: ~$0.003/day.

Without this script, `3_wsj_to_google_news.py` falls back to the clean title as the only search query — it works, but misses many relevant backup articles.

---

## CLI Commands (1)

| Command | Pipeline Phase | What It Does | Why |
|---------|---------------|--------------|-----|
| *(default)* | Phase 1 | Query DB for unpreprocessed items → Gemini Flash-Lite → save metadata | Generate better search queries before Google News search |

| Flag | Default | Action |
|------|---------|--------|
| `--limit N` | 200 | Max items to process |
| `--dry-run` | — | Print results without DB writes |
| `--backfill` | — | Include already-searched items (reprocess) |

**Pipeline call** (`run_pipeline.sh` L53):
```bash
$VENV "$SCRIPTS/2_wsj_preprocess.py" || echo "WARN: Preprocess had errors (continuing)"
```

Non-fatal — if preprocessing fails, the pipeline continues and `3_wsj_to_google_news.py` uses clean title as fallback.

---

## Constants & Configuration

### `PROMPT_TEMPLATE` (L50-66) `[KEEP]`

Single prompt template for Gemini Flash-Lite. Extracts 4 fields from title + description:

```
entities: company/person/org names (max 5)
keywords: 3-5 search terms capturing the specific event
tickers: stock symbols if identifiable
search_queries: 2-3 optimized Google News queries (5-10 words each)
```

**Rules baked into prompt:**
- Use entity names + key event terms
- Vary phrasing across queries
- Do NOT include source names (WSJ, Bloomberg)
- Do NOT add date filters (added later by `3_wsj_to_google_news.py`)

**Why JSON mode?** `response_mime_type="application/json"` forces Gemini to return valid JSON, avoiding regex/parsing hacks.

---

## Data Types

### `PreprocessResult` (L37-43) `[KEEP]`

```python
@dataclass
class PreprocessResult:
    entities: list[str]
    keywords: list[str]
    tickers: list[str]
    search_queries: list[str]
```

In-memory container for LLM output. Used between `preprocess_item()` → `save_preprocess_result()`.

Refactored from `__slots__` class to `@dataclass` — simpler, same functionality. Memory optimization was pointless for 60-80 items/day.

---

## Functions

### LLM Group

#### `preprocess_item(title, description)` (L69) `[KEEP]`

- **In**: WSJ title string, description string
- **Out**: `PreprocessResult` or None (on error)
- **Why**: Core function. Calls Gemini Flash-Lite with JSON mode, parses response, truncates arrays to safe maximums.
- **Model**: `gemini-2.5-flash-lite` (temperature 0.1, max 512 tokens)
- **Safety caps**: entities[:5], keywords[:5], tickers[:5], search_queries[:3]
- **Error handling**: Returns None on JSON parse error or API error (logged as WARN)
- **External caller**: `ab_test_pipeline.py` imports this function directly

### DB Operations Group

#### `get_items_to_preprocess(supabase, backfill, limit)` (L111) `[KEEP]`

- **In**: Supabase client, backfill flag, row limit
- **Out**: List of dicts (`id`, `title`, `description`)
- **Why**: Queries items that haven't been preprocessed yet (`preprocessed_at IS NULL`)
- **Default mode**: Only unsearched items (`searched=false`) — processes new items before they enter the search pipeline
- **Backfill mode**: Includes searched items — for reprocessing after prompt improvements
- **Order**: Most recent first (`published_at DESC`)

#### `save_preprocess_result(supabase, item_id, result)` (L128) `[KEEP]`

- **In**: Supabase client, wsj_item UUID, PreprocessResult
- **Out**: None (DB side effect)
- **Why**: Updates `wsj_items` row with extracted metadata + sets `preprocessed_at` timestamp
- **DB columns written**: `extracted_entities`, `extracted_keywords`, `extracted_tickers`, `llm_search_queries`, `preprocessed_at`
- **External caller**: `ab_test_pipeline.py` imports this function directly

### Command Group

#### `main()` (L145) `[KEEP]`

Sequential processing loop: query items → for each item: call Gemini → save result.

- Uses `argparse` (cleaner than 1_wsj_ingest.py's manual parsing)
- Progress output: `[1/60] Fed Holds Rates Steady...`
- Summary: `Done: 58 succeeded, 2 failed out of 60`
- Supabase client via `require_supabase_client()` (fail-fast on missing credentials)

---

## Data Flow

```
wsj_items (DB)
    │
    ▼ get_items_to_preprocess()
[items where preprocessed_at IS NULL]
    │
    ▼ preprocess_item() × N
[PreprocessResult per item]
    │
    ▼ save_preprocess_result() × N
[wsj_items UPDATE: extracted_entities, extracted_keywords,
 extracted_tickers, llm_search_queries, preprocessed_at]
    │
    ▼ (next step: 1_wsj_ingest.py --export)
[JSONL includes llm_search_queries for Google News search]
```

---

## DB Dependencies

| Table | Access | Functions | Columns |
|-------|--------|-----------|---------|
| `wsj_items` | SELECT | `get_items_to_preprocess()` | `id`, `title`, `description`, `preprocessed_at`, `searched` |
| `wsj_items` | UPDATE | `save_preprocess_result()` | `extracted_entities`, `extracted_keywords`, `extracted_tickers`, `llm_search_queries`, `preprocessed_at` |

Single-table responsibility (same as 1_wsj_ingest.py).

---

## Shared Dependencies

| Module | What's Used | Why |
|--------|-------------|-----|
| `domain_utils.py` | `require_supabase_client()` | DB client with fail-fast on missing credentials |
| `llm_analysis.py` | `get_gemini_client()` | Singleton Gemini client (shares API key config) |
| `google.genai` | `types.GenerateContentConfig` | Gemini API config (JSON mode, temperature) |
| `supabase` | `Client` type | Type hints for DB functions |

---

## vs wsj_llm_analysis

Both use Gemini, but at different pipeline stages:

| | 2_wsj_preprocess.py | llm_analysis.py |
|---|---|---|
| **When** | Before search (Phase 1) | After crawl (Phase 3) |
| **Input** | Title + description only | Title + description + crawled content |
| **Model** | gemini-2.5-flash-lite | gemini-2.5-flash |
| **Purpose** | Generate search queries | Verify content relevance |
| **Output to** | `wsj_items` (search metadata) | `wsj_llm_analysis` (content analysis) |
| **Cost** | ~$0.003/day | ~$0.01/day |

---

## Refactoring Notes

### Done (this session)
- Replaced `PreprocessResult` `__slots__` class with `@dataclass` — simpler, same functionality
- Removed duplicate `get_supabase_client()` — now uses `require_supabase_client()` from domain_utils.py
- Removed unused `os` import (was only used by deleted `get_supabase_client`)
- Removed unused `create_client` import from supabase

### Not Changed (pipeline-wide patterns)
| Pattern | Why Kept |
|---------|----------|
| `sys.path.insert(0, ...)` | Used by 9 scripts — changing one breaks consistency |
| `from google.genai import types` (inline) | Used by 7 scripts — lazy import pattern |

### Remaining Questions

| Item | Question |
|------|----------|
| No rate limiting | 60 sequential Gemini API calls with no delay. Works today but could hit 429 errors on large backfills. Low priority — Flash-Lite has generous rate limits. |
| `get_supabase_client()` unification | Now 2 copies remain (1_wsj_ingest.py, domain_utils.py). Pipeline-wide cleanup deferred. |
