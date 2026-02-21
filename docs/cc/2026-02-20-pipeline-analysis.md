<!-- Created: 2026-02-20 -->
# Pipeline Analysis — 2026-02-20 Run

## Timeline

```
09:00 ─ Pipeline start
09:00 ─ Phase 1: Ingest (261 items → 60 new)
09:01 ─ Phase 1: Export (60 items)
09:01 ─ Phase 1: Google News search (60 items × 3-4 queries)
09:04 ─ Phase 1 done                                          [4 min]
09:04 ─ Phase 2: Embedding rank (load model + rank 1,970 candidates)
09:08 ─ Phase 2: Resolve URLs (232 ranked → 224 resolved)
09:23 ─ Phase 2 done                                          [19 min]
09:23 ─ Phase 3: Crawl (60 items, 119 browser inits)
~09:28 ─ Phase 3 done                                         [~5 min?]
~09:28 ─ Phase 4: Post-process + domain status
~09:28 ─ Phase 4.5: Embed + Thread
09:25 ─ Phase 5: Briefing (EN generation + TTS + Whisper)
09:28 ─ EN briefing done, starting KO
09:29 ─ KO briefing text done, TTS generating...
~09:32 ─ Pipeline complete                                     [~32 min total]
```

**Total: ~32 minutes** (not 3 hours — initial impression was wrong)

### Time Breakdown

| Phase | Duration | Bottleneck |
|-------|----------|------------|
| Phase 1: Ingest + Search | 4 min | Google News queries (194 queries × 0.3s delay) |
| Phase 2: Rank + Resolve | 19 min | URL resolution (232 URLs × 0.5s delay + model load) |
| Phase 3: Crawl | ~5 min | 119 browser inits + 114 fetches |
| Phase 4: Post-process | <1 min | DB updates |
| Phase 4.5: Embed + Thread | <1 min | |
| Phase 5: Briefing | ~4 min | Gemini API (EN+KO) + TTS + Whisper alignment |

---

## The Real Problem: 27% Crawl Success Rate

```
60 WSJ items → 16 success (27%) / 44 failed (73%)
183 total crawl attempts for 60 items
```

### Failure Breakdown

| Failure Type | Count | % of 183 attempts | Impact |
|---|---|---|---|
| **Domain blocked (DB)** | 64 | 35% | Blocked candidates reaching crawl stage |
| **Too short (<500 chars)** | 94 | 51% | Crawled but content too thin |
| **Crawl error** | 5 | 3% | Browser/network failures |
| **LLM rejected** | 6 | 3% | Content didn't match WSJ topic |
| **Low relevance** | 2 | 1% | Embedding similarity too low |
| **Garbage content** | 1 | <1% | Paywall/CSS detected |
| **Success** | 16 | 9% | ✓ |

### Root Cause #1: Blocked domains reaching crawl stage (64 attempts wasted)

Blocked domains pass through search → ranking → resolve → crawl, then fail instantly at crawl. These should be filtered **earlier**.

Top offenders at crawl stage:
```
16× marketscreener.com (+ ca./uk./in. subdomains)
 6× cnbc.com
 5× m.netdania.com (4 attempts on same item!)
 3× cnn.com
 3× aol.com
 3× finimize.com
 3× oilprice.com
```

**Why this happens:** `wsj_to_google_news.py` filters by `is_source_blocked()`, but only on `source_domain` from Google News RSS `<source>` tag. After embedding ranking + URL resolution, the `resolved_domain` can differ from `source_domain`. Blocked domains slip through the cracks.

**Fix needed:** Filter blocked domains in `embedding_rank.py` or `resolve_ranked.py`, not just at search stage.

### Root Cause #2: "Too short" is the #1 failure (94 attempts)

51% of all crawl attempts produce content under 500 characters. This means:
- Browser starts up (slow)
- Page loads (network time)
- Content extracted (processing)
- Result: useless

Common "too short" domains:
```
4× marketscreener.com — financial data pages, not articles
3× cnbc.com — paywalled, returns stub
3× finimize.com — requires login
3× oilprice.com — blocks scrapers
```

### Root Cause #3: Low candidate count per item

```
Search results per WSJ item: avg 33 (min 2, max 159)
Items with <5 search results: 6
Items with <10 search results: 12
After embedding rank: avg 3.9 candidates per item
Items with 0 ranked candidates: 4
Items with ≤2 ranked candidates: 14
```

23% of items (14/60) enter crawling with ≤2 candidates. If both fail, the item fails.

### Root Cause #4: Same blocked domain tried multiple times per item

Item #47 tried `m.netdania.com` 4 times (all blocked). Item with 5 `marketscreener.com` variants (main + ca. + uk. + in. subdomains).

The `run_blocked` set in `crawl_ranked.py` should deduplicate these, but subdomains aren't matched.

---

## Newly Auto-Blocked Domains (Phase 4)

14 domains auto-blocked based on wilson score < 0.15 or LLM failure ratio:

| Domain | Success Rate | Reason |
|--------|-------------|--------|
| finance.yahoo.com | 17% (17/100) | wilson score 0.109 |
| morningstar.com | 3% (1/34) | wilson score 0.005 |
| livemint.com | 15% (4/27) | wilson score 0.059 |
| reddit.com | 0% (0/19) | wilson score 0.000 |
| moomoo.com | 0% (0/14) | 18 LLM failures |
| investing.com | 33% (4/12) | wilson score 0.138 |
| seekingalpha.com | 0% (0/6) | wilson score 0.000 |

---

## Improvements Needed (Priority Order)

### P0: Filter blocked domains BEFORE crawl stage
- Currently: blocked check at search → but domains slip through via different resolved URLs
- Fix: add blocked domain check in `resolve_ranked.py` when saving to DB (before `crawl_status='pending'`)
- Impact: eliminates 64 wasted crawl attempts (35% of all attempts)

### P1: `-site:` exclusions at Google News search level
- **Already implemented today** (this session)
- 28 highest-impact blocked domains excluded at search query level
- Google fills those slots with non-blocked sources
- Impact: more usable candidates per WSJ item

### P1: `search_hit_count` tracking
- **Designed today, pending DB migration**
- Track which domains appear most in Google News results
- Use frequency data to prioritize -site: exclusions
- Impact: optimal use of 28 -site: slots

### P2: Subdomain matching in `crawl_ranked.py`
- `run_blocked` set does exact matching
- `m.netdania.com` tried 4× because base domain match fails
- Fix: use `_is_domain_blocked()` subdomain logic (already written in wsj_to_google_news.py)

### P3: Skip "known bad" crawl patterns
- `marketscreener.com` → always too short (financial data page, not article)
- `finimize.com` → requires login
- These should be auto-blocked faster (lower wilson threshold, or block after 3 consecutive failures)

---

## Summary

| Metric | Value |
|--------|-------|
| Total runtime | ~32 minutes |
| WSJ items processed | 60 |
| Crawl success rate | 27% (16/60) |
| Wasted crawl attempts (blocked) | 64 (35%) |
| Wasted crawl attempts (too short) | 94 (51%) |
| Effective crawl rate | 16/119 actual fetches = 13% |
| Briefing generated | ✓ EN + KO |
