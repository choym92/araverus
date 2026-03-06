-- 014_llm_judge_threading.sql
-- LLM Judge threading: parent threads, judgment audit trail, analysis history.
-- All statements are idempotent (IF NOT EXISTS / IF EXISTS).

-- 1. Parent threads (macro event grouping)
CREATE TABLE IF NOT EXISTS wsj_parent_threads (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  created_at TIMESTAMPTZ DEFAULT now()
);

-- 2. LLM Judge judgment audit trail
CREATE TABLE IF NOT EXISTS wsj_thread_judgments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  article_id UUID NOT NULL REFERENCES wsj_items(id),
  candidate_threads_json JSONB NOT NULL,
  decision TEXT NOT NULL,                -- 'assign' | 'new_thread' | 'no_match'
  chosen_thread_id UUID REFERENCES wsj_story_threads(id),
  decision_reason TEXT NOT NULL,
  confidence TEXT NOT NULL,              -- 'high' | 'medium' | 'low'
  match_type TEXT NOT NULL DEFAULT 'direct',  -- 'direct' | 'causal' | 'none'
  related_thread_id UUID REFERENCES wsj_story_threads(id),
  judge_model TEXT NOT NULL,
  prompt_version TEXT NOT NULL DEFAULT 'v1',
  created_at TIMESTAMPTZ DEFAULT now()
);

-- 3. Thread analysis history (snapshots)
CREATE TABLE IF NOT EXISTS wsj_thread_analysis_history (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  thread_id UUID NOT NULL REFERENCES wsj_story_threads(id),
  article_count INT NOT NULL,
  analysis_json JSONB NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- 4. New columns on wsj_story_threads
ALTER TABLE wsj_story_threads ADD COLUMN IF NOT EXISTS parent_id UUID REFERENCES wsj_parent_threads(id);
ALTER TABLE wsj_story_threads ADD COLUMN IF NOT EXISTS analysis_json JSONB;
ALTER TABLE wsj_story_threads ADD COLUMN IF NOT EXISTS analysis_updated_at TIMESTAMPTZ;
ALTER TABLE wsj_story_threads ADD COLUMN IF NOT EXISTS analysis_article_count INT DEFAULT 0;
ALTER TABLE wsj_story_threads ADD COLUMN IF NOT EXISTS title_updated_at TIMESTAMPTZ;

-- 5. Indexes
CREATE INDEX IF NOT EXISTS idx_thread_judgments_article ON wsj_thread_judgments(article_id);
CREATE INDEX IF NOT EXISTS idx_thread_analysis_history_thread ON wsj_thread_analysis_history(thread_id);
CREATE INDEX IF NOT EXISTS idx_wsj_story_threads_parent ON wsj_story_threads(parent_id);
