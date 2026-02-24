<!-- Created: 2026-02-22 -->
# Audit: 1_wsj_ingest.py

Phase 1 · RSS Ingest — 570 LOC (post-refactor)

---

## Why This Script Exists

WSJ is paywalled. The RSS feeds freely give us headlines + descriptions but not article content. This script builds the **"what to look for" list** — it ingests WSJ headlines into the DB so the rest of the pipeline can find free alternatives on Google News.

Without this script, the pipeline has nothing to search for.

---

## CLI Commands (2)

| Command | Pipeline Phase | What It Does | Why |
|---------|---------------|--------------|-----|
| *(default)* | Phase 1 | Fetch 6 RSS feeds → merge categories → dedup → DB insert | Build the daily headline list |
| `--export [--all] [PATH]` | Phase 1 | Query DB → write JSONL file | Create input file for `3_wsj_to_google_news.py` |

**Moved to `domain_utils.py`**: `--mark-searched`, `--mark-processed`, `--mark-processed-from-db`, `--update-domain-status`, `--retry-low-relevance`, `--stats`, `--seed-blocked-from-json`

---

## Constants & Configuration

### `WSJ_FEEDS` (L46-53) `[KEEP]`

6 Dow Jones RSS feed URLs. These are the only free WSJ data source.

```
WORLD, BUSINESS, MARKETS, TECH, POLITICS, ECONOMY
```

**Why 6?** These cover the categories relevant to a finance briefing. WSJ has other feeds (Opinion, Lifestyle, Arts) but they're either off-topic or have poor crawl success rates.

### `FETCH_DELAY = 0.5` (L56) `[KEEP]`

Half-second between feed fetches. Conservative rate limit — WSJ RSS is public, but hammering 6 endpoints instantly is poor etiquette.

### `CATEGORY_MERGE` (L59) `[KEEP]`

```python
{'BUSINESS': 'BUSINESS_MARKETS', 'MARKETS': 'BUSINESS_MARKETS'}
```

**Why merge?** BUSINESS and MARKETS feeds have ~40% content overlap (same company earnings appear in both). Treating them as one category avoids double-counting in the briefing and gives the dedup algorithm a cleaner signal.

### `SKIP_URL_PATHS` (L62-65) `[KEEP]`

```
/lifestyle/, /real-estate/, /arts/, /health/, /style/,
/livecoverage/, /arts-culture/, /buyside/, /sports/, /opinion/
```

**Why?** These URL paths in WSJ article links indicate categories with very low crawl success rates (content is either non-article or heavily paywalled with no free alternatives). Filtering at parse time saves Google News API quota.

### `URL_CATEGORY_MAP` (L145-155) `[KEEP]`

Maps WSJ URL path segments to normalized feed categories. More accurate than RSS feed_name because WSJ cross-posts articles.

Example: An article at `wsj.com/tech/ai/...` from the BUSINESS feed gets correctly categorized as TECH.

### `AMBIGUOUS_PATHS` (L158) `[KEEP]`

```python
{'articles', 'buyside', 'us-news'}
```

URL paths where we can't determine the category — `/articles/` is the old WSJ URL format with no category info. Falls back to the RSS feed_name.

---

## Data Types

### `WsjItem` (L72-81) `[KEEP]`

In-memory representation of a parsed RSS item. Used between parse → dedup → insert. Not persisted directly — `_build_insert_row()` converts it to a DB dict.

| Field | Source | Notes |
|-------|--------|-------|
| `feed_name` | URL path or RSS feed | Overridden by `extract_category_from_url()` |
| `feed_url` | RSS feed URL | Stored for provenance tracking |
| `title` | `<title>` tag | Used for dedup and Google News search |
| `description` | `<description>` tag | Free snippet — primary input for search queries |
| `link` | `<link>` tag | WSJ article URL (paywalled) |
| `creator` | `<dc:creator>` tag | Author name, nullable |
| `url_hash` | SHA-256(link without query params) | UNIQUE constraint for DB dedup |
| `published_at` | `<pubDate>` tag → ISO string | Used for date filtering in search |
| `subcategory` | URL path segment 2 | e.g., `ai`, `trade`, `cybersecurity` |

### `~~IngestResult~~ (removed)` (L84-96) `[SIMPLIFY]`

Accumulator for ingest statistics. Only used by `cmd_ingest()` for the summary printout. Could be replaced by simple counters, but not worth the churn.

---

## Functions

### RSS Parsing Group

#### `generate_url_hash(url)` (L121) `[KEEP]`

- **In**: URL string
- **Out**: SHA-256 hex digest
- **Why**: DB dedup on `wsj_items.url_hash` UNIQUE constraint. Strips query params because WSJ sometimes appends tracking params to the same article URL.

#### `parse_rss_date(date_str)` (L128) `[KEEP]`

- **In**: RFC 2822 date string (from RSS `<pubDate>`)
- **Out**: ISO 8601 string or None
- **Why**: DB stores `published_at` as TIMESTAMPTZ. RSS dates come in `Mon, 21 Feb 2026 15:30:00 GMT` format.

#### `safe_text(el)` (L139) `[KEEP]`

- **In**: XML element (or None)
- **Out**: Stripped text or empty string
- **Why**: XML elements can be None or have None text. Every RSS field extraction uses this.

#### `extract_category_from_url(link)` (L161) `[KEEP]`

- **In**: WSJ article URL
- **Out**: `(category, subcategory)` tuple
- **Why**: RSS feed_name is unreliable — WSJ cross-posts articles. The URL path (`/tech/ai/slug`) is ~95% accurate for categorization.
- **Logic**: Parse URL → check path[0] against `URL_CATEGORY_MAP` → extract path[1] as subcategory if 3+ segments

#### `parse_wsj_rss(xml_text, feed_name, feed_url)` (L195) `[KEEP]`

- **In**: Raw XML string, feed metadata
- **Out**: List of `WsjItem`
- **Why**: Core parser. Applies 3 skip filters (opinion, roundup, low-value categories), extracts category from URL, and builds WsjItem objects.
- **DB columns written**: None directly — produces WsjItem objects for `insert_wsj_item()`

### HTTP Group

#### `fetch_wsj_feed(client, feed)` (L256) `[KEEP]`

- **In**: httpx.Client, feed dict (`{name, url}`)
- **Out**: `(items, error_message)` tuple
- **Why**: Single feed fetch with error handling. 10-second timeout.

#### `fetch_all_wsj_feeds()` (L271) `[KEEP]`

- **In**: None (reads `WSJ_FEEDS` constant)
- **Out**: `(all_items, errors)` tuple
- **Why**: Orchestrates 6 feed fetches with rate limiting. Uses `httpx.Client` context manager for connection pooling.
- **User-Agent**: `FinanceBriefBot/1.0 (contact@araverus.com)`

### DB Operations Group

#### `_build_insert_row(item, slug)` (L302) `[KEEP]`

- **In**: WsjItem + generated slug
- **Out**: Dict matching `wsj_items` table columns
- **Why**: Extracted to avoid duplicating the 10-field dict in `insert_wsj_item()` (was duplicated for slug collision retry).

#### `insert_wsj_item(supabase, item)` (L318) `[KEEP]`

- **In**: Supabase client, WsjItem
- **Out**: True if inserted, False if duplicate
- **Why**: Single-item insert with slug collision handling.
- **Dedup strategy**: `url_hash` UNIQUE constraint catches exact URL duplicates. If a slug collision occurs (different article, same title), retries with date-suffixed slug via `generate_unique_slug()`.
- **Error detection**: Checks for PostgreSQL error code 23505 (unique violation) in the exception string.

#### `get_unsearched_items(supabase, limit=500)` (L344) `[KEEP]`

- **In**: Supabase client, row limit
- **Out**: List of dicts (DB rows)
- **Why**: Export source for `--export`. Returns items where `searched=false`, ordered by most recent first.
- **Limit 500**: Safety cap. Daily ingest is ~60-80 items, so 500 covers several days of backlog.

### Export Group

#### `export_to_jsonl(items, output_path)` (L366) `[KEEP]`

- **In**: List of DB row dicts, output file path
- **Out**: JSONL file on disk
- **Why**: Creates the handoff file between `1_wsj_ingest.py` (Phase 1) and `3_wsj_to_google_news.py` (Phase 1 cont.)
- **Key rename**: `published_at` → `pubDate` for downstream compatibility

**JSONL Schema** (one line per item):
```json
{
  "id": "uuid",
  "title": "Fed Holds Rates Steady...",
  "description": "The Federal Reserve...",
  "link": "https://www.wsj.com/economy/...",
  "pubDate": "2026-02-21T15:30:00+00:00",
  "feed_name": "ECONOMY",
  "creator": "Nick Timiraos",
  "subcategory": "central-banking",
  "extracted_entities": ["Federal Reserve", "Jerome Powell"],
  "extracted_keywords": ["interest rates", "inflation"],
  "extracted_tickers": [],
  "llm_search_queries": ["Federal Reserve interest rate decision February 2026", ...]
}
```

### Dedup Group

#### `dedup_by_title(items)` (L392) `[KEEP]`

- **In**: List of WsjItem (post-category-merge)
- **Out**: Deduplicated list
- **Why**: WSJ cross-posts the same article to multiple RSS feeds. Without dedup, the same headline would generate duplicate Google News searches.
- **Algorithm**: Exact title match. On collision, keeps the version from the category with fewer items (least-count balancing). This naturally distributes articles across categories for a balanced briefing.

### Command Group

#### `cmd_ingest()` (L417) `[KEEP]`

Pipeline: fetch → merge → dedup → insert. 4 steps logged with progress.

#### `cmd_export(output_path, export_all)` (L490) `[KEEP]`

Two modes:
- **Default**: `searched=false` items only (normal pipeline flow)
- **`--all`**: Last 2 days regardless of searched flag (for re-searching after improvements)

---

## Data Flow

```
WSJ RSS Feeds (6 URLs)
    │
    ▼ fetch_all_wsj_feeds()
[Raw XML × 6]
    │
    ▼ parse_wsj_rss() × 6
[WsjItem list] ──skip──▶ Opinion | Roundup | Low-value paths
    │
    ▼ CATEGORY_MERGE
[WsjItem list with merged BUSINESS_MARKETS]
    │
    ▼ dedup_by_title()
[Unique WsjItem list]
    │
    ▼ insert_wsj_item() × N
[wsj_items DB table]
    │
    ▼ get_unsearched_items() + export_to_jsonl()
[output/wsj_items.jsonl] ──▶ 3_wsj_to_google_news.py
```

---

## DB Dependencies

| Table | Access | Functions |
|-------|--------|-----------|
| `wsj_items` | INSERT | `insert_wsj_item()` |
| `wsj_items` | SELECT | `get_unsearched_items()` |

No other tables touched. Clean single-table responsibility.

---

## Shared Dependencies

| Module | What's Used | Why |
|--------|-------------|-----|
| `utils/slug.py` | `generate_slug()`, `generate_unique_slug()` | URL-friendly slugs for `/news/[slug]` routes |
| `httpx` | HTTP client | RSS feed fetching |
| `supabase` | DB client | Insert + query |

---

## Refactoring Notes

### Done (this session)
- Moved `--mark-searched`, `--stats` + helpers to `domain_utils.py`
- Extracted `SKIP_URL_PATHS`, `CATEGORY_MERGE` to module-level constants
- Moved inline imports to module top (`urlparse`, `time`, `timedelta`)
- Deduplicated insert dict via `_build_insert_row()`
- Added batching to `mark_items_searched()` (now in domain_utils)
- Added `require_supabase_client()` to domain_utils — CLI commands now fail fast with clear error instead of `AttributeError: NoneType`
- Removed `IngestResult` dataclass — replaced with plain variables in `cmd_ingest()`
- Deleted `.github/workflows/finance-pipeline.yml` — unused (pipeline runs on Mac Mini launchd)
- Renamed `get_unprocessed_items()` → `get_unsearched_items()` — matches the actual `searched=false` filter

### Remaining Questions

| Item | Question |
|------|----------|
| `get_supabase_client()` | Still duplicated between `1_wsj_ingest.py` (raises ValueError) and `domain_utils.py` (returns None + `require_supabase_client()` wrapper). Could be unified into a shared `db.py` module, but touches many scripts. |
