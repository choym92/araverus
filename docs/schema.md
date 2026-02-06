<!-- Updated: 2026-02-06 -->
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
```sql
id            UUID PRIMARY KEY
feed_name     TEXT          -- WORLD, BUSINESS, MARKETS, TECH, POLITICS, ECONOMY
feed_url      TEXT
title         TEXT
description   TEXT
link          TEXT
creator       TEXT          -- Author
url_hash      TEXT UNIQUE   -- SHA-256 of link (dedup)
published_at  TIMESTAMPTZ
searched      BOOLEAN       -- Google search completed
searched_at   TIMESTAMPTZ
processed     BOOLEAN       -- Successfully crawled with good relevance
processed_at  TIMESTAMPTZ
```

### `wsj_crawl_results` — Crawled Backup Articles
```sql
id              UUID PRIMARY KEY
wsj_item_id     UUID FK → wsj_items
wsj_title       TEXT
wsj_link        TEXT
source          TEXT          -- Google News source name
title           TEXT          -- Backup article title
resolved_url    TEXT UNIQUE   -- Final URL after redirects
resolved_domain TEXT          -- e.g., reuters.com
embedding_score FLOAT         -- Similarity to WSJ article (0-1)
crawl_status    TEXT          -- pending, success, failed, skipped, garbage
crawl_error     TEXT
crawl_length    INT           -- Character count
content         TEXT          -- Crawled markdown
crawled_at      TIMESTAMPTZ
relevance_score FLOAT         -- Content similarity (0-1)
relevance_flag  TEXT          -- 'ok' (>=0.25) or 'low' (<0.25)
top_image       TEXT          -- Article hero image URL
```

### `wsj_domain_status` — Domain Quality Tracking
```sql
domain           TEXT PRIMARY KEY
status           TEXT         -- active, blocked
success_count    INT
fail_count       INT
failure_type     TEXT
block_reason     TEXT
llm_fail_count   INT
last_success     TIMESTAMPTZ
last_failure     TIMESTAMPTZ
last_llm_failure TIMESTAMPTZ
```

**Auto-block rule**: `fail_count > 5 AND success_rate < 20%` OR `llm_fail_count >= 3`

### `wsj_llm_analysis` — LLM Analysis Results
```sql
id                UUID PRIMARY KEY
crawl_result_id   UUID FK → wsj_crawl_results (UNIQUE)
relevance_score   FLOAT          -- LLM score (1-10)
is_same_event     BOOLEAN        -- Same news event as WSJ?
event_type        TEXT           -- earnings, acquisition, regulation, product, etc.
sentiment         TEXT           -- positive, negative, neutral, mixed
content_quality   TEXT           -- article, list_page, paywall, garbage, opinion
summary           TEXT           -- 1-2 sentence summary for TTS
key_entities      JSONB          -- Companies, organizations
key_numbers       JSONB          -- Dollar amounts, percentages
tickers_mentioned TEXT[]         -- Stock tickers
created_at        TIMESTAMPTZ
```

### `briefs` — Daily Briefing Scripts
```sql
id              UUID PRIMARY KEY
brief_date      DATE
ticker_group    TEXT DEFAULT 'default'  -- DAILY, MARKETS, TECH, etc.
tickers         TEXT[]
top_cluster_ids UUID[]
script_text     TEXT                    -- Generated TTS script
created_at      TIMESTAMPTZ
UNIQUE(brief_date, ticker_group)
```

### `audio_assets` — TTS Audio (Phase 3, future)
```sql
brief_id      UUID PRIMARY KEY FK → briefs
storage_path  TEXT
duration_sec  INT
tts_provider  TEXT
voice         TEXT
created_at    TIMESTAMPTZ
```

---

## Table Relationships

```
user_profiles ──1:N──▶ blog_posts
user_profiles ──1:N──▶ blog_assets

wsj_items ──1:N──▶ wsj_crawl_results ──1:1──▶ wsj_llm_analysis

wsj_domain_status (independent, updated by crawl pipeline)

briefs ──1:1──▶ audio_assets (future)
```
