-- 013_schema_cleanup.sql
-- Catch-up migration: indexes, columns, dead RPCs, legacy tables.
-- All statements are idempotent (IF NOT EXISTS / IF EXISTS).

-- 1A. Missing indexes (performance)
CREATE INDEX IF NOT EXISTS idx_wsj_crawl_results_wsj_item ON wsj_crawl_results(wsj_item_id);
CREATE INDEX IF NOT EXISTS idx_wsj_items_published_at ON wsj_items(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_wsj_items_feed_name ON wsj_items(feed_name);
CREATE INDEX IF NOT EXISTS idx_wsj_story_threads_last_seen ON wsj_story_threads(last_seen DESC);

-- 1B. Catch-up columns (manually added, now formalized)
ALTER TABLE wsj_llm_analysis ADD COLUMN IF NOT EXISTS headline TEXT;
ALTER TABLE wsj_llm_analysis ADD COLUMN IF NOT EXISTS key_takeaway TEXT;
ALTER TABLE wsj_llm_analysis ADD COLUMN IF NOT EXISTS importance_reranked TEXT;
ALTER TABLE wsj_briefings ADD COLUMN IF NOT EXISTS chapters JSONB;
ALTER TABLE wsj_briefings ADD COLUMN IF NOT EXISTS sentences JSONB;

-- 1C. Drop dead RPC functions
DROP FUNCTION IF EXISTS increment_llm_fail_count(TEXT);
DROP FUNCTION IF EXISTS reset_llm_fail_count(TEXT);

-- 1D. Drop legacy tables (leaf-first order)
DROP TABLE IF EXISTS audio_assets CASCADE;
DROP TABLE IF EXISTS briefs CASCADE;
DROP TABLE IF EXISTS event_scores CASCADE;
DROP TABLE IF EXISTS cluster_items CASCADE;
DROP TABLE IF EXISTS raw_feed_items CASCADE;
DROP TABLE IF EXISTS event_clusters CASCADE;
DROP TABLE IF EXISTS feed_sources CASCADE;
DROP TABLE IF EXISTS tickers CASCADE;
DROP TABLE IF EXISTS pipeline_runs CASCADE;
DROP TABLE IF EXISTS pipeline_results CASCADE;
