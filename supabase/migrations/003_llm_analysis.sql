-- Migration: LLM Analysis Table and Domain Status Updates
-- Created: 2026-01-21
-- PRD: prd-llm-relevance-check.md

-- ============================================================
-- 1. Create wsj_llm_analysis table
-- ============================================================

CREATE TABLE IF NOT EXISTS wsj_llm_analysis (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Foreign Key to crawl results
  crawl_result_id UUID NOT NULL REFERENCES wsj_crawl_results(id) ON DELETE CASCADE,

  -- Core Relevance (0-10 scale)
  relevance_score INT NOT NULL CHECK (relevance_score >= 0 AND relevance_score <= 10),
  is_same_event BOOLEAN NOT NULL,
  confidence TEXT CHECK (confidence IN ('high', 'medium', 'low')),

  -- Content Classification
  event_type TEXT CHECK (event_type IN (
    'earnings', 'acquisition', 'merger', 'lawsuit', 'regulation',
    'product', 'partnership', 'funding', 'ipo', 'bankruptcy',
    'executive', 'layoffs', 'guidance', 'other'
  )),
  content_quality TEXT CHECK (content_quality IN (
    'article', 'list_page', 'profile', 'paywall', 'garbage', 'opinion'
  )),

  -- Extracted Entities (JSONB arrays)
  key_entities JSONB DEFAULT '[]',
  key_numbers JSONB DEFAULT '[]',
  tickers_mentioned JSONB DEFAULT '[]',
  people_mentioned JSONB DEFAULT '[]',

  -- Analysis
  sentiment TEXT CHECK (sentiment IN ('positive', 'negative', 'neutral', 'mixed')),
  geographic_region TEXT CHECK (geographic_region IN (
    'US', 'China', 'Europe', 'Asia', 'Global', 'Other'
  )),
  time_horizon TEXT CHECK (time_horizon IN ('immediate', 'short_term', 'long_term')),

  -- Generated Content
  summary TEXT,

  -- Debug/Audit
  raw_response JSONB,
  model_used TEXT DEFAULT 'gpt-4o-mini',
  input_tokens INT,
  output_tokens INT,

  -- Timestamps
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  -- Ensure one analysis per crawl result
  UNIQUE(crawl_result_id)
);

-- ============================================================
-- 2. Create indexes for common queries
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_llm_analysis_crawl_result ON wsj_llm_analysis(crawl_result_id);
CREATE INDEX IF NOT EXISTS idx_llm_analysis_relevance ON wsj_llm_analysis(relevance_score);
CREATE INDEX IF NOT EXISTS idx_llm_analysis_event_type ON wsj_llm_analysis(event_type);
CREATE INDEX IF NOT EXISTS idx_llm_analysis_is_same_event ON wsj_llm_analysis(is_same_event);
CREATE INDEX IF NOT EXISTS idx_llm_analysis_created_at ON wsj_llm_analysis(created_at DESC);

-- ============================================================
-- 3. Add LLM tracking columns to wsj_domain_status
-- ============================================================

ALTER TABLE wsj_domain_status
ADD COLUMN IF NOT EXISTS llm_fail_count INT DEFAULT 0,
ADD COLUMN IF NOT EXISTS last_llm_failure TIMESTAMPTZ;

-- ============================================================
-- 4. Create function to increment LLM failure count
-- ============================================================

CREATE OR REPLACE FUNCTION increment_llm_fail_count(domain_name TEXT)
RETURNS VOID AS $$
BEGIN
  INSERT INTO wsj_domain_status (domain, llm_fail_count, last_llm_failure, status)
  VALUES (domain_name, 1, NOW(), 'active')
  ON CONFLICT (domain) DO UPDATE SET
    llm_fail_count = wsj_domain_status.llm_fail_count + 1,
    last_llm_failure = NOW();
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- 5. Create function to reset LLM failure count on success
-- ============================================================

CREATE OR REPLACE FUNCTION reset_llm_fail_count(domain_name TEXT)
RETURNS VOID AS $$
BEGIN
  UPDATE wsj_domain_status
  SET llm_fail_count = 0
  WHERE domain = domain_name;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- 6. Add llm_same_event column to wsj_crawl_results
-- ============================================================

ALTER TABLE wsj_crawl_results
ADD COLUMN IF NOT EXISTS llm_same_event BOOLEAN;

-- Index for filtering by LLM result
CREATE INDEX IF NOT EXISTS idx_crawl_results_llm_same_event ON wsj_crawl_results(llm_same_event);

-- ============================================================
-- 7. Add success_rate and weighted_score to wsj_domain_status
-- ============================================================

ALTER TABLE wsj_domain_status
ADD COLUMN IF NOT EXISTS success_rate DECIMAL(5,4),
ADD COLUMN IF NOT EXISTS weighted_score DECIMAL(5,4);

-- ============================================================
-- 7. Enable RLS (Row Level Security) for wsj_llm_analysis
-- ============================================================

ALTER TABLE wsj_llm_analysis ENABLE ROW LEVEL SECURITY;

-- Policy: Service role can do everything
CREATE POLICY "Service role full access on wsj_llm_analysis"
ON wsj_llm_analysis
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

-- Policy: Authenticated users can read
CREATE POLICY "Authenticated users can read wsj_llm_analysis"
ON wsj_llm_analysis
FOR SELECT
TO authenticated
USING (true);
