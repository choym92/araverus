<!-- Updated: 2026-02-06 -->
# Finance TTS Briefing Pipeline

Single source of truth. Covers every script, flag, threshold, table column, and workflow detail.

---

## High-Level Flow

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│   RSS    │───▶│  Search  │───▶│  Rank &  │───▶│  Crawl   │───▶│  Post-   │
│  Ingest  │    │  Google  │    │  Resolve │    │ Articles │    │ Process  │
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
     │               │               │               │               │
     ▼               ▼               ▼               ▼               ▼
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│wsj_items │    │  JSONL   │    │wsj_crawl │    │wsj_crawl │    │ domain   │
│  (DB)    │    │ (file)   │    │_results  │    │_results  │    │ status   │
└──────────┘    └──────────┘    │ (pending)│    │(success) │    │  (DB)    │
                               └──────────┘    └──────────┘    └──────────┘
```

**Orchestration:** `.github/workflows/finance-pipeline.yml`
**Schedule:** Daily at 6 AM ET (dual cron with timezone guard)

---

## Scripts & CLI

### `wsj_ingest.py` (926 lines)

RSS ingestion, export, lifecycle management, domain status.

| Flag | Action |
|------|--------|
| *(none)* | Ingest all 6 WSJ RSS feeds |
| `--export [PATH]` | Export unsearched items to JSONL |
| `--mark-searched FILE` | Set `searched=true` for items in FILE |
| `--mark-processed FILE` | Set `processed=true` (old method) |
| `--mark-processed-from-db` | Set `processed=true` based on DB crawl results |
| `--update-domain-status` | Aggregate crawl results → domain stats, auto-block |
| `--retry-low-relevance` | Reactivate backup articles for low-relevance items |
| `--stats` | Show database statistics (total/unprocessed/processed by feed) |

**Constants:**
- 6 WSJ Feeds: WORLD, BUSINESS, MARKETS, TECH, POLITICS, ECONOMY
- `FETCH_DELAY = 0.5s` between feed fetches
- `SKIP_CATEGORIES`: `/lifestyle/`, `/real-estate/`, `/arts/` (poor crawl success)
- `FEED_PRIORITY`: MARKETS(7) > ECONOMY(6) > TECH(5) > BUSINESS(4) > WORLD(3) > POLITICS(2) > OPINION(1) — for dedup when same article appears in multiple feeds
- `DOMAIN_ALLOWLIST`: `finance.yahoo.com`, `livemint.com` — never auto-blocked
- Skips titles starting with `"Opinion |"`

**Domain Auto-Block Logic (`--update-domain-status`):**
- Success = `crawl_status='success' AND relevance_flag='ok'`
- Failures = `crawl_status IN ('failed','error','resolve_failed','garbage','low_relevance')`
- Auto-block if: `fail_count > 5 AND success_rate < 20%`
- Also block if: `llm_fail_count >= 10 AND success_count < llm_fail_count * 3`
- `weighted_score = avg_relevance_score * success_rate` (used for domain ranking)
- Allowlisted domains never auto-blocked

---

### `wsj_to_google_news.py` (1078 lines)

Searches Google News for free alternatives to each WSJ article.

| Flag | Default | Action |
|------|---------|--------|
| `--limit N` | all | Process only N items |
| `--delay-item S` | 2.0 | Delay between WSJ items |
| `--delay-query S` | 1.0 | Delay between queries |
| `--xml` | — | Use legacy XML file instead of JSONL |
| `--input PATH` | auto | Custom JSONL input file |

**Query Building (4 queries per WSJ item):**
1. **Q1**: Clean title (most reliable, exact match)
2. **Q2**: Core keywords from title (6 tokens, lexical-mismatch resilient)
3. **Q3**: Core keywords from description (if different from Q2)
4. **Q4**: Entity + event/number (structured, e.g. `"Google" "AI" "retail"`)

**Dual-Phase Search Strategy:**
- **Phase 1**: Preferred domain `site:` queries (top 5 domains). `PHASE1_SUFFICIENT_THRESHOLD = 2`
- **Phase 2**: Broad search (always runs). Date filters: Q1-Q2 get 7-day window, Q3+ get 3-day window

**Entity Extraction:**
- 37 hardcoded known companies (Google, Apple, Microsoft, NVIDIA, etc.)
- Multi-word proper nouns, acronyms, capitalized words
- `EVENT_PRIORITY`: lawsuit(10), acquisition(9), ban(8), ipo(7), funding(6), launch(5), cut(4)

**Date Filtering:**
- WSJ pubDate -1 day to +3 days (3d mode) or -3 day to +4 days (7d mode)
- Post-filter: Only keep articles within [-1, +3] days of WSJ pubDate

**Filtering:**
- `EXCLUDED_SOURCES`: `'富途牛牛'` (Futu aggregator)
- Non-English detection (Arabic, Chinese, Japanese, Korean, Hebrew chars → skip)
- Newsletter title detection (roundup patterns like `'^plus,'`, `':\s*what to expect'`)
- Blocked domains: `scripts/data/blocked_domains.json` + DB (`wsj_domain_status.status='blocked'`)

**Preferred Domains:**
- Base: `marketwatch.com`, `cnbc.com`, `finance.yahoo.com`
- Dynamic: Top 10 from DB by `weighted_score` (where `success_count >= 3 AND success_rate >= 0.3`)

**Output Files:**
- `output/wsj_google_news_results.jsonl` — only items with articles found
- `output/wsj_google_news_results.txt` — human-readable
- `output/wsj_instrumentation.jsonl` — query performance metrics
- `output/wsj_processed_ids.json` — IDs for marking processed

---

### `embedding_rank.py` (232 lines)

Ranks Google News candidates by semantic similarity.

| Flag | Default | Action |
|------|---------|--------|
| `--top-k N` | 5 | Max results per WSJ item |
| `--min-score F` | 0.3 | Minimum cosine similarity |

**Model:** `all-MiniLM-L6-v2` (~80MB, sentence-transformers)
- Query = WSJ title + description
- Docs = candidate title + source
- Batch encode → cosine similarity → sort descending
- Preferred domains bypass `min_score` threshold (always included)

**Output:** `output/wsj_ranked_results.jsonl`

---

### `resolve_ranked.py` (304 lines)

Resolves Google News redirect URLs to actual article URLs.

| Flag | Default | Action |
|------|---------|--------|
| `--delay N` | 3.0 | Delay between requests |
| `--update-db` | — | Save results to Supabase |

**3 Resolution Strategies (in order):**
1. Direct base64 decode (old Google News format)
2. `batchexecute` API POST (new format, `AU_yqL` prefix)
3. Follow redirect / extract canonical URL from HTML

**Output:** Upserts to `wsj_crawl_results` with `crawl_status='pending'` (success) or `'resolve_failed'` (failure).

---

### `crawl_ranked.py` (597 lines)

Crawls resolved URLs with quality verification.

| Flag | Default | Action |
|------|---------|--------|
| `--delay N` | 3.0 | Delay between crawls |
| `--update-db` | — | Save results to Supabase |
| `--from-db` | — | Crawl pending items from DB (implies --update-db) |

**Constants:**
- `RELEVANCE_THRESHOLD = 0.25`
- `RELEVANCE_CHARS = 800` (chars compared for embedding)
- `LLM_ENABLED = bool(os.getenv("OPENAI_API_KEY"))`
- `CRAWL_MODE`: `"stealth"` in CI, `"undetected"` locally

**Candidate Ranking:**
- Sorted by `weighted_score = embedding_score * domain_success_rate`
- Tries articles in order until one passes all checks

**Per-Article Check Pipeline:**
```
1. Crawl (newspaper4k → crawl4ai fallback)
   └─ if crawl fails → crawl_status='failed', try next backup

2. Garbage Check
   └─ if garbage → crawl_status='garbage', try next backup

3. Embedding Relevance (cosine similarity)
   └─ if < 0.25 → crawl_status='success', relevance_flag='low', try next backup

4. LLM Verification (if OPENAI_API_KEY set)
   └─ Accept if: is_same_event=true OR (not same_event AND score >= 6)
   └─ Reject if: not same_event AND score < 6
      → relevance_flag='low', increment domain llm_fail_count, try next backup

5. All passed → crawl_status='success', relevance_flag='ok'
   → Mark other backups as 'skipped'
```

---

### `crawl_article.py` (1394 lines)

Core crawling engine. Hybrid newspaper4k + browser fallback.

| Flag | Default | Action |
|------|---------|--------|
| `<url>` | required | Article URL |
| `[mode]` | undetected | `basic` / `stealth` / `undetected` |
| `--save` | — | Save full content to file |
| `--force` | — | Force crawl even if domain blocked |
| `--no-domain-selector` | — | Disable site-specific CSS selectors |

**Crawl Modes:**
- `basic`: Headless Playwright (no stealth)
- `stealth`: Headless + stealth mode + magic + simulate_user + 2s delay
- `undetected`: UndetectedAdapter (most robust, used locally)

**Crawl Strategy:**
1. **newspaper4k** (fast HTTP): `newspaper.article(url, timeout=15)` → parse → extract title/text/authors/publish_date/top_image. Skip if domain blocked. Return if success with 300+ chars.
2. **Browser fallback** (crawl4ai):
   - Known domain → site-specific CSS selector (13 domains configured)
   - Unknown domain → 2-pass: generic pruning first, then article selectors if < 500 chars

**Site-Specific Configs (DOMAIN_CONFIG):**
- CSS selectors: cnn.com, forbes.com, engadget.com, cnbc.com, finviz.com, livemint.com, hindustantimes.com, theguardian.com
- Excluded tags: reuters.com, wsj.com, bloomberg.com, marketwatch.com, finance.yahoo.com, seekingalpha.com, businessinsider.com

**Content Extraction:**
- `trafilatura` preferred (`favor_precision=True`, output_format="txt")
- Falls back to crawl4ai's built-in extraction

**Quality Scoring (`_compute_quality`):**
- `quality_score` (0-1): weighted sum of length, short_line_ratio, link_line_ratio, boilerplate_ratio
- Reason codes: `TOO_SHORT` (<350 chars or <60 words), `TOO_LONG` (>50k), `LINK_HEAVY` (>30%), `MENU_HEAVY` (>55%), `BOILERPLATE_HEAVY` (>40%)
- `BOILERPLATE_KEYWORDS`: 17 words (cookie, privacy, terms of service, sign in, subscribe, etc.)
- `SECTION_CUT_MARKERS`: 14 regex patterns (related articles, read next, references, etc.)
- `MAX_CONTENT_LENGTH = 20000` chars (truncated with `[TRUNCATED]`)

**Google News URL Resolution (built-in):**
- Same 3 strategies as `resolve_ranked.py`
- Auto-resolves if input URL is `news.google.com`

---

### `domain_utils.py` (211 lines)

Shared domain utilities.

- `BASE_PREFERRED_DOMAINS`: marketwatch.com, cnbc.com, finance.yahoo.com
- `load_top_domains_from_db()`: Top 10 by `weighted_score` where `success_count >= 3 AND success_rate >= 0.3`
- `load_blocked_domains()`: From DB where `status='blocked'`
- `is_preferred_domain()` / `is_blocked_domain()`: Substring match (case-insensitive)

---

### `llm_analysis.py` (264 lines)

GPT-4o-mini content verification + metadata extraction.

**Config:** Model=`gpt-4o-mini`, Temperature=`0`, Max tokens=`500`, `response_format={"type": "json_object"}`

**LLM Prompt Scoring Guide:**
- 9-10: Exact same event, high quality article
- 7-8: Same event, some missing details
- 5-6: Related topic, different specific event
- 3-4: Tangentially related
- 0-2: Unrelated or garbage

**Extracted Fields:**
- `relevance_score` (0-10), `is_same_event` (bool), `confidence` (high/medium/low)
- `event_type`: earnings, acquisition, merger, lawsuit, regulation, product, partnership, funding, ipo, bankruptcy, executive, layoffs, guidance, other
- `content_quality`: article, list_page, profile, paywall, garbage, opinion
- `sentiment`: positive, negative, neutral, mixed
- `geographic_region`: US, China, Europe, Asia, Global, Other
- `time_horizon`: immediate, short_term, long_term
- `key_entities` (JSONB), `key_numbers` (JSONB), `tickers_mentioned` (text[]), `people_mentioned` (JSONB)
- `summary` (1-2 sentences for TTS)

**Domain Tracking:**
- On LLM reject (`is_same_event=false`): calls RPC `increment_llm_fail_count(domain_name)`
- On LLM pass: calls RPC `reset_llm_fail_count(domain_name)`

---

### `llm_backfill.py` (222 lines)

Backfill LLM analysis for existing articles.

| Flag | Default | Action |
|------|---------|--------|
| `--limit N` | all | Process only N articles |
| `--dry-run` | — | Preview only, no API calls |
| `--delay N` | 0.5 | Delay between API calls |

**Cost:** ~$0.00016 per article (GPT-4o-mini)

---

## Database Schema

### `wsj_items` — WSJ RSS Feed Articles
```sql
id              UUID PRIMARY KEY
feed_name       TEXT        -- WORLD, BUSINESS, MARKETS, TECH, POLITICS, ECONOMY
feed_url        TEXT
title           TEXT
description     TEXT
link            TEXT
creator         TEXT        -- author
url_hash        TEXT UNIQUE -- SHA-256 of link (dedup)
published_at    TIMESTAMPTZ
searched        BOOLEAN     -- Google search completed
searched_at     TIMESTAMPTZ
processed       BOOLEAN     -- Successfully crawled with good relevance
processed_at    TIMESTAMPTZ
```

### `wsj_crawl_results` — Crawled Backup Articles
```sql
id              UUID PRIMARY KEY
wsj_item_id     UUID FK → wsj_items
wsj_title       TEXT
wsj_link        TEXT
source          TEXT        -- Google News source name
title           TEXT        -- Backup article title
resolved_url    TEXT UNIQUE -- Final URL after redirects
resolved_domain TEXT        -- e.g., reuters.com
embedding_score FLOAT       -- Similarity to WSJ article (0-1)
crawl_status    TEXT        -- pending, success, failed, error, garbage, skipped, resolve_failed
crawl_error     TEXT
crawl_length    INT         -- Character count
content         TEXT        -- Crawled markdown
crawled_at      TIMESTAMPTZ
relevance_score FLOAT       -- Embedding cosine similarity (0-1)
relevance_flag  TEXT        -- 'ok' (>=0.25) or 'low' (<0.25)
top_image       TEXT        -- Article hero image URL
llm_same_event  BOOLEAN     -- LLM verdict
llm_score       INT         -- LLM relevance score (0-10)
```

### `wsj_domain_status` — Domain Quality Tracking
```sql
domain           TEXT PRIMARY KEY
status           TEXT        -- active, blocked
success_count    INT
fail_count       INT
success_rate     FLOAT       -- success_count / (success_count + fail_count)
weighted_score   FLOAT       -- avg_relevance_score * success_rate
failure_type     TEXT
block_reason     TEXT
llm_fail_count   INT
last_success     TIMESTAMPTZ
last_failure     TIMESTAMPTZ
last_llm_failure TIMESTAMPTZ
```

### `wsj_llm_analysis` — LLM Analysis Results
```sql
id                UUID PRIMARY KEY
crawl_result_id   UUID FK → wsj_crawl_results (UNIQUE)
relevance_score   INT           -- LLM score (0-10)
is_same_event     BOOLEAN
confidence        TEXT          -- high, medium, low
event_type        TEXT          -- earnings, acquisition, merger, lawsuit, regulation,
                                -- product, partnership, funding, ipo, bankruptcy,
                                -- executive, layoffs, guidance, other
content_quality   TEXT          -- article, list_page, profile, paywall, garbage, opinion
sentiment         TEXT          -- positive, negative, neutral, mixed
geographic_region TEXT          -- US, China, Europe, Asia, Global, Other
time_horizon      TEXT          -- immediate, short_term, long_term
summary           TEXT          -- 1-2 sentence summary for TTS
key_entities      JSONB         -- Companies, organizations
key_numbers       JSONB         -- Dollar amounts, percentages
tickers_mentioned JSONB         -- Stock tickers
people_mentioned  JSONB         -- Person names
raw_response      JSONB         -- Full LLM response (debug)
model_used        TEXT          -- gpt-4o-mini
input_tokens      INT
output_tokens     INT
created_at        TIMESTAMPTZ
```

### `briefs` — Daily Briefing Scripts (Phase 2)
```sql
id              UUID PRIMARY KEY
brief_date      DATE
ticker_group    TEXT DEFAULT 'default'  -- DAILY, MARKETS, TECH, etc.
tickers         TEXT[]
top_cluster_ids UUID[]
script_text     TEXT
created_at      TIMESTAMPTZ
UNIQUE(brief_date, ticker_group)
```

### `audio_assets` — TTS Audio (Phase 3)
```sql
brief_id      UUID PRIMARY KEY FK → briefs
storage_path  TEXT
duration_sec  INT
tts_provider  TEXT
voice         TEXT
created_at    TIMESTAMPTZ
```

---

## Crawl Status Values

| Status | Meaning | Set By | Next Action |
|--------|---------|--------|-------------|
| `pending` | Resolved URL, not yet crawled | resolve_ranked.py | Will be crawled |
| `success` | Crawled successfully | crawl_ranked.py | Check relevance_flag |
| `failed` | Crawl error (timeout, 404) | crawl_ranked.py | Try next backup |
| `error` | Unexpected exception | crawl_ranked.py | Try next backup |
| `garbage` | CSS/JS, paywall, repeated words | crawl_ranked.py | Try next backup |
| `skipped` | Another backup succeeded for this WSJ item | crawl_ranked.py | None |
| `resolve_failed` | Google News URL couldn't be resolved | resolve_ranked.py | Tracked for domain stats |

```
                          ┌─────────┐
                          │ pending │ ← Created by resolve
                          └────┬────┘
                               │
                ┌──────────────┼──────────────┐
                │              │              │
                ▼              ▼              ▼
          ┌─────────┐   ┌─────────┐   ┌─────────┐
          │ success │   │ failed  │   │ garbage │
          └────┬────┘   └─────────┘   └─────────┘
               │
      ┌────────┴────────┐
      │                 │
      ▼                 ▼
┌──────────┐     ┌──────────┐
│ flag=ok  │     │ flag=low │
└──────────┘     └──────────┘
      │                 │
      ▼                 ▼
Mark other         Try next backup
backups 'skipped'  (continue loop)
```

---

## GitHub Actions Workflow

**Trigger:** Manual (`workflow_dispatch`) or daily at 6 AM US Eastern.

**Timezone Guard:** Two cron entries (`0 11 * * *` for EST, `0 10 * * *` for EDT). A `tz-guard` job checks `date` in `America/New_York` — only the correct cron proceeds.

**Env:** `PYTHON_VERSION=3.11`, `UV_CACHE_DIR=/tmp/.uv-cache`, `TOKENIZERS_PARALLELISM=false`, `HF_HUB_DISABLE_TELEMETRY=1`

### Full Run (`crawl_only=false`)

| Job | Timeout | Steps |
|-----|---------|-------|
| **tz-guard** | 1 min | Check if 6 AM Eastern |
| **ingest-search** | 60 min | `wsj_ingest.py` → `--export` → `wsj_to_google_news.py --delay-item 0.5 --delay-query 0.3` |
| **rank-resolve** | 45 min | `embedding_rank.py` → `resolve_ranked.py --delay 0.5 --update-db` → `wsj_ingest.py --mark-searched` |
| **crawl** | 180 min | `crawl_ranked.py --delay 2 --update-db` (with OPENAI_API_KEY) |
| **save-results** | 5 min | Merge artifacts → upsert to DB → `--mark-processed-from-db` → `--update-domain-status` |

### Crawl Only (`crawl_only=true`)

| Job | Timeout | Steps |
|-----|---------|-------|
| **tz-guard** | 1 min | Always passes for manual triggers |
| **crawl-from-db** | 180 min | `crawl_ranked.py --from-db --delay 2` |
| **save-results-crawl-only** | 5 min | `--mark-processed-from-db` → `--update-domain-status` |

**Optimizations:**
- `uv` package manager (faster than pip)
- HuggingFace model caching (all-MiniLM-L6-v2)
- Playwright chromium installed fresh per run
- `continue-on-error` on crawl/search steps (pipeline proceeds even on partial failure)
- Artifact passing between jobs (7 days retention)

**Secrets Required:** `SUPABASE_URL`, `SUPABASE_KEY`, `OPENAI_API_KEY`

**Manual Trigger Options:**
- `crawl_only=true`: Skip search/rank, crawl pending DB items only
- `skip_crawl=true`: Skip crawling (test search/rank only)

---

## Garbage Detection Rules

Applied in `crawl_ranked.py` via `is_garbage_content()`:

| Rule | Threshold | What it catches |
|------|-----------|-----------------|
| Empty content | 0 chars | Crawl returned nothing |
| Repeated words | unique_ratio < 0.1 | "word word word..." |
| CSS/JS code | Multiple pattern matches | `mask-image:url`, `.f_`, `{display:`, `@media`, `font-family:`, `padding:` |
| Paywall markers | Substring match | `meterActive`, `meterExpired`, `piano`, `subscribe to continue` |
| Misc junk | Substring match | `copyright issues`, `temporarily unavailable`, `automatic translation` |

---

## Quality Scoring (`crawl_article.py`)

Applied to every crawled article:

| Metric | Check | Threshold |
|--------|-------|-----------|
| `char_len` | Character count | < 350 or < 60 words = `TOO_SHORT` |
| `char_len` | Character count | > 50,000 = `TOO_LONG` |
| `short_line_ratio` | Lines < 40 chars | > 55% = `MENU_HEAVY` |
| `link_line_ratio` | Lines containing URLs | > 30% = `LINK_HEAVY` |
| `boilerplate_ratio` | Lines with boilerplate keywords | > 40% = `BOILERPLATE_HEAVY` |
| `quality_score` | Weighted sum (0-1) | Used for ranking |

---

## Python Dependencies (`requirements.txt`)

| Package | Purpose |
|---------|---------|
| `httpx>=0.27.0` | HTTP client |
| `supabase>=2.0.0` | Supabase client |
| `python-dotenv>=1.0.0` | Environment variables |
| `sentence-transformers>=2.2.0` | Embedding model (all-MiniLM-L6-v2) |
| `numpy>=1.24.0` | Array operations |
| `trafilatura>=1.6.0` | Content extraction (preferred) |
| `lxml>=4.9.0` | XML parsing |
| `newspaper4k>=0.9.0` | Fast HTTP extraction + metadata |
| `crawl4ai>=0.4.0` | Browser-based crawling |
| `openai>=1.0.0` | OpenAI API (LLM analysis) |

---

## CLI Quick Reference

```bash
cd scripts && source .venv/bin/activate

# Full pipeline (local)
python wsj_ingest.py                                    # Ingest 6 WSJ RSS feeds
python wsj_ingest.py --export                           # Export unsearched → JSONL
python wsj_to_google_news.py --delay-item 2 --delay-query 1  # Search Google News
python embedding_rank.py --top-k 5 --min-score 0.3     # Rank by similarity
python resolve_ranked.py --delay 3 --update-db          # Resolve URLs → DB
python wsj_ingest.py --mark-searched output/wsj_items.jsonl   # Mark searched
python crawl_ranked.py --delay 3 --update-db            # Crawl articles

# Post-process
python wsj_ingest.py --mark-processed-from-db           # Mark quality crawls processed
python wsj_ingest.py --update-domain-status             # Update domain stats + auto-block
python wsj_ingest.py --retry-low-relevance              # Retry low-relevance items
python wsj_ingest.py --stats                            # Show DB statistics

# Crawl modes
python crawl_ranked.py --delay 2 --update-db            # From JSONL file
python crawl_ranked.py --from-db --delay 2              # From DB (pending items)

# LLM
python llm_backfill.py --limit 10 --delay 0.5           # Backfill LLM analysis
python llm_backfill.py --dry-run                         # Preview only

# Single article test
python crawl_article.py "https://example.com/article" stealth --save
```

---

## Environment Variables

```env
# Supabase (local dev)
NEXT_PUBLIC_SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=

# GitHub Actions secrets
SUPABASE_URL=
SUPABASE_KEY=
OPENAI_API_KEY=
```

---

## Remaining Work

### Phase 2: Briefing Generation (Next)

Generate daily TTS briefings from crawled articles using LLM synthesis.
`wsj_llm_analysis.summary` already provides per-article summaries — skip clustering/scoring.

**Briefing Types:**

| Type | ticker_group | Articles | Length |
|------|--------------|----------|--------|
| Daily Highlights | `DAILY` | 5-6 top across all feeds | 400-500 words |
| Markets | `MARKETS` | 3-5 | 250-350 words |
| Tech | `TECH` | 3-5 | 250-350 words |
| Business | `BUSINESS` | 3-5 | 250-350 words |
| World | `WORLD` | 3-5 | 250-350 words |
| Politics | `POLITICS` | 3-5 | 250-350 words |
| Economy | `ECONOMY` | 3-5 | 250-350 words |

**New script: `scripts/generate_briefing.py`**

```bash
python generate_briefing.py --type DAILY --dry-run
python generate_briefing.py --type MARKETS
python generate_briefing.py --all
```

**Architecture:**
```
wsj_crawl_results (success + ok, last 24h)
    JOIN wsj_llm_analysis (summary, entities, sentiment)
    JOIN wsj_items (feed_name for category filtering)
        ↓
    GPT-4o-mini synthesizes → TTS script (temp=0.3)
        ↓
    Save to `briefs` table (ticker_group = category name)
```

**LLM Config:** GPT-4o-mini, temp=0.3, max tokens 1000 (DAILY) / 600 (CATEGORY)
**Cost:** ~$0.005/day (~$0.15/month)
**GitHub Actions:** New `generate-briefing` job after `save-results`.

### Phase 3: TTS & Frontend (Future)

- OpenAI TTS API → audio file generation → Supabase storage
- `/finance` page with briefing audio player
- Article list with sources

---

## Key Files

```
scripts/
├── wsj_ingest.py           # RSS ingest, export, mark searched/processed, domain status
├── wsj_to_google_news.py   # Google News search (dual-phase, 4 queries per item)
├── embedding_rank.py       # Similarity ranking (all-MiniLM-L6-v2)
├── resolve_ranked.py       # URL resolution (3 strategies), save to DB
├── crawl_ranked.py         # Article crawling + garbage/relevance/LLM checks
├── crawl_article.py        # Core crawling engine (newspaper4k + crawl4ai)
├── domain_utils.py         # Preferred/blocked domain management
├── llm_analysis.py         # GPT-4o-mini analysis + domain tracking
├── llm_backfill.py         # Backfill LLM analysis on existing articles
├── requirements.txt        # Python dependencies
├── data/
│   └── blocked_domains.json  # Manual domain blocklist
└── output/                 # Ephemeral JSONL files (not persisted after GH Actions)

.github/workflows/
└── finance-pipeline.yml    # GitHub Actions (daily 6 AM ET, dual cron + tz-guard)
```

---

## Deprecated: TypeScript Library

`src/lib/finance/` contains a partially implemented TypeScript library (types, config, feed fetchers, keyword dictionary). Superseded by the Python pipeline. May be repurposed for the frontend API layer in Phase 3.
