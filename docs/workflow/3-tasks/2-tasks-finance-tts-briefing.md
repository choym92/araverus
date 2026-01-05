<!-- Updated: 2025-01-05 -->
# Task List: Finance TTS Briefing System (Phase 1)

Based on PRD: `docs/workflow/2-prds/prd-finance-tts-briefing.md`

## Relevant Files

### Library Core
- `src/lib/finance/db.ts` - Supabase client & TypeScript types for all tables
- `src/lib/finance/config.ts` - FETCH_CONFIG, constants, rate limits, Google News queries
- `src/lib/finance/types.ts` - TypeScript interfaces for all entities
- `src/lib/finance/pipeline.ts` - Pipeline run logging utilities

### Risk Signal System (Loughran-McDonald)
- `src/lib/finance/data/LoughranMcDonald_MasterDictionary.csv` - 86k financial words with sentiment categories
- `src/lib/finance/keywords/dictionary.ts` - L-M loader, `extractLMFeatures()` for risk signals

### Feed Fetchers
- `src/lib/finance/feeds/sec.ts` - SEC EDGAR Atom feed fetcher
- `src/lib/finance/feeds/sec.test.ts` - Unit tests for SEC fetcher
- `src/lib/finance/feeds/googleNews.ts` - Google News RSS fetcher
- `src/lib/finance/feeds/googleNews.test.ts` - Unit tests for Google News fetcher
- `src/lib/finance/feeds/resolver.ts` - Google News URL resolver queue processor
- `src/lib/finance/feeds/resolver.test.ts` - Unit tests for resolver
- `src/lib/finance/feeds/ingest.ts` - Main ingest orchestrator
- `src/lib/finance/feeds/ingest.test.ts` - Unit tests for ingest orchestrator

### Processing
- `src/lib/finance/clustering/dedup.ts` - URL hash deduplication logic
- `src/lib/finance/clustering/dedup.test.ts` - Unit tests for dedup
- `src/lib/finance/clustering/fingerprint.ts` - Keyword fingerprint generator
- `src/lib/finance/clustering/fingerprint.test.ts` - Unit tests for fingerprint
- `src/lib/finance/clustering/cluster.ts` - Event clustering logic (pg_trgm)
- `src/lib/finance/clustering/cluster.test.ts` - Unit tests for clustering
- `src/lib/finance/scoring/rules.ts` - Scoring rule engine
- `src/lib/finance/scoring/rules.test.ts` - Unit tests for scoring

### Briefing
- `src/lib/finance/briefing/generator.ts` - Script generation from top clusters
- `src/lib/finance/briefing/generator.test.ts` - Unit tests for generator

### API Routes
- `src/app/api/finance/ingest/route.ts` - POST endpoint for feed ingestion
- `src/app/api/finance/resolve/route.ts` - POST endpoint for URL resolution
- `src/app/api/finance/brief/route.ts` - GET endpoint for briefing retrieval

### Database
- `supabase/migrations/001_finance_tables.sql` - DDL for all 9 tables + indexes + seed data

### Configuration
- `.env.local` - Add CRON_SECRET environment variable

### Notes

- Unit tests should be placed alongside code files (e.g., `sec.ts` and `sec.test.ts`)
- Use `npm test` for running tests
- All API routes `/api/finance/ingest` and `/api/finance/resolve` require `CRON_SECRET` authentication
- Use `createServiceClient()` from `src/lib/supabase-server.ts` for API routes
- **중요:** `url_hash`는 삽입 시 고정, resolve 후에는 `canonical_url_hash`만 업데이트

---

## Task 2.0 Explanations: Why We Need Each Sub-task

### 2.1 Directory Structure
**Problem:** Without folders, all files end up in one place. Hard to find things.
**Solution:** Organize by feature. Need to fix scoring? Go to `scoring/`. Need to fix RSS? Go to `feeds/`.

### 2.2 `types.ts`
**Problem:** TypeScript doesn't know your data shape. `item.titlee` (typo) won't error until runtime crash.
**Solution:** Define shapes once. IDE catches typos immediately with red underline.

### 2.3 `db.ts`
**Problem:** Same database query copy-pasted in 5 files. Bug fix = edit 5 places.
**Solution:** Write each query once, import everywhere. Bug fix = edit 1 place.

### 2.4 `config.ts`
**Problem:** Magic numbers scattered everywhere. `timeout: 10000` in one file, `timeout: 15000` in another.
**Solution:** All settings in one file. Easy to find, easy to change, always consistent.

### 2.5 Risk Signal System (Loughran-McDonald Dictionary)
**Problem:** Need to identify headlines with risk-related language (lawsuits, investigations, uncertainty).

**Solution:** Use Loughran-McDonald financial dictionary for risk signals.

#### What Loughran-McDonald Does
- 86k financial words categorized by sentiment (built for 10-K filings)
- **Strong at**: uncertainty, litigious, constraining (risk indicators)
- **Weak at**: positive/negative sentiment for news headlines
- Use: `extractLMFeatures(headline)` → returns counts, ratios, riskScore

#### What We're NOT Doing (Decision: 2025-01-05)
- ~~TF-IDF keyword extraction for scoring~~ - Cold-start problem, keywords become stale
- ~~YAKE/RAKE phrase extraction~~ - Same issue
- ~~keyword_bonus in scoring~~ - Removed from formula

**Why?** Keywords extracted from recent news (7-30 days) quickly become outdated as topics change. The `keyword_bonus` would either miss new important topics or boost irrelevant old ones.

#### Future Enhancement (Not Phase 1)
- Keywords for **tagging/highlighting** what news is about (UI feature)
- Not for scoring, just for display/filtering

#### Scoring Formula (Updated)
```
impact_score = tier_score + source_bonus + risk_weight - novelty_penalty
```
- `tier_score`: Source tier (A=50, B=25, C=5)
- `source_bonus`: Number of sources covering event
- `risk_weight`: Loughran-McDonald uncertainty/litigious/constraining counts
- `novelty_penalty`: Reduce score for repeated topics

**Sub-tasks:**
- **2.5.1**: Download Loughran-McDonald CSV (~85k words)
- **2.5.2**: `dictionary.ts` - load CSV, provide `extractLMFeatures()` for risk signals

### 2.6 Google News Query Templates
**Problem:** Need specific search queries to find relevant news for each ticker.
**Solution:** Pre-define queries like `NVDA OR NVIDIA earnings OR guidance` for consistent results.

### 2.7 `fetchWithRetry()`
**Problem:** Network requests fail sometimes. One failure = entire pipeline crashes.
**Solution:** Auto-retry with increasing wait times. Attempt 1 fails → wait 1s → retry → success.

### 2.8 `pipeline.ts`
**Problem:** "Why is today's briefing empty?" No way to debug.
**Solution:** Log every run to database. Query `pipeline_runs` to see what happened.

---

## Tasks

- [x] 1.0 Setup Database Schema (Supabase DDL)
  - [x] 1.1 Create migration file `supabase/migrations/001_finance_tables.sql`
  - [x] 1.2 Add `pgcrypto` and `pg_trgm` extensions
  - [x] 1.3 Create `tickers` table with CIK and aliases columns
  - [x] 1.4 Insert seed data for NVDA and GOOG tickers
  - [x] 1.5 Create `feed_sources` table with ticker NOT NULL and error tracking columns
  - [x] 1.6 Create `raw_feed_items` table with url_hash (고정) + canonical_url_hash (resolve 후) 분리
  - [x] 1.7 Create indexes for `raw_feed_items` (ticker_time, title_trgm, resolve_status, source_domain, canonical_url_hash)
  - [x] 1.8 Create `event_clusters` table with fingerprint column
  - [x] 1.9 Create `cluster_items` junction table
  - [x] 1.10 Create `event_scores` table
  - [x] 1.11 Create `briefs` table with ticker_group for future expansion
  - [x] 1.12 Create `audio_assets` table (placeholder for Phase 2)
  - [x] 1.13 Create `pipeline_runs` table for operational logging/debugging
  - [x] 1.14 Apply migration to Supabase via dashboard or CLI

- [x] 2.0 Create Finance Library Foundation
  - [x] 2.1 Create directory structure: `src/lib/finance/{feeds,clustering,scoring,briefing}`
  - [x] 2.2 Create `src/lib/finance/types.ts` with TypeScript interfaces for all DB entities
  - [x] 2.3 Create `src/lib/finance/db.ts` with typed Supabase queries helper functions
  - [x] 2.4 Create `src/lib/finance/config.ts` with FETCH_CONFIG (User-Agent, timeout, retry settings)
  - [x] 2.5 Build Risk Signal System (Loughran-McDonald)
    - [x] 2.5.1 Download Loughran-McDonald dictionary CSV and add to `src/lib/finance/data/`
    - [x] 2.5.2 Create `src/lib/finance/keywords/dictionary.ts` - load CSV, `extractLMFeatures()`
    - ~~2.5.3-2.5.9 TF-IDF/YAKE keyword extraction~~ - CANCELLED (see explanation above)
  - [x] 2.6 Add Google News query templates for NVDA and GOOG (in config.ts)
  - [x] 2.7 Create `fetchWithRetry()` utility function with exponential backoff (in config.ts)
  - [x] 2.8 Pipeline logging helpers - `startPipelineRun()`, `finishPipelineRun()` (in db.ts)

- [x] 3.0 Implement SEC EDGAR Feed Fetcher
  - [x] 3.1 Create `src/lib/finance/feeds/sec.ts`
  - [x] 3.2 Implement `buildSecFeedUrl(cik: string, filingType: string)` function (in config.ts)
  - [x] 3.3 Implement `parseSecAtomFeed(xml: string)` to extract entries
  - [x] 3.4 Extract accession_no, filing_type, published_at from SEC entries
  - [x] 3.5 Implement `fetchSecFilings(ticker: string)` main function
  - [x] 3.6 Handle ETag/Last-Modified for conditional requests
  - [x] 3.7 Write unit tests for SEC feed parsing (17 tests passing)

- [x] 4.0 Implement Google News RSS Fetcher
  - [x] 4.1 Create `src/lib/finance/feeds/googleNews.ts`
  - [x] 4.2 Implement `buildGoogleNewsUrl(query: string)` function (in config.ts)
  - [x] 4.3 Implement `parseGoogleNewsRss(xml: string)` to extract items
  - [x] 4.4 Extract title, summary, google_redirect_url, published_at from RSS items
  - [x] 4.5 Implement `fetchGoogleNews(ticker: string, queryIndex: number)` main function
  - [x] 4.6 Set resolve_status to 'pending' for new items (url_hash = sha256(google_redirect_url))
  - [x] 4.7 Write unit tests for Google News RSS parsing (21 tests passing)

- [ ] 5.0 Build URL Resolver for Google News
  - [ ] 5.1 Create `src/lib/finance/feeds/resolver.ts`
  - [ ] 5.2 Implement `resolveGoogleNewsUrl(itemId: string, googleUrl: string)` function
  - [ ] 5.3 Follow redirects to get canonical_url
  - [ ] 5.4 Extract source_domain from final URL
  - [ ] 5.5 Set `canonical_url_hash` = sha256(canonical_url) — **url_hash는 변경 금지!**
  - [ ] 5.6 Handle failures: set resolve_status='failed', store resolve_error
  - [ ] 5.7 Implement `processResolveQueue(limit: number)` to batch process pending items
  - [ ] 5.8 Add rate limiting (1 req/sec for Google News)
  - [ ] 5.9 Write unit tests for resolver

- [ ] 6.0 Implement Deduplication Logic
  - [ ] 6.1 Create `src/lib/finance/clustering/dedup.ts`
  - [ ] 6.2 Implement `generateUrlHash(url: string)` using sha256
  - [ ] 6.3 Implement `isDuplicate(urlHash: string)` check against raw_feed_items.url_hash
  - [ ] 6.4 Implement `isDuplicateByCanonical(canonicalHash: string)` for resolved URL dedup
  - [ ] 6.5 Implement `isDuplicateSec(accessionNo: string)` for SEC-specific dedup
  - [ ] 6.6 Implement `findDuplicatesByCanonical()` to merge items with same canonical_url_hash
  - [ ] 6.7 Use `ON CONFLICT (url_hash) DO NOTHING` for insert operations
  - [ ] 6.8 Write unit tests for deduplication

- [ ] 7.0 Build Event Clustering System
  - [ ] 7.1 Create `src/lib/finance/clustering/fingerprint.ts`
  - [ ] 7.2 Implement `generateFingerprint(title: string)` with keyword extraction
  - [ ] 7.3 Create `src/lib/finance/clustering/cluster.ts`
  - [ ] 7.4 Implement `findMatchingCluster(ticker: string, title: string, publishedAt: Date)` using pg_trgm similarity
  - [ ] 7.5 Implement `createCluster(item: RawFeedItem)` for new events
  - [ ] 7.6 Implement `addToCluster(clusterId: string, itemId: string)` for matches
  - [ ] 7.7 Update cluster metadata: item_count, source_count, highest_tier, last_seen_at
  - [ ] 7.8 Select representative_url based on tier priority (A > B > C)
  - [ ] 7.9 Implement `clusterNewItems()` main orchestrator function
  - [ ] 7.10 Write unit tests for clustering logic

- [ ] 8.0 Implement Scoring Engine
  - [ ] 8.1 Create `src/lib/finance/scoring/rules.ts`
  - [ ] 8.2 Implement `calculateTierScore(tier: string)` returning 50/25/5
  - [ ] 8.3 Implement `calculateSourceBonus(sourceCount: number)` with min(20, count*3)
  - [ ] 8.4 Implement `calculateKeywordBonus(title: string)` checking high/medium/low/negative keywords
  - [ ] 8.5 Implement `calculateNoveltyPenalty(fingerprint: string)` checking 7-day window
  - [ ] 8.6 Implement `classifyEventType(title: string)` returning event type
  - [ ] 8.7 Implement `calculateImpactScore(cluster: EventCluster)` combining all factors
  - [ ] 8.8 Implement `scoreAllClusters(date: Date)` to batch score today's clusters
  - [ ] 8.9 Write unit tests for scoring rules

- [ ] 9.0 Create Briefing Script Generator
  - [ ] 9.1 Create `src/lib/finance/briefing/generator.ts`
  - [ ] 9.2 Implement `getTopClusters(tickers: string[], limit: number)` fetching by impact_score
  - [ ] 9.3 Implement `generateWhyItMatters(cluster: EventCluster)` based on event_type
  - [ ] 9.4 Implement `formatBriefSection(cluster: EventCluster, rank: number)` for each event
  - [ ] 9.5 Implement `generateBriefingScript(date: Date, tickers: string[])` combining sections
  - [ ] 9.6 Implement `saveBrief(script: BriefingScript)` to briefs table
  - [ ] 9.7 Handle case when no events found (empty briefing)
  - [ ] 9.8 Write unit tests for generator

- [ ] 10.0 Build API Endpoints
  - [ ] 10.1 Create `src/app/api/finance/ingest/route.ts`
  - [ ] 10.2 Add CRON_SECRET authentication middleware check
  - [ ] 10.3 Implement POST handler: fetch feeds → dedupe → cluster → score
  - [ ] 10.4 Log pipeline run to `pipeline_runs` table (start/finish/status)
  - [ ] 10.5 Return stats: itemsIngested, clustersCreated, resolveQueueSize, duration
  - [ ] 10.6 Create `src/app/api/finance/resolve/route.ts`
  - [ ] 10.7 Implement POST handler: process resolve queue with limit
  - [ ] 10.8 Log pipeline run to `pipeline_runs` table
  - [ ] 10.9 Return stats: resolved, failed, remaining
  - [ ] 10.10 Create `src/app/api/finance/brief/route.ts`
  - [ ] 10.11 Implement GET handler with date query parameter
  - [ ] 10.12 Return brief data: date, tickers, script, topEvents
  - [ ] 10.13 Add error handling and appropriate HTTP status codes

- [ ] 11.0 Add Environment Variables & Configuration
  - [ ] 11.1 Add `CRON_SECRET` to `.env.local`
  - [ ] 11.2 Add `CRON_SECRET` to `.env.example` (without value)
  - [ ] 11.3 Verify `SUPABASE_SERVICE_ROLE_KEY` is configured
  - [ ] 11.4 Update Vercel environment variables for production
  - [ ] 11.5 Run `npm run lint` to verify no ESLint errors
  - [ ] 11.6 Run `npm run build` to verify TypeScript compilation
  - [ ] 11.7 Test ingest endpoint manually with curl/Postman
  - [ ] 11.8 Test brief endpoint manually
  - [ ] 11.9 Verify pipeline_runs logging works correctly
  - [ ] 11.10 Document API usage in README or docs/
