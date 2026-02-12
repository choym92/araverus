-- Backfill subcategory from URL path for existing wsj_items rows.
-- Run AFTER 004_subcategory.sql in Supabase Dashboard.
-- This is a one-time backfill; new rows are handled by wsj_ingest.py.

-- Step 0: Clear bad subcategory data from previous backfill attempt
UPDATE wsj_items SET subcategory = NULL WHERE subcategory IS NOT NULL;

-- Step 1: Extract subcategory from URL path (second path segment)
-- Only when URL has 3+ path segments: /category/subcategory/article-slug
-- URLs with only 2 segments (/category/article-slug) have no subcategory
-- Example: wsj.com/tech/ai/article-slug → subcategory = 'ai'
-- Example: wsj.com/markets/article-slug → subcategory = NULL (only 2 segments)
UPDATE wsj_items
SET subcategory = split_part(regexp_replace(link, '^https?://[^/]+/', ''), '/', 2)
WHERE subcategory IS NULL
  AND link ~ '^https?://www\.wsj\.com/(tech|finance|business|economy|politics|world|markets)/'
  -- Require 3+ path segments (category/subcategory/article)
  AND split_part(regexp_replace(link, '^https?://[^/]+/', ''), '/', 3) != ''
  -- subcategory segment must exist and not be ambiguous
  AND split_part(regexp_replace(link, '^https?://[^/]+/', ''), '/', 2) != ''
  AND split_part(regexp_replace(link, '^https?://[^/]+/', ''), '/', 2) NOT IN (
      'articles', 'buyside', 'us-news'
  );

-- Step 2: Fix feed_name based on URL path for misclassified rows
-- tech/* → TECH (even if RSS said BUSINESS or MARKETS)
UPDATE wsj_items
SET feed_name = 'TECH'
WHERE link ~ '^https?://www\.wsj\.com/tech/'
  AND feed_name != 'TECH';

-- economy/* → ECONOMY
UPDATE wsj_items
SET feed_name = 'ECONOMY'
WHERE link ~ '^https?://www\.wsj\.com/economy/'
  AND feed_name != 'ECONOMY';

-- politics/* → POLITICS
UPDATE wsj_items
SET feed_name = 'POLITICS'
WHERE link ~ '^https?://www\.wsj\.com/politics/'
  AND feed_name != 'POLITICS';

-- world/* → WORLD
UPDATE wsj_items
SET feed_name = 'WORLD'
WHERE link ~ '^https?://www\.wsj\.com/world/'
  AND feed_name != 'WORLD';

-- finance/* or business/* or markets/* → BUSINESS_MARKETS
UPDATE wsj_items
SET feed_name = 'BUSINESS_MARKETS'
WHERE link ~ '^https?://www\.wsj\.com/(finance|business|markets)/'
  AND feed_name NOT IN ('BUSINESS_MARKETS');

-- Verify results
SELECT feed_name, subcategory, COUNT(*) as cnt
FROM wsj_items
WHERE subcategory IS NOT NULL
GROUP BY feed_name, subcategory
ORDER BY feed_name, cnt DESC;
