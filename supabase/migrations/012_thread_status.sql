-- Phase 1: Replace boolean active column with TEXT status column
-- Values: 'active' (0-3 days), 'cooling' (3-14 days), 'archived' (14+ days)
-- Safe to drop active immediately — Phase 2 wipes all threads and re-creates with status.

ALTER TABLE wsj_story_threads DROP COLUMN active;
ALTER TABLE wsj_story_threads ADD COLUMN status TEXT NOT NULL DEFAULT 'active';
CREATE INDEX idx_wsj_story_threads_status ON wsj_story_threads(status);
