<!-- Created: 2026-03-04 -->
# Follow-up: Headline Cleanup Verification

## Context
Ran `backfill_headlines.py --cleanup` on 2026-03-04, clearing 1,318 non-ok headlines.

## Tomorrow's Session Checklist
1. **Pipeline check**: Run today's pipeline cycle, then verify no new non-ok crawls have headlines:
   ```bash
   cd scripts && .venv/bin/python backfill_headlines.py --cleanup --dry-run
   ```
   - If count > 0: pipeline is still writing headlines on non-ok crawls → fix in `llm_analysis.py` (Step 2 should only run on `relevance_flag='ok'`)
   - If count = 0: pipeline is clean, no further action needed

2. **Frontend spot-check**: Browse `/news` and verify:
   - No WSJ original titles visible anywhere
   - Article count looks reasonable (should be ~1,908 visible)
   - `/news/[slug]` pages show AI headlines in h1, OG, JSON-LD

3. **RSS/Sitemap**: Check `/rss.xml` and `/sitemap.xml` — no headline-less articles should appear

4. **Search Console**: Submit `https://araverus.com/sitemap-news.xml` (one-time, after deploy confirms it's live)

## Script Retention
`scripts/backfill_headlines.py` kept as maintenance tool:
- `--cleanup`: Re-run periodically to enforce headline=ok invariant
- Default mode: Backfill missing headlines with LLM generation
