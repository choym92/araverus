-- Migration: Add `briefed` column to wsj_items table
-- Purpose: Track which articles have been included in LLM-curated briefings
-- Note: This marks ALL articles that were sent to the briefing LLM, not just curated ones

ALTER TABLE wsj_items
ADD COLUMN briefed boolean NOT NULL DEFAULT false,
ADD COLUMN briefed_at timestamptz;

-- Index for efficient filtering on briefed status
CREATE INDEX idx_wsj_items_briefed ON wsj_items(briefed);

-- Add comment explaining the column's purpose
COMMENT ON COLUMN wsj_items.briefed IS 'Marks all articles that were used as input to a briefing generation. Prevents re-briefing on previously seen articles.';
