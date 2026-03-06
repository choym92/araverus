<!-- Updated: 2026-03-06 -->
<!-- Phase: LLM Judge threading (migrations 001-014) -->
# Database Schema (araverus)

All Supabase/Postgres tables. Blog tables for the website, WSJ tables for the finance pipeline.

---

## Blog & Auth Tables

### `user_profiles`
```sql
id            UUID PRIMARY KEY  -- same as auth.users.id (direct FK)
email         TEXT UNIQUE
full_name     TEXT
display_name  TEXT             -- from OAuth provider (e.g., Google full_name)
avatar_url    TEXT             -- from OAuth provider profile picture
role          TEXT DEFAULT 'user'  -- 'admin' | 'user'
created_at    TIMESTAMPTZ
updated_at    TIMESTAMPTZ
```

**Rules**: Admin determined by `role='admin'`, never by email. `id` is the auth uid directly (no separate `user_id`).
**Auto-creation**: `on_auth_user_created` trigger inserts a profile row on first login (upserts email/display_name/avatar_url on conflict).
**RLS**: Users can SELECT/UPDATE own profile (`auth.uid() = id`). Admins have full access.

### `blog_posts`
```sql
id            UUID PRIMARY KEY
author_id     UUID FK → user_profiles.id
title         TEXT
slug          TEXT UNIQUE
content_md    TEXT
tags_csv      TEXT           -- "tag1,tag2,tag3"
status        TEXT DEFAULT 'draft'  -- 'draft' | 'published'
published_at  TIMESTAMPTZ
created_at    TIMESTAMPTZ
updated_at    TIMESTAMPTZ
```

**Note**: Blog is primarily MDX-based now (`content/blog/`). This table exists for admin/DB-backed features.

### `blog_assets`
```sql
id          UUID PRIMARY KEY
owner_id    UUID FK → user_profiles.id
path        TEXT    -- Storage object path
url         TEXT    -- Public URL
created_at  TIMESTAMPTZ
```

### RLS Policies (Blog)

- `blog_posts` SELECT: `status='published'` OR `author_id=auth.uid()` OR admin
- `blog_posts` INSERT/UPDATE/DELETE: `author_id=auth.uid()` OR admin
- `blog_assets`: Owner or admin only

---

## Finance Pipeline Tables

### `wsj_items` — WSJ RSS Feed Articles
**Written by**: `1_wsj_ingest.py` → `insert_wsj_item()`
**Pipeline step**: Job 1 (ingest-search) — `python 1_wsj_ingest.py`

```sql
id            UUID PRIMARY KEY    -- auto-generated
feed_name     TEXT          -- RSS feed category: BUSINESS_MARKETS, WORLD, TECH, ECONOMY, POLITICS
feed_url      TEXT          -- source RSS URL
title         TEXT          -- WSJ article headline (from <title> tag)
description   TEXT          -- WSJ article snippet (from <description> tag, free/unpaywalled)
link          TEXT          -- WSJ article URL (paywalled)
creator       TEXT          -- author name (from <dc:creator> tag)
url_hash      TEXT UNIQUE   -- sha256(link) for dedup, computed in parse_wsj_rss()
subcategory   TEXT          -- URL-derived subcategory (e.g., 'ai', 'trade', 'cybersecurity')
                            --   extracted from link path: wsj.com/{category}/{subcategory}/...
                            --   NULL for ambiguous paths (articles, buyside, us-news)
published_at  TIMESTAMPTZ   -- from <pubDate> tag
fetched_at    TIMESTAMPTZ   -- when we ingested it (auto: now())
searched      BOOLEAN       -- set true after Google News search completed
searched_at   TIMESTAMPTZ   -- when searched was set true
processed     BOOLEAN       -- set true when quality crawl result exists (relevance ok/good)
processed_at  TIMESTAMPTZ   -- when processed was set true
briefed       BOOLEAN NOT NULL DEFAULT false  -- set true for all articles used as input to a briefing
briefed_at    TIMESTAMPTZ   -- when briefed was set true
slug          TEXT UNIQUE   -- URL-friendly slug for /news/[slug] (generated from title)
thread_id     UUID FK → wsj_story_threads(id)  -- story thread assignment (nullable)
extracted_entities  TEXT[]   -- Gemini Flash-Lite: company/person/org names from title+desc (pre-search)
extracted_keywords  TEXT[]   -- Gemini Flash-Lite: 3-5 search terms from title+desc (pre-search)
extracted_tickers   TEXT[]   -- Gemini Flash-Lite: stock symbols from title+desc (pre-search)
llm_search_queries  TEXT[]   -- Gemini Flash-Lite: 2-3 optimized Google News queries (pre-search)
preprocessed_at     TIMESTAMPTZ  -- when preprocessing completed
created_at    TIMESTAMPTZ   -- auto: now()
```

**Lifecycle**: `insert → searched=true (after Google News) → processed=true (after quality crawl) → briefed=true (all articles in briefing)`
**Skip filter**: Opinion articles (`title.startswith('Opinion |')`) and low-value categories (`/lifestyle/`, `/real-estate/`, `/arts/`, `/health/`, `/style/`, `/livecoverage/`, `/arts-culture/`) are skipped at parse time.
**Category override**: `feed_name` and `subcategory` are extracted from the article URL path when available (more accurate than RSS feed name). Ambiguous paths (`articles`, `buyside`, `us-news`) fall back to RSS feed_name.

**Indexes**:
- `idx_wsj_items_subcategory` ON (subcategory) WHERE subcategory IS NOT NULL
- `idx_wsj_items_briefed` ON (briefed)
- `idx_wsj_items_slug` ON (slug)
- `idx_wsj_items_thread` ON (thread_id)

**Missing indexes** (recommended):
- `published_at DESC` — most common sort column, used by every frontend query
- `feed_name` — category filter in `getNewsItems()`, `getActiveThreadsGrouped()`

### `wsj_crawl_results` — Crawled Backup Articles
**Written by**: Two stages:
1. `5_resolve_ranked.py` — creates initial record with `crawl_status='pending'`
2. `6_crawl_ranked.py` → `save_crawl_result_to_db()` — updates with crawl data (upsert on `resolved_url`)

```sql
id              UUID PRIMARY KEY    -- auto-generated
wsj_item_id     UUID FK → wsj_items -- which WSJ article this is a backup for
wsj_title       TEXT          -- copied from wsj_items.title (denormalized for convenience)
wsj_link        TEXT          -- copied from wsj_items.link
source          TEXT          -- Google News source name (e.g., "Yahoo Finance", "CNBC")
title           TEXT          -- backup article title from Google News RSS
resolved_url    TEXT UNIQUE   -- final URL after following Google News redirects (5_resolve_ranked.py)
resolved_domain TEXT          -- extracted domain from resolved_url (e.g., "finance.yahoo.com")
embedding_score FLOAT         -- cosine similarity (0-1) between WSJ title+desc and backup title
                              --   computed by 4_embedding_rank.py using BAAI/bge-base-en-v1.5
                              --   >=0.5 high, >=0.4 medium, <0.4 low
crawl_status    TEXT          -- pending → success | failed | skipped | resolve_failed
crawl_error     TEXT          -- error message if crawl failed
crawl_length    INT           -- character count of crawled markdown
content         TEXT          -- full crawled article as markdown (via Playwright)
crawled_at      TIMESTAMPTZ   -- when crawl completed
relevance_score FLOAT         -- content similarity (0-1), computed by 6_crawl_ranked.py
relevance_flag  TEXT          -- 'ok' (passed LLM check) or 'low' (LLM rejected / score < 0.25)
llm_same_event  BOOLEAN       -- from LLM analysis: is this the same news event as WSJ?
llm_score       INT           -- from LLM analysis: relevance score 0-10
top_image       TEXT          -- article hero image URL (extracted during crawl)
attempt_order   INT           -- 1-indexed rank in weighted-sorted candidate list (written before crawl loop)
weighted_score  FLOAT         -- composite score: 0.50×emb + 0.25×wilson + 0.25×(llm/10) (written before crawl loop)
created_at      TIMESTAMPTZ   -- auto: now()
updated_at      TIMESTAMPTZ   -- auto: now()
```

**Crawl decision logic** (6_crawl_ranked.py):
- LLM accept: `is_same_event=true` OR `(is_same_event=false AND llm_score >= 7)` → `relevance_flag='ok'`
- LLM reject: `is_same_event=false AND llm_score < 7` → `relevance_flag='low'`, tries next backup article

**Indexes**:
- `idx_crawl_results_llm_same_event` ON (llm_same_event)

**Missing indexes** (recommended):
- `wsj_item_id` — heavily joined by frontend (getNewsItems, getArticleSources, etc.)

### `wsj_llm_analysis` — LLM Content Analysis
**Written by**: 2-step LLM flow in `lib/llm_analysis.py`, called from `6_crawl_ranked.py`
- **Step 1 (Gate)**: `analyze_content()` → `save_analysis_to_db()` — Gemini 2.5 Flash Lite, gate-only fields (relevance_score, is_same_event, confidence, content_quality)
- **Step 2 (Analysis)**: `analyze_content_detailed()` → `save_step2_to_db()` — Gemini 2.5 Flash, full analysis (headline, summary, key_takeaway, keywords, importance, etc.)
**Input**: WSJ title + WSJ description + crawled content

```sql
id                UUID PRIMARY KEY    -- auto-generated
crawl_result_id   UUID FK → wsj_crawl_results (UNIQUE, 1:1)
-- Step 1: Gate (Flash Lite)
relevance_score   INT           -- LLM score 0-10: how well crawled content matches WSJ headline
                                --   9-10: exact same event, high quality
                                --   7-8: same event, different angle
                                --   5-6: related topic, different event
                                --   3-4: tangentially related
                                --   0-2: unrelated or garbage
is_same_event     BOOLEAN       -- LLM judgment: same specific news event?
confidence        TEXT          -- high | medium | low — LLM's confidence in its judgment
content_quality   TEXT          -- article | list_page | profile | paywall | garbage | opinion
-- Step 2: Full analysis (Flash)
event_type        TEXT          -- earnings | acquisition | merger | lawsuit | regulation |
                                --   product | partnership | funding | ipo | bankruptcy |
                                --   executive | layoffs | guidance | other
key_entities      JSONB         -- company/org names extracted by LLM (e.g., ["Anthropic","Claude"])
key_numbers       JSONB         -- dollar amounts, percentages (e.g., ["$1.25 billion","218-214"])
tickers_mentioned JSONB         -- stock symbols if any (e.g., ["NVDA","GOOG"])
people_mentioned  JSONB         -- person names (e.g., ["Elon Musk","Pascal Soriot"])
sentiment         TEXT          -- positive | negative | neutral | mixed
geographic_region TEXT          -- US | China | Europe | Asia | Global | Other
time_horizon      TEXT          -- immediate | short_term | long_term
summary           TEXT          -- LLM-generated summary of crawled article (typically 150-1000 chars)
headline          TEXT          -- AI-generated headline (never copies WSJ title, max 8 words)
                                --   Written by Step 2 (Flash) via save_step2_to_db()
                                --   Only exists on relevance_flag='ok' crawls
                                --   Frontend visibility gate: no headline = article hidden everywhere
key_takeaway      TEXT          -- 1-2 sentence cross-domain impact analysis
                                --   Written by Step 2 (Flash) via save_step2_to_db()
importance        TEXT          -- must_read | worth_reading | optional (1st pass, absolute classification)
importance_reranked TEXT        -- must_read | worth_reading | optional (2nd pass, relative re-rank)
                                --   set by 8_generate_briefing.py curate_articles()
                                --   compares all articles in batch for relative importance
keywords          TEXT[]        -- 2-4 free-form topic keywords (e.g., {"Fed","interest rates"})
-- Metadata
raw_response      JSONB         -- full LLM JSON response (for debugging)
model_used        TEXT          -- DEFAULT 'gpt-4o-mini' (migration default, actual models vary: gemini-2.5-flash-lite, gemini-2.5-flash)
input_tokens      INT           -- prompt token count
output_tokens     INT           -- completion token count
created_at        TIMESTAMPTZ   -- auto: now()
```

**Note**: `headline`, `key_takeaway`, `importance_reranked` were added via manual ALTER TABLE (not in migration files). Migration 007 added `importance` and `keywords`.

**Indexes**:
- `idx_llm_analysis_crawl_result` ON (crawl_result_id)
- `idx_llm_analysis_relevance` ON (relevance_score)
- `idx_llm_analysis_event_type` ON (event_type)
- `idx_llm_analysis_is_same_event` ON (is_same_event)
- `idx_llm_analysis_created_at` ON (created_at DESC)
- `idx_wsj_llm_analysis_importance` ON (importance)

**RLS**:
- Service role: full access
- Authenticated users: read-only

**CHECK constraints**: `relevance_score` 0-10, `confidence` (high/medium/low), `event_type` (14 values), `content_quality` (6 values), `sentiment` (4 values), `geographic_region` (6 values), `time_horizon` (3 values)

### `wsj_domain_status` — Domain Quality Tracking
**Written by**: `domain_utils.py` → `cmd_update_domain_status()` (aggregation) and `reset_domain_status.py` (one-time reset)
**Pipeline step**: Job 4 (save-results) — `python domain_utils.py --update-domain-status`

```sql
domain              TEXT PRIMARY KEY  -- e.g., "finance.yahoo.com"
status              TEXT         -- active | blocked
fail_count          INT          -- total crawl failures (excludes "domain blocked" errors)
fail_counts         JSONB        -- per-reason failure counts: {"content too short": 3, "paywall": 1, ...}
success_count       INT          -- total crawl successes
last_failure        TIMESTAMPTZ  -- actual crawl time (from crawl_results.created_at)
last_success        TIMESTAMPTZ  -- actual crawl time (from crawl_results.created_at)
block_reason        TEXT         -- e.g., "Auto-blocked: wilson=0.05 < 0.15 (...)"
success_rate        NUMERIC      -- computed: success_count / (success_count + fail_count)
wilson_score        NUMERIC      -- Wilson score 95% CI lower bound for true success rate
avg_crawl_length    INT          -- average content length in chars (success crawls only)
avg_embedding_score NUMERIC      -- average title embedding similarity (all crawls)
avg_llm_score       NUMERIC      -- average LLM relevance score 0-10 (success + low_relevance)
search_hit_count    INT DEFAULT 0 -- Google News appearance count (incremented per pipeline run)
created_at          TIMESTAMPTZ
updated_at          TIMESTAMPTZ
-- Dropped columns (2026-02-23): failure_type, llm_fail_count, last_llm_failure, weighted_score
```

**Auto-block rules** (either triggers blocking):
1. `wilson_score < 0.15` (with `blockable_total >= 5`), where blockable = ONLY `http error` and `timeout or network error`
2. `avg_llm_score < 3.0` (with `>= 5` LLM-scored samples) — crawl succeeds but content is consistently irrelevant

**Manual block protection**: Domains with `block_reason` not starting with "Auto-blocked:" are never overwritten by auto-block logic (preserves JSON-migrated and hand-added blocks).
**"domain blocked" handling**: Rows with `crawl_error = "Domain blocked (DB)"` are excluded from success/fail counts (circular), but the domain is preserved as `status='blocked'`.
**Failure taxonomy** (fail_counts keys): `content too short`, `paywall`, `css/js instead of content`, `copyright or unavailable`, `repeated content`, `empty content`, `http error`, `social media`, `too many links`, `navigation/menu content`, `boilerplate content`, `content too long`, `timeout or network error`, `low relevance`, `llm rejected`.
**Search hit tracking**: `search_hit_count` incremented each time domain appears in Google News results, used to prioritize `-site:` exclusions.

### `wsj_briefings` — Daily Briefing Output
**Written by**: `8_generate_briefing.py`

```sql
id              UUID PRIMARY KEY    -- auto-generated
date            DATE          -- briefing date (e.g., 2026-02-10)
category        TEXT          -- 'EN', 'KO' (previously 'ALL'). Default 'ALL'
briefing_text   TEXT          -- LLM-generated briefing narrative (~700-1400 words)
audio_url       TEXT          -- Supabase Storage URL for TTS audio
audio_duration  INT           -- audio length in seconds
chapters        JSONB         -- chapter markers [{title, position}] for audio navigation
sentences       JSONB         -- per-sentence timestamps [{text, start, end}] for transcript sync
item_count      INT           -- number of articles included in this briefing
model           TEXT          -- LLM model used for generation
tts_provider    TEXT          -- TTS service used
created_at      TIMESTAMPTZ   -- auto: now()
UNIQUE(date, category)        -- one briefing per day per category
```

**Note**: `chapters` and `sentences` columns were added via manual ALTER TABLE (not in migration 002_briefings).

**Indexes**:
- `idx_briefings_date_category` UNIQUE ON (date, category)

### `wsj_briefing_items` — Briefing ↔ Article Junction
**Written by**: `8_generate_briefing.py`

```sql
briefing_id   UUID FK → wsj_briefings(id) ON DELETE CASCADE
wsj_item_id   UUID FK → wsj_items(id) ON DELETE CASCADE
PRIMARY KEY (briefing_id, wsj_item_id)
```

**Purpose**: Tracks which articles were included in which briefing. N:N relationship — one article can appear in multiple briefings (e.g., EN + KO). Replaces the need for a `briefed` flag on `wsj_items`.

**Indexes**:
- `idx_briefing_items_wsj` ON (wsj_item_id)

### `wsj_embeddings` — Article Embeddings
**Written by**: `7_embed_and_thread.py`
**Model**: BAAI/bge-base-en-v1.5 (768 dimensions)

```sql
id          UUID PRIMARY KEY    -- auto-generated
wsj_item_id UUID NOT NULL UNIQUE FK → wsj_items(id) ON DELETE CASCADE
embedding   vector(768) NOT NULL -- normalized embedding vector
model       TEXT NOT NULL DEFAULT 'BAAI/bge-base-en-v1.5'
created_at  TIMESTAMPTZ DEFAULT now()
```

**Purpose**: Stores article embeddings for semantic similarity search (related articles, more-like-this, future search).

### `wsj_story_threads` — Story Thread Clusters
**Written by**: `7_embed_and_thread.py`

```sql
id                    UUID PRIMARY KEY    -- auto-generated
title                 TEXT NOT NULL        -- LLM-generated thread headline (updated by thread analysis)
centroid              vector(768)          -- normalized centroid of member embeddings
member_count          INT NOT NULL DEFAULT 0
first_seen            DATE NOT NULL        -- earliest article in thread
last_seen             DATE NOT NULL        -- most recent article in thread
status                TEXT NOT NULL DEFAULT 'active' -- 'active' (0-3d) / 'cooling' (3-14d) / 'archived' (14d+)
summary               TEXT                 -- LLM-generated thread summary
parent_id             UUID FK → wsj_parent_threads(id)  -- macro-event group (nullable)
analysis_json         JSONB                -- latest thread analysis (impacts, narrative, drivers)
analysis_updated_at   TIMESTAMPTZ          -- when analysis was last run
analysis_article_count INT DEFAULT 0       -- member_count at time of last analysis
title_updated_at      TIMESTAMPTZ          -- when title was last updated by analysis
created_at            TIMESTAMPTZ DEFAULT now()
updated_at            TIMESTAMPTZ DEFAULT now()
```

**Purpose**: Groups related articles across days into story threads. Centroids updated incrementally. Status transitions: active (0-3d) → cooling (3-14d) → archived (14d+). Resurrection: archived thread matched by new article → back to active.

**analysis_json structure**:
```json
{
  "updated_title": "string",
  "summary": "string",
  "catalyst": "string",
  "drivers": ["string"],
  "impacts": [{"name", "type", "confidence", "direction", "reason", "rank"}],
  "narrative_strength": 1-10,
  "narrative_velocity": "accelerating|stable|decelerating",
  "dominant_theme": "string",
  "dominant_sector": "string",
  "dominant_macro": "string"
}
```

**Indexes**:
- `idx_wsj_story_threads_status` ON (status)
- `idx_wsj_story_threads_parent` ON (parent_id)

**Missing indexes** (recommended):
- `last_seen DESC` — used in `getActiveThreadsGrouped()` ORDER BY

### `wsj_parent_threads` — Macro-Event Groups
**Written by**: `7_embed_and_thread.py` → `group_threads_into_parents()`
**Migration**: `014_llm_judge_threading.sql`

```sql
id          UUID PRIMARY KEY DEFAULT gen_random_uuid()
title       TEXT NOT NULL        -- macro-event name (e.g., "Iran Crisis", "Fed Policy")
status      TEXT NOT NULL DEFAULT 'active'
created_at  TIMESTAMPTZ DEFAULT now()
```

**Purpose**: Groups related story threads under a parent macro-event. Re-computed daily by LLM. Threads link to parents via `wsj_story_threads.parent_id`.

### `wsj_thread_judgments` — LLM Judge Audit Trail
**Written by**: `7_embed_and_thread.py` → `match_article_with_llm_judge()`
**Migration**: `014_llm_judge_threading.sql`

```sql
id                    UUID PRIMARY KEY DEFAULT gen_random_uuid()
article_id            UUID NOT NULL FK → wsj_items(id)
candidate_threads_json JSONB NOT NULL   -- [{id, title, cosine}] candidates considered
decision              TEXT NOT NULL     -- 'assign' | 'new_thread' | 'no_match'
chosen_thread_id      UUID FK → wsj_story_threads(id)  -- only when decision='assign'
decision_reason       TEXT NOT NULL     -- LLM's explanation
confidence            TEXT NOT NULL     -- 'high' | 'medium' | 'low'
match_type            TEXT NOT NULL DEFAULT 'direct'  -- 'direct' | 'causal' | 'none'
related_thread_id     UUID FK → wsj_story_threads(id)  -- causal link target (nullable)
judge_model           TEXT NOT NULL     -- e.g., 'gemini-2.5-flash'
prompt_version        TEXT NOT NULL DEFAULT 'v1'
created_at            TIMESTAMPTZ DEFAULT now()
```

**Purpose**: Audit trail for every LLM Judge decision. Enables A/B testing, quality review, and debugging.

**Indexes**:
- `idx_thread_judgments_article` ON (article_id)

### `wsj_thread_analysis_history` — Thread Analysis Snapshots
**Written by**: `7_embed_and_thread.py` → `analyze_threads()`
**Migration**: `014_llm_judge_threading.sql`

```sql
id             UUID PRIMARY KEY DEFAULT gen_random_uuid()
thread_id      UUID NOT NULL FK → wsj_story_threads(id)
article_count  INT NOT NULL        -- member_count at time of snapshot
analysis_json  JSONB NOT NULL      -- full analysis (same structure as wsj_story_threads.analysis_json)
created_at     TIMESTAMPTZ DEFAULT now()
```

**Purpose**: Historical snapshots of thread analysis. Tracks how impacts, narrative, and drivers evolve over time.

**Indexes**:
- `idx_thread_analysis_history_thread` ON (thread_id)

### RPC Functions (pgvector)

| Function | Purpose | Status |
|----------|---------|--------|
| `match_articles(query_item_id, match_count, days_window)` | Cosine similarity search within ±N days | Active |
| `match_articles_wide(query_item_id, match_count, days_window)` | Same but wider window (90 days default) | Active |
| `increment_llm_fail_count(domain_name)` | Increment LLM failure count for domain | Dead — references dropped `llm_fail_count` column |
| `reset_llm_fail_count(domain_name)` | Reset LLM failure count on success | Dead — references dropped `llm_fail_count` column |

### Extensions

| Extension | Purpose | Migration |
|-----------|---------|-----------|
| `pgcrypto` | UUID generation (`gen_random_uuid()`) | 001 |
| `pg_trgm` | Trigram full-text search indexes | 001 |
| `vector` | pgvector for embedding similarity | 008 |

---

## Table Relationships

```
user_profiles ──1:N──▶ blog_posts
user_profiles ──1:N──▶ blog_assets

wsj_items ──1:N──▶ wsj_crawl_results ──1:1──▶ wsj_llm_analysis
wsj_items ──N:N──▶ wsj_briefings (via wsj_briefing_items)
wsj_items ──1:1──▶ wsj_embeddings
wsj_items ──N:1──▶ wsj_story_threads (via thread_id)
wsj_items ──1:N──▶ wsj_thread_judgments (via article_id)

wsj_story_threads ──N:1──▶ wsj_parent_threads (via parent_id)
wsj_story_threads ──1:N──▶ wsj_thread_analysis_history (via thread_id)

wsj_domain_status (independent, updated by crawl pipeline)
```

## Pipeline Data Flow

```
Job 1: ingest-search
  1_wsj_ingest.py          → wsj_items (insert)
  2_wsj_preprocess.py      → wsj_items (update: extracted_*, llm_search_queries)
  1_wsj_ingest.py --export → JSONL file (includes llm_search_queries)
  3_wsj_to_google_news.py  → Google News search results JSONL

Job 2: rank-resolve
  4_embedding_rank.py      → ranked results JSONL (adds embedding_score)
  5_resolve_ranked.py      → wsj_crawl_results (insert, crawl_status='pending')
  domain_utils.py --mark-searched → wsj_items.searched=true

Job 3: crawl
  6_crawl_ranked.py        → wsj_crawl_results (upsert: content, crawl_status, relevance_flag)
                           → wsj_llm_analysis (insert: LLM analysis per crawl)

Job 4: save-results
  1_wsj_ingest.py --mark-processed-from-db → wsj_items.processed=true
  domain_utils.py --update-domain-status   → wsj_domain_status (update)

Job 5: embed-thread
  7_embed_and_thread.py    → wsj_embeddings (upsert)
                           → wsj_story_threads (insert/update, analysis_json)
                           → wsj_items.thread_id (update)
                           → wsj_thread_judgments (insert — LLM Judge audit)
                           → wsj_thread_analysis_history (insert — analysis snapshots)
                           → wsj_parent_threads (insert — macro-event groups)

Job 6: briefing
  8_generate_briefing.py   → wsj_briefings (insert)
                           → wsj_briefing_items (insert)
                           → wsj_items.briefed=true
                           → wsj_llm_analysis.importance_reranked (update)
```

---

## Legacy Tables (Migration 001 — unused)

These tables were created in the original ticker-based finance pipeline (2025-12-30) and are no longer used by any script. They remain in the database but could be dropped.

| Table | Original purpose |
|-------|-----------------|
| `tickers` | Watchlist with CIK (NVDA, GOOG seed) |
| `feed_sources` | Feed sources per ticker (SEC, IR, RSS, Google News, GDELT) |
| `raw_feed_items` | Collected raw items from feeds |
| `event_clusters` | Event clustering output |
| `cluster_items` | Cluster ↔ item junction |
| `event_scores` | Scoring and classification per cluster |
| `briefs` | Briefing scripts (old format) |
| `audio_assets` | TTS audio placeholder |
| `pipeline_runs` | Operational logging |
| `pipeline_results` | Processed articles (Migration 002, replaced by `wsj_crawl_results`) |

---

## Recommendations

### Missing Indexes (add when needed)

```sql
-- wsj_items: most common sort + filter columns
CREATE INDEX idx_wsj_items_published_at ON wsj_items(published_at DESC);
CREATE INDEX idx_wsj_items_feed_name ON wsj_items(feed_name);

-- wsj_crawl_results: heavily joined by frontend
CREATE INDEX idx_wsj_crawl_results_wsj_item ON wsj_crawl_results(wsj_item_id);

-- wsj_story_threads: sorted in getActiveThreadsGrouped()
CREATE INDEX idx_wsj_story_threads_last_seen ON wsj_story_threads(last_seen DESC);
```

### Dead RPC Cleanup

```sql
DROP FUNCTION IF EXISTS increment_llm_fail_count(TEXT);
DROP FUNCTION IF EXISTS reset_llm_fail_count(TEXT);
```

### Pending Schema Changes

| Change | Phase | Table |
|--------|-------|-------|
| Create `user_watchlist` table | future | new |
| Create `wsj_thread_links` table | future | new |

### Manual Columns (not in migrations)

These columns exist in the DB but were added via manual ALTER TABLE, not tracked in migration files:
- `wsj_llm_analysis.headline`
- `wsj_llm_analysis.key_takeaway`
- `wsj_llm_analysis.importance_reranked`
- `wsj_briefings.chapters`
- `wsj_briefings.sentences`

Consider creating a catch-up migration to formalize these.
