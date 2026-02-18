-- Migration 009: pgvector RPC functions for article similarity
-- Phase 1 of News UX enhancement

-- Find similar articles to a given article within a time window
CREATE OR REPLACE FUNCTION match_articles(
    query_item_id UUID,
    match_count INT DEFAULT 5,
    days_window INT DEFAULT 1
)
RETURNS TABLE (
    id UUID,
    title TEXT,
    slug TEXT,
    feed_name TEXT,
    published_at TIMESTAMPTZ,
    similarity FLOAT
)
LANGUAGE plpgsql
AS $$
DECLARE
    query_embedding vector(768);
    query_published TIMESTAMPTZ;
BEGIN
    -- Get the embedding and published date for the query article
    SELECT e.embedding, i.published_at
    INTO query_embedding, query_published
    FROM wsj_embeddings e
    JOIN wsj_items i ON i.id = e.wsj_item_id
    WHERE e.wsj_item_id = query_item_id;

    IF query_embedding IS NULL THEN
        RETURN;
    END IF;

    RETURN QUERY
    SELECT
        i.id,
        i.title,
        i.slug,
        i.feed_name,
        i.published_at,
        1 - (e.embedding <=> query_embedding) AS similarity
    FROM wsj_embeddings e
    JOIN wsj_items i ON i.id = e.wsj_item_id
    WHERE e.wsj_item_id != query_item_id
      AND i.published_at >= query_published - (days_window || ' days')::INTERVAL
      AND i.published_at <= query_published + (days_window || ' days')::INTERVAL
    ORDER BY e.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- Find similar articles across a wider time window (for "more like this")
CREATE OR REPLACE FUNCTION match_articles_wide(
    query_item_id UUID,
    match_count INT DEFAULT 5,
    days_window INT DEFAULT 90
)
RETURNS TABLE (
    id UUID,
    title TEXT,
    slug TEXT,
    feed_name TEXT,
    published_at TIMESTAMPTZ,
    similarity FLOAT
)
LANGUAGE plpgsql
AS $$
DECLARE
    query_embedding vector(768);
    query_published TIMESTAMPTZ;
BEGIN
    SELECT e.embedding, i.published_at
    INTO query_embedding, query_published
    FROM wsj_embeddings e
    JOIN wsj_items i ON i.id = e.wsj_item_id
    WHERE e.wsj_item_id = query_item_id;

    IF query_embedding IS NULL THEN
        RETURN;
    END IF;

    RETURN QUERY
    SELECT
        i.id,
        i.title,
        i.slug,
        i.feed_name,
        i.published_at,
        1 - (e.embedding <=> query_embedding) AS similarity
    FROM wsj_embeddings e
    JOIN wsj_items i ON i.id = e.wsj_item_id
    WHERE e.wsj_item_id != query_item_id
      AND i.published_at >= query_published - (days_window || ' days')::INTERVAL
    ORDER BY e.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;
