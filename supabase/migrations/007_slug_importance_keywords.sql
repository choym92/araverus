-- Migration 007: Add slug to wsj_items, importance + keywords to wsj_llm_analysis
-- Phase 1 of News UX enhancement

-- Slug for human-readable article URLs (/news/[slug])
ALTER TABLE wsj_items ADD COLUMN slug TEXT UNIQUE;
CREATE INDEX idx_wsj_items_slug ON wsj_items(slug);

-- Importance classification: must_read | worth_reading | optional
ALTER TABLE wsj_llm_analysis ADD COLUMN importance TEXT;
CREATE INDEX idx_wsj_llm_analysis_importance ON wsj_llm_analysis(importance);

-- Free-form keywords from LLM (2-4 per article)
ALTER TABLE wsj_llm_analysis ADD COLUMN keywords TEXT[];
