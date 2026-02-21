<!-- Updated: 2026-02-21 -->
# Google News Search — How It Works

## Overview

WSJ title+description → search queries → Google News RSS → filter → candidates for embedding ranking

```
wsj_items.jsonl ──→ wsj_to_google_news.py ──→ wsj_google_news_results.jsonl
                         │
                         ├── build_queries()         → 4 queries per item
                         ├── format_query_with_exclusions()  → add -site: exclusions
                         ├── add_date_filter()        → add after:/before: dates
                         ├── search_google_news()     → HTTP GET to Google News RSS
                         └── add_article()            → dedup + blocked domain + date check
```

---

## Step 1: Query Generation (`build_queries`)

**Input:** WSJ title, description, `llm_search_queries` (from Gemini preprocessing)

**Output:** Up to 4 queries

```
Q1: Clean title (remove "- WSJ" branding)
Q2: llm_search_queries[0]  (Gemini-generated)
Q3: llm_search_queries[1]
Q4: llm_search_queries[2]
```

If `llm_search_queries` is empty (not preprocessed), only Q1 is used.

---

## Step 2: Query Formatting

Each query goes through two transformations:

### 2a. Site Exclusions (`format_query_with_exclusions`)

Adds `-site:` for top paywalled domains to prevent them from using up Google's 100-result slots:

```
"US GDP growth" → "US GDP growth -site:wsj.com -site:reuters.com -site:bloomberg.com -site:ft.com -site:nytimes.com -site:barrons.com"
```

**Why only 6 domains?** Google has a query length limit. We exclude the 6 highest-traffic paywall sites here. The remaining 60+ blocked domains are filtered post-fetch (Step 4).

### 2b. Date Filter (`add_date_filter`)

Adds `after:` / `before:` date operators (±1 day from WSJ pubDate):

```
"US GDP growth -site:wsj.com ..." → "US GDP growth -site:wsj.com ... after:2026-02-19 before:2026-02-22"
```

**Window: 3 days** (pubDate minus 1 day → pubDate plus 1 day)

---

## Step 3: Google News RSS Call

```
GET https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en
```

- Returns XML (RSS format)
- **Hard limit: ~100 results per query** (undocumented, observed)
- Each result has: `title`, `link` (Google redirect URL), `source` (outlet name), `source url` (outlet domain), `pubDate`
- Response time: typically 0.01-0.7 seconds

**Delay between queries:** 1 second (rate limit safety)

---

## Step 4: Post-Fetch Filtering (`add_article`)

Every result goes through 3 checks before being added:

### 4a. Source Blocking (`is_source_blocked`)

```python
is_source_blocked(source_name, source_domain)
```

Checks against:
1. **Non-English filter** — Source name contains non-Latin characters (Arabic, Chinese, Korean, etc.)
2. **blocked_domains DB** — `wsj_domain_status` table where `status = 'blocked'` (~60 domains)

All blocked domains managed in DB only — no hardcoded lists.

### 4b. Deduplication (`dedupe_key`)

```python
MD5(f"{title}|{source}".lower())
```

- Same title + same source = duplicate → skip
- Same news, different source = kept (intentional — we want multiple domain options to crawl)

---

## Domain Blocking — Full Picture

### Where blocked domains come from

All blocked domains managed in `wsj_domain_status` table (DB-only, no hardcoded lists):

```
wsj_domain_status table (Supabase, ~60 blocked)
├── JSON migration (manual seeds)
│   └── Paywall: wsj.com, reuters.com, bloomberg.com, ft.com, nytimes.com, barrons.com
│   └── Social/video: facebook, instagram, tiktok, twitter, x, youtube, linkedin, threads
│   └── Aggregator: msn.com, news.google.com
│
└── Auto-blocked (wilson score < 0.15, n >= 5)
    └── Only "blockable" failures count (low_relevance / llm_rejected excluded)
    └── e.g., finance.yahoo.com, morningstar.com
```

### Where blocking is applied

| Stage | What happens | Domains excluded |
|-------|-------------|-----------------|
| **Query time** (`-site:`) | Google doesn't return these | 6 top paywall sites |
| **Post-fetch** (`is_source_blocked`) | Python drops these from results | All ~60 blocked domains |

### The DB table: `wsj_domain_status`

Columns: `domain`, `status`, `fail_count`, `fail_counts` (JSONB per-reason), `success_count`, `wilson_score`, `block_reason`, etc.

Auto-blocking triggers when `wilson_score < 0.15` (blockable failures only, n >= 5).

---

## Output Files

```
scripts/output/
├── wsj_google_news_results.jsonl   → Input for embedding_rank.py
│   Each line: { wsj: {...}, queries: [...], google_news: [{title, link, source, source_domain, pubDate}, ...] }
│
├── wsj_google_news_results.txt     → Human-readable debug view
├── wsj_instrumentation.jsonl       → Per-query performance (results count, added count, time)
└── wsj_processed_ids.json          → WSJ item IDs to mark as searched=true in DB
```

---

## Known Constraints

1. **100-result hard limit per query** — Google News RSS caps at ~100. Mitigated by using 4 different queries.
2. **Query length limit** — Can't add all 67 `-site:` exclusions. Only top 6 paywall sites excluded at query time.
3. **No pagination** — Google News RSS doesn't support `start=` or `num=` parameters.
4. **Rate limiting** — 1-second delay between queries, 2-second delay between items.

---

## Recent Changes (2026-02-21)

| Change | Before | After |
|--------|--------|-------|
| Date window | Q1-Q2: 7 days, Q3-Q4: 5 days | **All queries: 3 days (±1 day)** |
| `-site:` exclusions | wsj.com only | **wsj + reuters + bloomberg + ft + nytimes + barrons** |
| `load_wsj_jsonl` | Hardcoded 9-field dict reconstruction | **Pass-through (all JSONL fields preserved)** |
| Domain blocking | Hardcoded list + DB | **DB-only** (`wsj_domain_status`) |
| Source filtering | `EXCLUDED_SOURCES` + `SOURCE_NAME_TO_DOMAIN` | **Removed** (DB handles all) |
| Post-fetch date check | Python-side re-validation | **Removed** (Google `after:/before:` sufficient) |
| `embedding_rank.py` top_k | 5 | **10** |
| `crawl_ranked.py` errors | Raw strings | **Normalized** (`normalize_crawl_error()`) |
| `wsj_ingest.py` domain status | Simple fail_count | **fail_counts JSONB** + blockable failure filtering |

---

## A/B Test Results (2026-02-21)

**OLD** = main branch cron (regex title-only queries, MiniLM, 7-day window, wsj.com-only exclusion)
**NEW** = feature branch (LLM queries, bge-base, 3-day window, 6-site exclusion)

All embedding scores use **bge-base** for fair comparison (OLD re-ranked with bge-base).

### Aggregate Metrics (19 WSJ items)

| Metric | OLD | NEW | Δ |
|--------|-----|-----|---|
| Raw search candidates | 71 | **3,894** | 54x |
| Ranked candidates (bge >= 0.3) | 71 | **190** | +119 |
| Items with 0 candidates | 1 | **0** | -1 |
| Avg ranked/item | 3.9 | **10.0** | +6.1 |
| Unique domains | 62 | **138** | +76 |

### Embedding Score Distribution (bge-base)

| Metric | OLD | NEW | Δ |
|--------|-----|-----|---|
| min | 0.471 | 0.466 | -0.004 |
| **avg** | 0.676 | **0.718** | **+0.041** |
| max | 0.855 | **0.900** | +0.045 |
| P25 | 0.620 | **0.658** | +0.038 |
| **P50** | 0.678 | **0.729** | **+0.051** |
| P75 | 0.747 | **0.777** | +0.030 |
| P90 | 0.801 | **0.831** | +0.030 |

### Quality Thresholds

| Threshold | OLD | NEW | Δ |
|-----------|-----|-----|---|
| bge >= 0.7 | 30 | **116** | +86 (3.9x) |
| bge >= 0.5 | 69 | **186** | +117 (2.7x) |

### Per-Item Results

- **14 improvements**, 2 regressions, 3 same
- Biggest wins: "Billionaire Women" (+0.425), "Lloyd Blankfein" (+0.666, was 0), "Casey Wasserman" (+0.236)
- Regressions: "Trump trade agenda" (-0.027), "Trump White House meeting" (-0.066) — minor

### Key Takeaway

LLM-generated queries + tighter date window + broader site exclusions = **more candidates, higher quality matches, fewer zero-result items**. The 3-day window doesn't hurt coverage because LLM queries are more targeted.
