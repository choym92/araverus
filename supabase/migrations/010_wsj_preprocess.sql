-- Migration: Add pre-processing columns to wsj_items
-- These store Gemini Flash-Lite extracted metadata from title+description (pre-search).
-- Distinct from wsj_llm_analysis which is post-crawl content-based analysis.

ALTER TABLE wsj_items
  ADD COLUMN IF NOT EXISTS extracted_entities text[],
  ADD COLUMN IF NOT EXISTS extracted_keywords text[],
  ADD COLUMN IF NOT EXISTS extracted_tickers text[],
  ADD COLUMN IF NOT EXISTS llm_search_queries text[],
  ADD COLUMN IF NOT EXISTS preprocessed_at timestamptz;
