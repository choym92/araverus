-- Pipeline results table for storing processed articles
-- Created: 2026-01-14
-- Links to wsj_items via foreign key

CREATE TABLE IF NOT EXISTS pipeline_results (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Foreign key to WSJ source article
  wsj_item_id UUID REFERENCES wsj_items(id) ON DELETE CASCADE,

  -- Denormalized WSJ info (for convenience, optional)
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
CREATE INDEX IF NOT EXISTS idx_pipeline_results_wsj_item ON pipeline_results(wsj_item_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_results_domain ON pipeline_results(resolved_domain);
CREATE INDEX IF NOT EXISTS idx_pipeline_results_created ON pipeline_results(created_at DESC);
