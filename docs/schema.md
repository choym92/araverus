<!-- Updated: 2026-02-17 -->
<!-- Phase: News UX enhancement (migrations 007-009) -->
# Database Schema (araverus)

All Supabase/Postgres tables. Blog tables for the website, WSJ tables for the finance pipeline.

---

## Blog & Auth Tables

### `user_profiles`
```sql
id          UUID PRIMARY KEY
user_id     UUID UNIQUE      -- Supabase auth uid
email       TEXT UNIQUE
role        TEXT DEFAULT 'user'  -- 'admin' | 'user'
created_at  TIMESTAMPTZ
```

**Rules**: Admin determined by `role='admin'`, never by email. Index on `(user_id)`, `(email)`.

### `blog_posts`
```sql
id            UUID PRIMARY KEY
author_id     UUID FK → user_profiles.user_id
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
owner_id    UUID FK → user_profiles.user_id
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
**Written by**: `wsj_ingest.py` → `insert_wsj_item()`
**Pipeline step**: Job 1 (ingest-search) — `python wsj_ingest.py`

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
briefed       BOOLEAN       -- set true for all articles used as input to a briefing
                            --   prevents re-briefing on previously seen articles
briefed_at    TIMESTAMPTZ   -- when briefed was set true
slug          TEXT UNIQUE   -- URL-friendly slug for /news/[slug] (generated from title)
thread_id     UUID FK → wsj_story_threads(id)  -- story thread assignment (nullable)
created_at    TIMESTAMPTZ   -- auto: now()
```

**Lifecycle**: `insert → searched=true (after Google News) → processed=true (after quality crawl) → briefed=true (all articles in briefing)`
**Skip filter**: Opinion articles (`title.startswith('Opinion |')`) and low-value categories (`/lifestyle/`, `/real-estate/`, `/arts/`, `/health/`, `/style/`, `/livecoverage/`, `/arts-culture/`) are skipped at parse time.
**Category override**: `feed_name` and `subcategory` are extracted from the article URL path when available (more accurate than RSS feed name). Ambiguous paths (`articles`, `buyside`, `us-news`) fall back to RSS feed_name.

### `wsj_crawl_results` — Crawled Backup Articles
**Written by**: Two stages:
1. `resolve_ranked.py` — creates initial record with `crawl_status='pending'`
2. `crawl_ranked.py` → `save_crawl_result_to_db()` — updates with crawl data (upsert on `resolved_url`)

```sql
id              UUID PRIMARY KEY    -- auto-generated
wsj_item_id     UUID FK → wsj_items -- which WSJ article this is a backup for
wsj_title       TEXT          -- copied from wsj_items.title (denormalized for convenience)
wsj_link        TEXT          -- copied from wsj_items.link
source          TEXT          -- Google News source name (e.g., "Yahoo Finance", "CNBC")
title           TEXT          -- backup article title from Google News RSS
resolved_url    TEXT UNIQUE   -- final URL after following Google News redirects (resolve_ranked.py)
resolved_domain TEXT          -- extracted domain from resolved_url (e.g., "finance.yahoo.com")
embedding_score FLOAT         -- cosine similarity (0-1) between WSJ title+desc and backup title
                              --   computed by embedding_rank.py using all-MiniLM-L6-v2
                              --   >=0.5 high, >=0.4 medium, <0.4 low
crawl_status    TEXT          -- pending → success | failed | skipped | resolve_failed
crawl_error     TEXT          -- error message if crawl failed
crawl_length    INT           -- character count of crawled markdown
content         TEXT          -- full crawled article as markdown (via Playwright)
crawled_at      TIMESTAMPTZ   -- when crawl completed
relevance_score FLOAT         -- content similarity (0-1), computed by crawl_ranked.py
relevance_flag  TEXT          -- 'ok' (passed LLM check) or 'low' (LLM rejected / score < 0.25)
llm_same_event  BOOLEAN       -- from LLM analysis: is this the same news event as WSJ?
llm_score       INT           -- from LLM analysis: relevance score 0-10
top_image       TEXT          -- article hero image URL (extracted during crawl)
created_at      TIMESTAMPTZ   -- auto: now()
updated_at      TIMESTAMPTZ   -- auto: now()
```

**Crawl decision logic** (crawl_ranked.py):
- LLM accept: `is_same_event=true` OR `(is_same_event=false AND llm_score >= 6)` → `relevance_flag='ok'`
- LLM reject: `is_same_event=false AND llm_score < 6` → `relevance_flag='low'`, tries next backup article

### `wsj_llm_analysis` — LLM Content Analysis
**Written by**: `llm_analysis.py` → `save_analysis_to_db()`, called from `crawl_ranked.py` after each crawl
**Model**: gpt-4o-mini (temperature=0, max_tokens=500, json_object mode)
**Input**: WSJ title + WSJ description + first 800 chars of crawled content

```sql
id                UUID PRIMARY KEY    -- auto-generated
crawl_result_id   UUID FK → wsj_crawl_results (UNIQUE, 1:1)
relevance_score   INT           -- LLM score 0-10: how well crawled content matches WSJ headline
                                --   9-10: exact same event, high quality
                                --   7-8: same event, different angle
                                --   5-6: related topic, different event
                                --   3-4: tangentially related
                                --   0-2: unrelated or garbage
is_same_event     BOOLEAN       -- LLM judgment: same specific news event?
confidence        TEXT          -- high | medium | low — LLM's confidence in its judgment
event_type        TEXT          -- earnings | acquisition | merger | lawsuit | regulation |
                                --   product | partnership | funding | ipo | bankruptcy |
                                --   executive | layoffs | guidance | other
content_quality   TEXT          -- article | list_page | profile | paywall | garbage | opinion
key_entities      JSONB         -- company/org names extracted by LLM (e.g., ["Anthropic","Claude"])
key_numbers       JSONB         -- dollar amounts, percentages (e.g., ["$1.25 billion","218-214"])
tickers_mentioned JSONB         -- stock symbols if any (e.g., ["NVDA","GOOG"])
people_mentioned  JSONB         -- person names (e.g., ["Elon Musk","Pascal Soriot"])
sentiment         TEXT          -- positive | negative | neutral | mixed
geographic_region TEXT          -- US | China | Europe | Asia | Global | Other
time_horizon      TEXT          -- immediate | short_term | long_term
summary           TEXT          -- 1-2 sentence LLM-generated summary of crawled article
importance        TEXT          -- must_read | worth_reading | optional (market impact classification)
keywords          TEXT[]        -- 2-4 free-form topic keywords (e.g., {"Fed","interest rates"})
raw_response      JSONB         -- full LLM JSON response (for debugging)
model_used        TEXT          -- "gpt-4o-mini"
input_tokens      INT           -- prompt token count
output_tokens     INT           -- completion token count
created_at        TIMESTAMPTZ   -- auto: now()
```

### `wsj_domain_status` — Domain Quality Tracking
**Written by**: `wsj_ingest.py` → `cmd_update_domain_status()` and `llm_analysis.py` → `update_domain_llm_failure()`
**Pipeline step**: Job 4 (save-results) — `python wsj_ingest.py --update-domain-status`

```sql
domain           TEXT PRIMARY KEY  -- e.g., "finance.yahoo.com"
status           TEXT         -- active | blocked
failure_type     TEXT         -- type of failure (crawl error category)
fail_count       INT          -- total crawl failures
success_count    INT          -- total crawl successes
last_failure     TIMESTAMPTZ
last_success     TIMESTAMPTZ
block_reason     TEXT         -- e.g., "Auto-blocked: 25 failures, 0% success rate"
llm_fail_count   INT          -- LLM is_same_event=false count (reset on success)
last_llm_failure TIMESTAMPTZ
success_rate     NUMERIC      -- computed: success_count / (success_count + fail_count)
weighted_score   NUMERIC      -- quality score combining success rate and volume
wilson_score     NUMERIC      -- Wilson score 95% CI lower bound for true success rate
search_hit_count INT DEFAULT 0 -- Google News appearance count (incremented by wsj_to_google_news.py per run)
created_at       TIMESTAMPTZ
updated_at       TIMESTAMPTZ
```

**Auto-block rule**: `wilson_score < 0.15` (with `total >= 5`) OR `llm_fail_count >= 10 AND success < llm_fail * 3`
**LLM tracking**: `llm_fail_count` incremented when crawled content doesn't match WSJ event, reset to 0 on success.
**Search hit tracking**: `search_hit_count` incremented each time domain appears in Google News results, used to prioritize `-site:` exclusions.

### `wsj_briefings` — Daily Briefing Output (Phase 2)
**Written by**: TBD (generate_briefing.py)

```sql
id              UUID PRIMARY KEY    -- auto-generated
date            DATE          -- briefing date (e.g., 2026-02-10)
category        TEXT          -- 'ALL', 'BUSINESS_MARKETS', 'TECH', etc. Default 'ALL'
briefing_text   TEXT          -- LLM-generated briefing narrative (~700-1400 words)
audio_url       TEXT          -- Supabase Storage URL for TTS audio (Phase 3)
audio_duration  INT           -- audio length in seconds (Phase 3)
chapters        JSONB         -- chapter markers [{title, position}] for audio navigation
sentences       JSONB         -- Whisper sentence timestamps [{text, start, end}] for transcript sync
item_count      INT           -- number of articles included in this briefing
model           TEXT          -- LLM model used for generation
tts_provider    TEXT          -- TTS service used (Phase 3)
created_at      TIMESTAMPTZ   -- auto: now()
UNIQUE(date, category)        -- one briefing per day per category
```

### `wsj_briefing_items` — Briefing ↔ Article Junction
**Written by**: TBD (generate_briefing.py)

```sql
briefing_id   UUID FK → wsj_briefings(id) ON DELETE CASCADE
wsj_item_id   UUID FK → wsj_items(id) ON DELETE CASCADE
PRIMARY KEY (briefing_id, wsj_item_id)
```

**Purpose**: Tracks which articles were included in which briefing. N:N relationship — one article can appear in multiple briefings (e.g., ALL + TECH). Replaces the need for a `briefed` flag on `wsj_items`.

### `wsj_embeddings` — Article Embeddings (Phase: News UX)
**Written by**: `embed_and_thread.py`
**Model**: BAAI/bge-base-en-v1.5 (768 dimensions)

```sql
id          UUID PRIMARY KEY    -- auto-generated
wsj_item_id UUID NOT NULL UNIQUE FK → wsj_items(id) ON DELETE CASCADE
embedding   vector(768) NOT NULL -- normalized embedding vector
model       TEXT NOT NULL DEFAULT 'BAAI/bge-base-en-v1.5'
created_at  TIMESTAMPTZ DEFAULT now()
```

**Purpose**: Stores article embeddings for semantic similarity search (related articles, more-like-this, future search).

### `wsj_story_threads` — Story Thread Clusters (Phase: News UX)
**Written by**: `embed_and_thread.py`

```sql
id           UUID PRIMARY KEY    -- auto-generated
title        TEXT NOT NULL        -- LLM-generated thread headline
centroid     vector(768)          -- normalized centroid of member embeddings
member_count INT NOT NULL DEFAULT 0
first_seen   DATE NOT NULL        -- earliest article in thread
last_seen    DATE NOT NULL        -- most recent article in thread
active       BOOLEAN NOT NULL DEFAULT true  -- false when last_seen > 7 days
created_at   TIMESTAMPTZ DEFAULT now()
updated_at   TIMESTAMPTZ DEFAULT now()
```

**Purpose**: Groups related articles across days into story threads. Centroids updated incrementally. Threads deactivated after 7 days of inactivity.

### RPC Functions (pgvector)

| Function | Purpose |
|----------|---------|
| `match_articles(query_item_id, match_count, days_window)` | Cosine similarity search within ±N days |
| `match_articles_wide(query_item_id, match_count, days_window)` | Same but wider window (90 days default) |

---

## Table Relationships

```
user_profiles ──1:N──▶ blog_posts
user_profiles ──1:N──▶ blog_assets

wsj_items ──1:N──▶ wsj_crawl_results ──1:1──▶ wsj_llm_analysis
wsj_items ──N:N──▶ wsj_briefings (via wsj_briefing_items)
wsj_items ──1:1──▶ wsj_embeddings
wsj_items ──N:1──▶ wsj_story_threads (via thread_id)

wsj_domain_status (independent, updated by crawl pipeline)
```

## Pipeline Data Flow

```
Job 1: ingest-search
  wsj_ingest.py          → wsj_items (insert)
  wsj_ingest.py --export → JSONL file
  wsj_to_google_news.py  → Google News search results JSONL

Job 2: rank-resolve
  embedding_rank.py      → ranked results JSONL (adds embedding_score)
  resolve_ranked.py      → wsj_crawl_results (insert, crawl_status='pending')
  wsj_ingest.py --mark-searched → wsj_items.searched=true

Job 3: crawl
  crawl_ranked.py        → wsj_crawl_results (upsert: content, crawl_status, relevance_flag)
                         → wsj_llm_analysis (insert: LLM analysis per crawl)

Job 4: save-results
  wsj_ingest.py --mark-processed-from-db → wsj_items.processed=true
  wsj_ingest.py --update-domain-status   → wsj_domain_status (update)

Job 5: briefing
  generate_briefing.py   → wsj_briefings (insert)
                         → wsj_briefing_items (insert)
                         → wsj_items.briefed=true (all articles in briefing)
```
