-- Add subcategory column to wsj_items for URL-based category extraction
-- Run in Supabase Dashboard: SQL Editor → paste → Run

ALTER TABLE wsj_items ADD COLUMN subcategory TEXT;

-- Optional index for frontend filtering
CREATE INDEX idx_wsj_items_subcategory ON wsj_items (subcategory) WHERE subcategory IS NOT NULL;
