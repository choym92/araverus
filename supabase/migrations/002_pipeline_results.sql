-- Pipeline results table for storing processed articles
-- Created: 2026-01-14

CREATE TABLE IF NOT EXISTS pipeline_results (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- WSJ source article
  wsj_title TEXT,
  wsj_link TEXT,

  -- Google News alternative
  source TEXT,
  title TEXT,
  resolved_url TEXT UNIQUE,
  resolved_domain TEXT,

  -- Ranking info
  bm25_score FLOAT,
  bm25_rank INT,

  -- Crawled content (optional, for future)
  content TEXT,
  crawled_at TIMESTAMPTZ,

  -- Metadata
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_pipeline_results_domain ON pipeline_results(resolved_domain);
CREATE INDEX IF NOT EXISTS idx_pipeline_results_created ON pipeline_results(created_at DESC);
