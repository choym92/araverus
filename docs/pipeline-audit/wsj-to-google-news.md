<!-- Created: 2026-02-22 -->
# Audit: wsj_to_google_news.py

Phase 1 · Step 3 · Google News Search — 646 LOC (post-refactor)

---

## Why This Script Exists

WSJ articles are paywalled. We need to find **free alternatives** covering the same news event. This script searches Google News for each WSJ headline, builds a candidate pool, and writes it to JSONL for the next stage (embedding ranking).

Without this script, the pipeline has no way to find free articles.

**Cost:** Free (Google News RSS is public). Rate-limited to ~1 req/sec for politeness.

---

## CLI Commands (1)

| Command | Pipeline Phase | What It Does | Why |
|---------|---------------|--------------|-----|
| *(default)* | Phase 1 · Step 3 | Read JSONL → build queries → search Google News → filter → write results | Find free article candidates |

| Flag | Default | Action |
|------|---------|--------|
| `--limit N` | all | Process only N items |
| `--delay-item S` | 2.0 | Delay between WSJ items |
| `--delay-query S` | 1.0 | Delay between Google News queries |
| `--input PATH` | `output/wsj_items.jsonl` | Custom JSONL input file |

**Pipeline call** (`run_pipeline.sh` L55):
```bash
$VENV "$SCRIPTS/wsj_to_google_news.py" --delay-item 0.5 --delay-query 0.3 || echo "WARN: Google News search had errors (continuing)"
```

Non-fatal — if search fails, downstream scripts just have fewer candidates.

---

## Constants & Configuration

### `GOOGLE_NEWS_RSS` (L42) `[KEEP]`

```
https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en
```

Google News RSS search endpoint. Returns XML with up to ~100 results per query (undocumented limit, empirically observed).

### `SOURCE_NAME_TO_DOMAIN` (L45-63) `[KEEP]`

Maps known outlet names to domains for blocklist matching. Safety net when Google News source_url is missing or doesn't match.

```python
'reuters': 'reuters.com', 'bloomberg': 'bloomberg.com', 'ft': 'ft.com', ...
```

**Why?** Google News sometimes returns source_name without source_url. This mapping ensures major paywall outlets are still caught by the blocklist.

### `MAX_SITE_EXCLUSIONS = 28` (L66) `[KEEP]`

Google limits ~32 search operators per query. Reserve 4 for date/other operators, use up to 28 for `-site:` exclusions.

### `_search_hit_counter` (L71) `[KEEP]`

Module-level dict tracking how often each domain appears in Google News results per pipeline run. Flushed to `wsj_domain_status.search_hit_count` at end of run. Used to prioritize which domains get `-site:` exclusion slots.

---

## Functions

### Utility Group

#### `is_non_english_source(source_name)` (L74) `[KEEP]`

- **In**: Source name string
- **Out**: True if contains non-Latin characters (ord > 687)
- **Why**: Non-English sources (Arabic, Chinese, Korean, etc.) aren't useful for an English briefing. Filtered at post-search time.

#### `safe_text(el)` (L89) `[KEEP]`

- **In**: XML element (or None)
- **Out**: Stripped text or empty string
- **Why**: Same pattern as wsj_ingest.py. Used in Google News RSS XML parsing.

#### `normalize_domain(url)` (L94) `[KEEP]`

- **In**: URL string
- **Out**: Domain without www. prefix
- **Why**: Consistent domain keys for blocklist matching and hit counting.

#### `dedupe_key(article)` (L103) `[KEEP]`

- **In**: Article dict (title, source)
- **Out**: MD5 hex digest
- **Why**: Same title + same source = duplicate. Same news from different sources = kept (intentional — more crawl options).

### Domain Blocking Group

#### `load_blocked_domains()` (L109) `[KEEP]`

- Wrapper around `domain_utils.load_blocked_domains()` with `@lru_cache`
- Loaded once per run, cached as frozenset

#### `_is_domain_blocked(domain, blocked_domains)` (L117) `[KEEP]`

- Subdomain-aware matching: `ca.finance.yahoo.com` matches `yahoo.com`
- Walks up domain hierarchy checking each parent

#### `is_source_blocked(source_name, source_domain)` (L137) `[KEEP]`

Three checks:
1. `is_non_english_source()` — non-Latin characters
2. `_is_domain_blocked(source_domain)` — direct domain check
3. `SOURCE_NAME_TO_DOMAIN` lookup — name-to-domain fallback

### Query Building Group

#### `is_newsletter_title(title)` (L162) `[KEEP]`

- Detects roundup/newsletter titles that won't search well on Google News
- Patterns: "Plus,...", "5 Things to Know", "What to expect", etc.
- When detected AND LLM queries are available, bypasses title-based search entirely

#### `build_queries(title, description, llm_queries)` (L175) `[KEEP]`

Core query generation:
```
Q1: Clean title (strip "- WSJ" branding)
Q2-Q4: llm_search_queries[0:3] (from wsj_preprocess.py)
```

If no LLM queries, only Q1 is used (clean title).
Newsletters with LLM queries skip Q1 entirely (newsletter titles are unsearchable).
Max 4 queries total.

#### `parse_rss_date(date_str)` (L207) `[KEEP]`

- Parses RFC 2822 (Google News RSS) or ISO 8601 (JSONL) dates
- Used for date filtering in `add_date_filter()`

#### `add_date_filter(query, after_date)` (L324) `[KEEP]`

- Adds `after:YYYY-MM-DD before:YYYY-MM-DD` to query
- 3-day window: pubDate -1 day → pubDate +1 day
- Fallback: `when:3d` if no pubDate available

### Search Group

#### `search_google_news(query, client)` (L289) `[KEEP]`

- **In**: Formatted query string, httpx.AsyncClient
- **Out**: List of article dicts (title, link, source, source_domain, pubDate)
- **Why**: Core HTTP call. Parses Google News RSS XML response.
- **Timeout**: 10 seconds

#### `_dedupe_subdomains(domains)` (L343) `[KEEP]`

- Removes subdomains when parent domain is in the set
- `finance.yahoo.com` removed if `yahoo.com` exists (Google's `-site:yahoo.com` covers subdomains)
- Maximizes unique domains in the 28-slot `-site:` budget

#### `format_query_with_exclusions(query)` (L451) `[KEEP]`

- Adds `-site:` operators for top blocked domains, sorted by `search_hit_count DESC`
- Dedupes subdomains, caps at `MAX_SITE_EXCLUSIONS` (28)
- Full blocked list still applies post-search via `is_source_blocked()`

#### `search_multi_query(queries, client, after_date, delay_query)` (L468) `[KEEP]`

Orchestrator for multi-query search:
1. For each query: add exclusions → add date filter → search Google News
2. Track domain hits in `_search_hit_counter` (before blocking)
3. Filter: `is_source_blocked()` → dedupe → add to results
4. Rate limit: `delay_query` seconds between queries

### Search Hit Tracking Group

#### `save_search_hit_counts()` (L365) `[KEEP]`

- Flushes `_search_hit_counter` to `wsj_domain_status.search_hit_count` in DB
- Increments DB values (additive across runs)
- Only updates domains that already exist in the table

#### `_load_blocked_with_hits()` (L404) `[KEEP]`

- Loads blocked domains with their `search_hit_count` from DB
- Used by `format_query_with_exclusions()` for prioritization
- `@lru_cache`: loaded once per run

### Main Group

#### `main()` (L497) `[KEEP]`

Pipeline: load JSONL → for each item: build queries → search → filter → collect results → save 4 output files + flush hit counts.

---

## Output Files

| File | Purpose | Downstream |
|------|---------|------------|
| `wsj_google_news_results.jsonl` | Main output — candidates per WSJ item | `embedding_rank.py` |
| `wsj_google_news_results.txt` | Human-readable debug view | Manual inspection |
| `wsj_instrumentation.jsonl` | Per-query metrics (results, time, added) | Debugging |
| `wsj_searched_ids.json` | WSJ item IDs to mark as `searched=true` | `domain_utils.py --mark-searched` |

---

## Domain Blocking — Three Layers

```
Layer 1: -site: exclusion (search-time, top 28 domains)
  → Google doesn't return these. Slots freed for useful results.

Layer 2: is_source_blocked() (post-search, ALL blocked domains)
  → Python drops remaining blocked results after Google returns them.

Layer 3: crawl_ranked.py (crawl-time)
  → Final safety net before crawling.
```

Layer 1 is most valuable (prevents slot waste). Sorted by `search_hit_count` to maximize impact.

---

## Data Flow

```
wsj_items.jsonl (from wsj_ingest.py --export)
    │
    ▼ load_wsj_jsonl() — dedup by title
[WSJ items list]
    │
    ▼ for each item:
    │   build_queries() → 1-4 queries
    │   │
    │   ▼ for each query:
    │   │   format_query_with_exclusions() → add -site:
    │   │   add_date_filter() → add after:/before:
    │   │   search_google_news() → HTTP GET
    │   │   │
    │   │   ▼ for each result:
    │   │       _search_hit_counter[domain] += 1
    │   │       is_source_blocked() → drop blocked
    │   │       dedupe_key() → drop duplicates
    │   │
    │   ▼ collected articles for this item
    │
    ▼ save outputs
[wsj_google_news_results.jsonl]  → embedding_rank.py
[wsj_searched_ids.json]          → domain_utils.py --mark-searched
[wsj_domain_status]              ← save_search_hit_counts()
```

---

## DB Dependencies

| Table | Access | Functions |
|-------|--------|-----------|
| `wsj_domain_status` | SELECT | `load_blocked_domains()`, `_load_blocked_with_hits()` |
| `wsj_domain_status` | UPDATE | `save_search_hit_counts()` |

Does NOT read/write `wsj_items` directly — communicates via JSONL files.

---

## Shared Dependencies

| Module | What's Used | Why |
|--------|-------------|-----|
| `domain_utils.py` | `load_blocked_domains()`, `get_supabase_client()` | DB blocked domains, hit count save |
| `httpx` | AsyncClient | Google News HTTP calls |

---

## Refactoring Notes

### Done (this session)
- Removed `parse_wsj_rss()` + `--xml` flag (36 LOC dead code — pipeline uses JSONL only)
- Replaced manual `sys.argv` parsing with `argparse` (cleaner, consistent)
- Removed `EXCLUDED_SOURCES` (redundant — `is_non_english_source()` already catches CJK)
- Removed `today_only` parameter from `load_wsj_jsonl()` (never used)
- Removed `_load_blocked_with_hits()` column-missing fallback (`search_hit_count` exists)
- Removed `save_search_hit_counts()` column-missing fallback
- Fixed `processed_ids` → `searched_ids` naming (these are searched, not processed)
- Fixed incorrect CLI hint: `--mark-processed` → `--mark-searched`
- Updated docstring to remove XML references
- Added Step number to Phase docstring (Phase 1 · Step 3)

### Not Changed
| Pattern | Why Kept |
|---------|----------|
| `sys.path.insert(0, ...)` | Pipeline-wide pattern (9 scripts) |
| `from google.genai import types` inline | Pipeline-wide pattern (7 scripts) |
| `save_search_hit_counts()` N+1 queries | ~100 domains, runs once per pipeline. Low priority optimization. |
| `SOURCE_NAME_TO_DOMAIN` hardcoded | Safety net — only 7 entries, rarely changes |
| Dedup in `load_wsj_jsonl()` | Safety net for `--export --all` which may include cross-run duplicates |

### Remaining Questions

| Item | Question |
|------|----------|
| `save_search_hit_counts()` efficiency | SELECT+UPDATE per domain. Could use Supabase RPC for bulk increment. Not urgent at ~100 domains. |
| `docs/1.1-news-google-search.md` | Updated with correct -site: count (28, sorted by search_hit_count). `google-news-search-flow.md` merged in. |
