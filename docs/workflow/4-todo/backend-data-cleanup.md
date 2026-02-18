<!-- Updated: 2026-02-17 -->
# Backend TODO: WSJ Data Cleanup & Pipeline Gaps

Findings from `/audit-data wsj_` run on 2026-02-17.

---

## Quick Fixes (SQL)

### 1. ~~Block `finance.yahoo.com`~~ — RESOLVED
~~102 failures, 17% success rate — still marked `active`, wasting crawl resources.~~

**Resolved**: Wilson Score auto-blocking now handles this. `wilson=0.12 < 0.15` → auto-blocked.

### 2. ~~Block `livemint.com`~~ — RESOLVED
~~23 failures, 15% success rate.~~

**Resolved**: Wilson Score auto-blocking now handles this. `wilson=0.06 < 0.15` → auto-blocked.

### 3. Clean stale pending crawls
Pending crawls older than 7 days are stuck and won't be retried.

```sql
DELETE FROM wsj_crawl_results
WHERE crawl_status='pending' AND created_at < now() - interval '7 days';
```

**Estimated rows**: ~1

---

## Pipeline Gaps (Code Changes Needed)

### 4. 391 successful crawls missing LLM analysis
`wsj_crawl_results` with `crawl_status='success'` but no matching row in `wsj_llm_analysis`. Likely caused by pipeline interruptions or partial runs.

**Action**: Run `llm_analysis.py` backfill on unanalyzed crawl results, or add a recovery step to the pipeline.

```sql
-- Find them:
SELECT cr.id, cr.wsj_title, cr.crawled_at
FROM wsj_crawl_results cr
WHERE cr.crawl_status = 'success'
  AND NOT EXISTS (SELECT 1 FROM wsj_llm_analysis la WHERE la.crawl_result_id = cr.id)
ORDER BY cr.crawled_at DESC;
```

### 5. 103 items with >5 crawl results each
Some WSJ items generate excessive Google News search results. Consider capping search results per item in `resolve_ranked.py`.

```sql
-- See the worst offenders:
SELECT wi.title, count(*) AS crawl_count
FROM wsj_crawl_results cr
JOIN wsj_items wi ON wi.id = cr.wsj_item_id
GROUP BY wi.title
HAVING count(*) > 5
ORDER BY crawl_count DESC
LIMIT 10;
```

### 6. 629 unprocessed items (39%)
Not a bug — normal backlog. But if this grows over time, pipeline throughput may need tuning. Monitor with:

```sql
SELECT feed_name,
  count(*) AS total,
  sum(CASE WHEN NOT processed THEN 1 ELSE 0 END) AS unprocessed,
  round(100.0 * sum(CASE WHEN NOT processed THEN 1 ELSE 0 END) / count(*), 1) AS pct
FROM wsj_items GROUP BY 1 ORDER BY pct DESC;
```

### 7. 28% of items have NULL subcategory
450 out of 1,627 items. Subcategory assignment may need fallback logic or a backfill script.

```sql
-- Breakdown by feed:
SELECT feed_name, count(*) AS null_subcat
FROM wsj_items WHERE subcategory IS NULL
GROUP BY 1 ORDER BY null_subcat DESC;
```

---

## Data Health Summary

| Check | Status |
|-------|--------|
| Orphan rows (broken FKs) | Clean (0) |
| Duplicate items (`url_hash`) | Clean (0) |
| Duplicate crawl results | Clean (0) |
| Duplicate LLM analyses | Clean (0) |
| Blocked domains | 7 blocked, 2 should-be-blocked |
| LLM cost to date | ~$0.15 (gpt-4o-mini, 1.5M tokens) |
| Briefings generated | 2 (EN + KO, new feature) |
