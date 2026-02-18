-- Migration 008: pgvector embeddings + story threads
-- Phase 1 of News UX enhancement

CREATE EXTENSION IF NOT EXISTS vector;

-- Article embeddings (BAAI/bge-base-en-v1.5, 768 dimensions)
CREATE TABLE wsj_embeddings (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    wsj_item_id UUID NOT NULL UNIQUE REFERENCES wsj_items(id) ON DELETE CASCADE,
    embedding   vector(768) NOT NULL,
    model       TEXT NOT NULL DEFAULT 'BAAI/bge-base-en-v1.5',
    created_at  TIMESTAMPTZ DEFAULT now()
);

-- Story threads: dynamic clusters of related articles
CREATE TABLE wsj_story_threads (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title        TEXT NOT NULL,
    centroid     vector(768),
    member_count INT NOT NULL DEFAULT 0,
    first_seen   DATE NOT NULL,
    last_seen    DATE NOT NULL,
    active       BOOLEAN NOT NULL DEFAULT true,
    created_at   TIMESTAMPTZ DEFAULT now(),
    updated_at   TIMESTAMPTZ DEFAULT now()
);

-- Link articles to their story thread
ALTER TABLE wsj_items ADD COLUMN thread_id UUID REFERENCES wsj_story_threads(id);
CREATE INDEX idx_wsj_items_thread ON wsj_items(thread_id);
