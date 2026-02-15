-- Cleanup orphan pending crawl candidates
-- Created: 2026-02-12
--
-- Root cause: save-results job in GitHub Actions was re-upserting ALL resolved
-- candidates from the JSONL artifact, overwriting 'skipped' status that
-- crawl_ranked.py had correctly set in DB.
--
-- This migration marks backup candidates as 'skipped' when their WSJ item
-- already has a successful crawl that passed all quality checks
-- (crawl_status='success' AND relevance_flag='ok' = passed embedding + LLM audit).

-- Mark orphan pending rows as skipped where the WSJ item already has a quality crawl
UPDATE wsj_crawl_results
SET crawl_status = 'skipped',
    crawl_error = 'Another article succeeded for this WSJ item'
WHERE crawl_status = 'pending'
  AND wsj_item_id IN (
    SELECT DISTINCT wsj_item_id
    FROM wsj_crawl_results
    WHERE crawl_status = 'success'
      AND relevance_flag = 'ok'
  );
