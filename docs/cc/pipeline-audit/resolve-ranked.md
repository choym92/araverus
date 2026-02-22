<!-- Created: 2026-02-22 -->
# Audit: resolve_ranked.py + google_news_resolver.py

Phase 2 · Step 2 · URL Resolve — 241 LOC (post-refactor, was 303)

---

## Why This Script Exists

Google News wraps all article URLs in redirect links (`news.google.com/articles/...`). The crawler needs actual article URLs. This script resolves each ranked candidate's Google News URL to the real URL using a 3-strategy resolver.

Without this script, crawl_ranked.py would try to crawl Google's redirect pages instead of actual articles.

**Cost:** Free (HTTP calls to Google). Runtime: ~3 min for 600 articles at 0.5s delay.

---

## CLI Commands (1)

| Command | Pipeline Phase | What It Does |
|---------|---------------|--------------|
| *(default)* | Phase 2 · Step 2 | Read ranked JSONL → resolve URLs → write back + optionally save to DB |

| Flag | Default | Action |
|------|---------|--------|
| `--delay N` | 3.0 | Delay between HTTP requests (seconds) |
| `--update-db` | false | Save results to `wsj_crawl_results` table |

**Pipeline call** (`run_pipeline.sh` L61):
```bash
$VENV "$SCRIPTS/resolve_ranked.py" --delay 0.5 --update-db || { echo "ERROR: Resolve failed"; exit 1; }
```

Fatal — if resolution fails, pipeline stops (can't crawl without URLs).

---

## Functions (3 in resolve_ranked.py)

### `atomic_write_jsonl(path, data)` (L33) `[KEEP]`

Writes JSONL atomically using tempfile + `os.replace()`. Prevents partial writes if script crashes mid-write. Important because input file is overwritten in-place with resolved URLs.

### `update_supabase(all_data)` (L50) `[SIMPLIFIED]`

Saves results to `wsj_crawl_results` table:
- `resolve_status == 'success'` → `crawl_status = 'pending'` (ready for crawling)
- `resolve_status in ('failed', 'skipped')` → `crawl_status = 'resolve_failed'` (tracked for domain blocking)

Uses insert-only with duplicate skip (23505 / 'duplicate' string match).

**Refactored:** Now uses `domain_utils.get_supabase_client()` instead of manually reading env vars and creating its own client.

### `main()` (L119) `[SIMPLIFIED]`

Orchestrator: load ranked JSONL → iterate articles → resolve each URL → track stats → write back → optional DB save.

**Refactored:** async → sync, argparse, `time.sleep()` instead of `asyncio.sleep()`.

---

## google_news_resolver.py — Dependency Module (~480 LOC post-refactor)

The resolver module implements the 3-strategy resolution:

### Strategy 1: Direct Base64 Decode (`decode_google_news_url`)
- Works for old Google News URL format
- No HTTP calls needed — pure string manipulation
- Extracts URL from base64-encoded article ID

### Strategy 2: Batchexecute API (`fetch_decoded_batch_execute`)
- Works for new `AU_yqL` format
- 2 HTTP calls: (1) fetch article page → extract sig/timestamp, (2) POST to batchexecute API
- Google's internal API for resolving article URLs

### Strategy 3: HTML Canonical Fallback (`fetch_canonical_from_html`)
- Last resort: GET the Google News page, follow redirects
- Extract `<link rel="canonical">` or `<meta property="og:url">`
- Works when other strategies fail

### Resolution Flow
```
URL → is_google_news_url?
  No  → PASSTHROUGH (return as-is)
  Yes → try decode (old format)
    Success → return decoded URL
    Fail    → needs_batch_execute?
      Yes → try batchexecute API
        Success → return resolved URL
        Fail    → try canonical fallback
      No  → try canonical fallback
        Success → return canonical URL
        Fail    → ALL_STRATEGIES_FAILED
```

### Structured Results
Every resolution returns a `ResolveResult` dataclass with:
- `success`, `resolved_url`, `reason_code` (enum), `strategy_used` (enum)
- `http_status`, `elapsed_ms`, `error_detail`

17 reason codes track exactly why each resolution succeeded or failed.

---

## Data Flow

```
wsj_ranked_results.jsonl (from embedding_rank.py)
    │ ~600 articles (10 per WSJ item × 60 items)
    ▼ resolve_google_news_url() × N
[adds resolved_url, resolve_status, resolve_domain, strategy fields]
    │
    ├── ▼ atomic_write_jsonl()
    │   wsj_ranked_results.jsonl (overwritten in-place)
    │
    └── ▼ update_supabase() (if --update-db)
        wsj_crawl_results table (crawl_status='pending' or 'resolve_failed')
```

---

## Shared Dependencies

| Module | What's Used | Why |
|--------|-------------|-----|
| `google_news_resolver` | `resolve_google_news_url`, `extract_domain`, `ResolveResult`, `ReasonCode` | URL resolution logic |
| `domain_utils` | `get_supabase_client()` | Supabase client (optional, returns None if no creds) |
| `httpx` | `httpx.Client` | HTTP client for Google News API calls |

---

## Refactoring Notes

### Done (this session)

**resolve_ranked.py:**
- **Removed async/await** — all HTTP calls sequential with delay, zero concurrency
- `httpx.AsyncClient` → `httpx.Client`, `asyncio.sleep()` → `time.sleep()`
- Removed `import asyncio`, `asyncio.run(main())`
- Manual `sys.argv` parsing → `argparse`
- Own Supabase client creation → `domain_utils.get_supabase_client()`
- Added Step number (Phase 2 · Step 2)

**google_news_resolver.py:**
- Removed all `async def` → `def` (3 functions)
- `await client.get/post` → `client.get/post`
- `httpx.AsyncClient` type hints → `httpx.Client`
- Removed dead `resolve_google_news_url_legacy()` (zero callers)
- Moved `import json` from function-level to module-level
- **303 → 241 LOC** (resolve_ranked.py), **501 → 489 LOC** (google_news_resolver.py)

### Not Changed
| Pattern | Why Kept |
|---------|----------|
| `sys.path.insert(0, ...)` | Pipeline-wide pattern (9 scripts) |
| N+1 Supabase inserts | Working pattern, optimization is separate concern |
| Duplicate key error string matching | Intentional skip-on-duplicate design |
| `atomic_write_jsonl` | Well-implemented, important safety pattern |
| 3-strategy resolution approach | Core design, well-structured |
