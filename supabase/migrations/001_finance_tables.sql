-- Migration: Finance TTS Briefing System Tables
-- Created: 2025-12-30
-- Based on PRD: docs/workflow/2-prds/prd-finance-tts-briefing.md

-- Enable required extensions
create extension if not exists pgcrypto;
create extension if not exists pg_trgm;

-----------------------------------------------------------
-- 1. tickers (watchlist with CIK)
-----------------------------------------------------------
create table if not exists tickers (
  ticker text primary key,
  company_name text not null,
  cik text not null,
  aliases text[] default '{}',
  is_active boolean not null default true,
  created_at timestamptz not null default now()
);

-- Seed data for MVP tickers
insert into tickers (ticker, company_name, cik, aliases) values
  ('NVDA', 'NVIDIA Corporation', '0001045810', '{}'),
  ('GOOG', 'Alphabet Inc.', '0001652044', '{GOOGL}')
on conflict (ticker) do nothing;

-----------------------------------------------------------
-- 2. feed_sources (feed sources per ticker)
-----------------------------------------------------------
create table if not exists feed_sources (
  id uuid primary key default gen_random_uuid(),
  source_name text not null,
  ticker text not null references tickers(ticker),
  tier text not null check (tier in ('A','B','C')),
  feed_type text not null check (feed_type in ('SEC','IR','RSS','GOOGLE_NEWS','GDELT')),
  feed_url text not null unique,
  is_enabled boolean not null default true,
  poll_minutes int not null default 30,
  etag text,
  last_modified text,
  last_fetched_at timestamptz,
  last_error text,
  error_count int not null default 0,
  created_at timestamptz not null default now()
);

-----------------------------------------------------------
-- 3. raw_feed_items (collected raw items)
-----------------------------------------------------------
create table if not exists raw_feed_items (
  id uuid primary key default gen_random_uuid(),
  feed_source_id uuid references feed_sources(id) on delete cascade,
  source_name text not null,
  tier text not null check (tier in ('A','B','C')),
  ticker text references tickers(ticker),

  -- Timestamps
  published_at timestamptz,
  fetched_at timestamptz not null default now(),

  -- Content metadata
  title text not null,
  summary text,
  url text not null,
  canonical_url text,
  url_hash text not null,
  canonical_url_hash text,

  -- Google News specific
  google_redirect_url text,
  resolve_status text default 'pending' check (resolve_status in ('pending','resolved','failed')),
  resolved_at timestamptz,
  resolve_error text,

  -- External identifiers
  external_id text,
  source_domain text,

  -- SEC specific
  filing_type text,
  accession_no text,

  content_type text,

  unique(url_hash)
);

-- Indexes for raw_feed_items
create index if not exists idx_raw_items_ticker_time on raw_feed_items(ticker, published_at desc);
create index if not exists idx_raw_items_title_trgm on raw_feed_items using gin (title gin_trgm_ops);
create index if not exists idx_raw_items_resolve_status on raw_feed_items(resolve_status) where resolve_status = 'pending';
create index if not exists idx_raw_items_source_domain on raw_feed_items(source_domain);
create index if not exists idx_raw_items_canonical_hash on raw_feed_items(canonical_url_hash) where canonical_url_hash is not null;

-----------------------------------------------------------
-- 4. event_clusters (event clusters)
-----------------------------------------------------------
create table if not exists event_clusters (
  cluster_id uuid primary key default gen_random_uuid(),
  ticker text references tickers(ticker),
  cluster_title text not null,
  cluster_fingerprint text,
  first_seen_at timestamptz not null,
  last_seen_at timestamptz not null,
  representative_url text,
  highest_tier text check (highest_tier in ('A','B','C')),
  source_count int not null default 0,
  item_count int not null default 0,
  created_at timestamptz not null default now()
);

-- Indexes for event_clusters
create index if not exists idx_clusters_ticker_time on event_clusters(ticker, first_seen_at desc);
create index if not exists idx_clusters_fingerprint on event_clusters(cluster_fingerprint);

-----------------------------------------------------------
-- 5. cluster_items (cluster-item junction)
-----------------------------------------------------------
create table if not exists cluster_items (
  cluster_id uuid references event_clusters(cluster_id) on delete cascade,
  raw_item_id uuid references raw_feed_items(id) on delete cascade,
  primary key (cluster_id, raw_item_id)
);

-----------------------------------------------------------
-- 6. event_scores (scoring and classification)
-----------------------------------------------------------
create table if not exists event_scores (
  cluster_id uuid primary key references event_clusters(cluster_id) on delete cascade,
  impact_score int not null,
  event_type text,
  horizon text,
  why_it_matters text,
  novelty_score int,
  updated_at timestamptz not null default now()
);

-----------------------------------------------------------
-- 7. briefs (briefing scripts)
-----------------------------------------------------------
create table if not exists briefs (
  id uuid primary key default gen_random_uuid(),
  brief_date date not null,
  ticker_group text not null default 'default',
  tickers text[] not null,
  top_cluster_ids uuid[] not null,
  script_text text not null,
  created_at timestamptz not null default now(),
  unique(brief_date, ticker_group)
);

-----------------------------------------------------------
-- 8. audio_assets (TTS audio - Phase 2 placeholder)
-----------------------------------------------------------
create table if not exists audio_assets (
  brief_id uuid primary key references briefs(id) on delete cascade,
  storage_path text,
  duration_sec int,
  tts_provider text,
  voice text,
  created_at timestamptz not null default now()
);

-----------------------------------------------------------
-- 9. pipeline_runs (operational logging)
-----------------------------------------------------------
create table if not exists pipeline_runs (
  id uuid primary key default gen_random_uuid(),
  run_type text not null check (run_type in ('ingest','resolve','cluster','score','brief')),
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  status text not null default 'running' check (status in ('running','success','failed')),
  items_processed int default 0,
  items_created int default 0,
  errors_count int default 0,
  error_message text,
  metadata jsonb,
  created_at timestamptz not null default now()
);

-- Index for pipeline_runs
create index if not exists idx_pipeline_runs_type_date on pipeline_runs(run_type, started_at desc);
