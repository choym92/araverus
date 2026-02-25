<!-- Created: 2026-02-25 -->
# TODO: Validate Batch vs Per-Attempt Scoring Data

## Context

`6_crawl_ranked.py` now writes `attempt_order` and `weighted_score` for ALL candidates (including later-skipped ones) in a batch update before the crawl loop. This ensures complete data for analysis but adds ~N DB calls per run (where N = total candidates, typically ~1800/day).

## Validation Date

~2026-02-28 (after 3 days of data collection)

## Checks

1. **Data completeness**: How many rows have `weighted_score IS NOT NULL`? Should be high for all recent runs.
   ```sql
   SELECT crawl_status, COUNT(*), COUNT(weighted_score) as has_ws
   FROM wsj_crawl_results
   WHERE created_at >= '2026-02-25'
   GROUP BY crawl_status;
   ```

2. **Is skipped data useful?** Do we actually reference skipped candidates' scores in analysis?
   ```sql
   SELECT crawl_status, AVG(weighted_score), AVG(attempt_order)
   FROM wsj_crawl_results
   WHERE weighted_score IS NOT NULL
   GROUP BY crawl_status;
   ```

3. **DB call overhead**: Check pipeline timing — does the batch update add noticeable latency?

## Decision

- If skipped data **is** used in analysis → keep batch approach
- If skipped data **is not** used → switch to per-attempt (only write for actually-tried candidates), reduce DB calls
