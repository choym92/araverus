-- Per-reason failure tracking for wsj_domain_status
-- Tracks failure counts by category (e.g., "content too short", "paywall")
-- Used for smarter auto-blocking: content_mismatch reasons excluded from block decisions

ALTER TABLE wsj_domain_status
  ADD COLUMN IF NOT EXISTS fail_counts JSONB DEFAULT '{}'::jsonb;
