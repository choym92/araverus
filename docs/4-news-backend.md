<!-- Updated: 2026-02-19 -->
# News Platform — Backend & Pipeline

Single source of truth for the finance news pipeline: ingestion, crawling, analysis, briefing generation, and deployment.

---

## High-Level Architecture

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│   RSS    │───▶│  Search  │───▶│  Rank &  │───▶│  Crawl   │───▶│  Post-   │───▶│ Embed &  │───▶│ Briefing │
│  Ingest  │    │  Google  │    │  Resolve │    │ Articles │    │ Process  │    │  Thread  │    │   Gen    │
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
     │               │               │               │               │               │               │
     ▼               ▼               ▼               ▼               ▼               ▼               ▼
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│wsj_items │    │  JSONL   │    │wsj_crawl │    │wsj_crawl │    │ domain   │    │wsj_embed │    │wsj_brief │
│  (DB)    │    │ (file)   │    │_results  │    │_results  │    │ status   │    │dings +   │    │ ings(DB) │
│ +slug    │    └──────────┘    │ (pending)│    │(success) │    │  (DB)    │    │ threads  │    │ +audio   │
└──────────┘                    └──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
```

**Orchestration:** `.github/workflows/finance-pipeline.yml`
**Schedule:** Daily at 6 AM ET (dual cron with timezone guard)

---

## Pipeline Scripts

### `wsj_ingest.py` (1071 lines)

RSS ingestion, export, lifecycle management, domain status.

| Flag | Action |
|------|--------|
| *(none)* | Ingest all 6 WSJ RSS feeds |
| `--export [PATH]` | Export unsearched items to JSONL |
| `--mark-searched FILE` | Set `searched=true` for items in FILE |
| `--mark-processed FILE` | Set `processed=true` (old method) |
| `--mark-processed-from-db` | Set `processed=true` based on DB crawl results |
| `--update-domain-status` | Aggregate crawl results → domain stats, auto-block |
| `--retry-low-relevance` | Reactivate backup articles for low-relevance items |
| `--seed-blocked-from-json` | One-time: migrate JSON blocked domains to DB |
| `--stats` | Show database statistics |

**Feeds:** 6 WSJ RSS feeds — BUSINESS, MARKETS, WORLD, TECH, ECONOMY, POLITICS. Each feed has a `feed_name` and `feed_url` configured as constants.

**Category extraction:** URL-based (~95% accuracy). Parses `/articles/` or `/livecoverage/` URL paths to extract subcategory (e.g., `wsj.com/economy/trade` → `trade`). Falls back to `feed_name` if URL pattern doesn't match. Known gap: ~28% of items still have NULL `subcategory`.

**Dedup:** Title-based dedup with Levenshtein-like comparison. When a duplicate is found across feeds, keeps the version from the feed with fewer total items (least-count category balancing). Skips lifestyle/arts/opinion content.

**Slug generation:** `slugify(title)[:80]` with date-suffix collision handling (e.g., `-2`, `-3`).

**Domain auto-block** (via `--update-domain-status`): Two criteria — `fail_count > 5 AND success_rate < 20%` OR `llm_fail_count >= 10 AND success_count < llm_fail_count * 3`. Uses Wilson score for statistical confidence on small sample sizes.

### `wsj_to_google_news.py` (1078 lines)

Searches Google News for free alternatives to each WSJ article.

| Flag | Default | Action |
|------|---------|--------|
| `--limit N` | all | Process only N items |
| `--delay-item S` | 2.0 | Delay between WSJ items |
| `--delay-query S` | 1.0 | Delay between queries |
| `--input PATH` | auto | Custom JSONL input file |

**Key logic:** 4 queries per item (clean title, core keywords, description keywords, entity+event). Dual-phase search: Phase 1 preferred domain `site:` queries, Phase 2 broad search. Date filtering: [-1, +3] days from WSJ pubDate. Non-English/newsletter/blocked domain filtering.

### `embedding_rank.py` (232 lines)

Ranks Google News candidates by semantic similarity.

| Flag | Default | Action |
|------|---------|--------|
| `--top-k N` | 5 | Max results per WSJ item |
| `--min-score F` | 0.3 | Minimum cosine similarity |

**Model:** `all-MiniLM-L6-v2`. Preferred domains bypass min_score threshold.

### `resolve_ranked.py` (304 lines)

Resolves Google News redirect URLs to actual article URLs.

| Flag | Default | Action |
|------|---------|--------|
| `--delay N` | 3.0 | Delay between requests |
| `--update-db` | — | Save results to Supabase |

**3 strategies:** Direct base64 decode → `batchexecute` API POST → follow redirect/canonical URL.

### `crawl_ranked.py`

Crawls resolved URLs with quality verification. Maintains `run_blocked` in-memory set (seeded from DB) to skip domains that fail during the current run.

| Flag | Default | Action |
|------|---------|--------|
| `--delay N` | 3.0 | Delay between crawls |
| `--update-db` | — | Save results to Supabase |
| `--from-db` | — | Crawl pending items from DB (implies --update-db) |

**Key logic:** Candidates sorted by `weighted_score = embedding_score * domain_success_rate`. Per-article pipeline: crawl → garbage check → embedding relevance (≥0.25) → LLM verification → accept or try next backup. `CRAWL_MODE`: `"stealth"` in CI, `"undetected"` locally.

### `crawl_article.py`

Core crawling engine. Hybrid newspaper4k + browser fallback. Blocked domain check uses caller-provided `blocked_domains` set (from DB). No local JSON file — domain blocking is DB-only via `domain_utils.is_blocked_domain()`.

| Flag | Default | Action |
|------|---------|--------|
| `<url>` | required | Article URL |
| `[mode]` | undetected | `basic` / `stealth` / `undetected` |
| `--save` | — | Save full content to file |
| `--force` | — | Force crawl even if domain blocked |

**Strategy:** newspaper4k first (fast HTTP), then crawl4ai browser fallback. 13 domains with site-specific CSS selectors. Content extraction via trafilatura (preferred). Quality scoring: weighted sum of length, short_line_ratio, link_line_ratio, boilerplate_ratio.

### `domain_utils.py` (211 lines)

Shared domain utilities. Blocked domain loading from DB (`wsj_domain_status` table only). Substring matching via `is_blocked_domain()`.

### `llm_analysis.py` (280 lines)

**Gemini 2.5 Flash** content verification + metadata extraction (JSON mode). Extracts: relevance_score, is_same_event, event_type, content_quality, sentiment, geographic_region, key_entities, key_numbers, tickers, people, summary (150-250 words), **importance** (must_read/worth_reading/optional), **keywords** (2-4 free-form). Tracks domain LLM fail/success counts. Requires `GEMINI_API_KEY`.

### `llm_backfill.py` (222 lines)

Backfill LLM analysis for existing articles. ~$0.00016/article.

| Flag | Default | Action |
|------|---------|--------|
| `--limit N` | all | Process only N articles |
| `--dry-run` | — | Preview only |
| `--delay N` | 0.5 | Delay between API calls |

### `embed_and_thread.py` (new)

Embeds articles and assigns to story threads.

| Flag | Default | Action |
|------|---------|--------|
| *(none)* | — | Full run: embed + thread match + deactivate stale |
| `--embed-only` | — | Only embed, skip thread matching |
| `--dry-run` | — | Preview only |

**Key logic:** BAAI/bge-base-en-v1.5 (768d) embeddings for `title + description`. Thread matching: cosine > 0.70 → assign to existing thread, else LLM (gpt-4o-mini) groups unmatched into new threads. Centroid updated incrementally. Threads inactive after 7 days.

### `backfill_slugs.py` / `backfill_embeddings.py` (run-once)

Backfill scripts for existing articles. Slugs generated from titles with date-suffix collision handling. Embeddings + thread assignment for historical data.

### `generate_briefing.py`

Generates daily EN/KO finance briefings with TTS audio.

**Pipeline steps:** fetch_articles → filter_previously_briefed → fetch_crawl_map → fetch_llm_map → curate_articles (Gemini 2.5 Pro, 3 retries → Flash fallback) → assemble_articles (3 tiers: curated/standard/title-only) → build_briefing_prompt → generate_briefing (Gemini 2.5 Pro, temp 0.6, think 4K) → TTS → save_briefing_to_db → mark_articles_as_briefed.

**TTS providers:**
- EN: Google Cloud **Chirp 3 HD** (`en-US-Chirp3-HD-Alnilam`), 4K char chunks, 1.1x speed
- KO: **Gemini 2.5 Pro Preview TTS** (`Kore` voice), single pass

**CLI:**
```bash
python scripts/generate_briefing.py                          # Full run (EN+KO, TTS+DB)
python scripts/generate_briefing.py --date 2026-02-13        # Specific date
python scripts/generate_briefing.py --lang ko --skip-tts     # KO only, no audio
python scripts/generate_briefing.py --dry-run                # Read-only preview
python scripts/generate_briefing.py --skip-db                # Skip Supabase save
python scripts/generate_briefing.py --hours 48               # Lookback window
python scripts/generate_briefing.py --output-dir PATH        # Custom output dir
```

**Output:** `scripts/output/briefings/{date}/` — articles-input, briefing-{lang}.txt, audio-{lang}.mp3

---

## GitHub Actions Workflow

**File:** `.github/workflows/finance-pipeline.yml`
**Trigger:** Manual (`workflow_dispatch`) or daily at 6 AM US Eastern.
**Timezone Guard:** Two cron entries (`0 11 * * *` EST, `0 10 * * *` EDT). `tz-guard` job checks `date` in `America/New_York`.

### Full Run (`crawl_only=false`)

| Job | Timeout | Steps |
|-----|---------|-------|
| **tz-guard** | 1 min | Check if 6 AM Eastern |
| **ingest-search** | 60 min | `wsj_ingest.py` → `--export` → `wsj_to_google_news.py --delay-item 0.5 --delay-query 0.3` |
| **rank-resolve** | 45 min | `embedding_rank.py` → `resolve_ranked.py --delay 0.5 --update-db` → `wsj_ingest.py --mark-searched` |
| **crawl** | 180 min | `crawl_ranked.py --delay 2 --update-db` (with OPENAI_API_KEY) |
| **save-results** | 5 min | Merge artifacts → upsert to DB → `--mark-processed-from-db` → `--update-domain-status` |

### Crawl Only (`crawl_only=true`)

| Job | Timeout | Steps |
|-----|---------|-------|
| **tz-guard** | 1 min | Always passes for manual triggers |
| **crawl-from-db** | 180 min | `crawl_ranked.py --from-db --delay 2` |
| **save-results-crawl-only** | 5 min | `--mark-processed-from-db` → `--update-domain-status` |

**Manual Trigger Options:** `crawl_only=true` (skip search/rank), `skip_crawl=true` (test search/rank only).

**Optimizations:** `uv` package manager, HuggingFace model caching, Playwright chromium fresh per run, `continue-on-error` on crawl/search steps, artifact passing (7 days retention).

**Secrets:** `SUPABASE_URL`, `SUPABASE_KEY`, `GEMINI_API_KEY`

---

## Database Tables

> Full schema: [`docs/schema.md`](schema.md)

| Table | Purpose |
|-------|---------|
| `wsj_items` | WSJ RSS feed articles with feed_name, category, searched/processed/briefed flags, **slug**, **thread_id** |
| `wsj_crawl_results` | Crawled backup articles with content, embedding_score, crawl_status, relevance_flag |
| `wsj_domain_status` | Domain quality tracking — success_rate, weighted_score, auto-block status |
| `wsj_llm_analysis` | Gemini 2.5 Flash extracted metadata — entities, sentiment, summary, event_type, **importance**, **keywords** |
| `wsj_embeddings` | Article embeddings (BAAI/bge-base-en-v1.5, 768d) for semantic similarity |
| `wsj_story_threads` | Story thread clusters with centroids, member counts, active/inactive status |
| `wsj_briefings` | Generated briefing text + audio paths, upsert on (date, category) |
| `wsj_briefing_items` | Junction table linking briefings to source articles |

---

## Crawl Status Flow

| Status | Meaning | Set By | Next Action |
|--------|---------|--------|-------------|
| `pending` | Resolved URL, not yet crawled | resolve_ranked.py | Will be crawled |
| `success` | Crawled successfully | crawl_ranked.py | Check relevance_flag |
| `failed` | Crawl error (timeout, 404) | crawl_ranked.py | Try next backup |
| `error` | Unexpected exception | crawl_ranked.py | Try next backup |
| `garbage` | CSS/JS, paywall, repeated words | crawl_ranked.py | Try next backup |
| `skipped` | Another backup succeeded for this WSJ item | crawl_ranked.py | None |
| `resolve_failed` | Google News URL couldn't be resolved | resolve_ranked.py | Tracked for domain stats |

```
                      ┌─────────┐
                      │ pending │ ← Created by resolve
                      └────┬────┘
                           │
            ┌──────────────┼──────────────┐
            │              │              │
            ▼              ▼              ▼
      ┌─────────┐   ┌─────────┐   ┌─────────┐
      │ success │   │ failed  │   │ garbage │
      └────┬────┘   └─────────┘   └─────────┘
           │
  ┌────────┴────────┐
  │                 │
  ▼                 ▼
┌──────────┐  ┌──────────┐
│ flag=ok  │  │ flag=low │
└──────────┘  └──────────┘
  │                 │
  ▼                 ▼
Mark other      Try next backup
backups 'skipped'
```

---

## Quality & Relevance Checks

**Garbage Detection** (`crawl_ranked.py`):
- Empty content, repeated words (unique_ratio < 0.1), CSS/JS patterns, paywall markers, misc junk strings

**Quality Scoring** (`crawl_article.py`):
- `quality_score` (0-1): weighted sum of length, short_line_ratio, link_line_ratio, boilerplate_ratio
- Fail reasons: `TOO_SHORT` (<350 chars/<60 words), `TOO_LONG` (>50k), `LINK_HEAVY` (>30%), `MENU_HEAVY` (>55%), `BOILERPLATE_HEAVY` (>40%)
- `MAX_CONTENT_LENGTH = 20000` chars (truncated)

**Embedding Relevance**: Cosine similarity ≥ 0.25 → `relevance_flag='ok'`, else `'low'`

**LLM Verification** (Gemini 2.5 Flash): Accept if `is_same_event=true` OR `score >= 6`. Reject otherwise → domain `llm_fail_count` incremented.

---

## Environment Variables

```env
# Supabase (local dev / Mac Mini)
NEXT_PUBLIC_SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=

# Gemini (LLM analysis, embedding thread grouping, briefing generation)
GEMINI_API_KEY=

# Google Cloud TTS (service account — only needed for briefing audio)
GOOGLE_APPLICATION_CREDENTIALS=~/credentials/araverus-tts-sa.json

# GitHub Actions secrets
SUPABASE_URL=
SUPABASE_KEY=
GEMINI_API_KEY=
```

> **Note:** `OPENAI_API_KEY` is no longer used. All LLM calls migrated to Gemini. Mac Mini loads secrets from macOS Keychain via `load_env.sh`.

---

## Python Dependencies

| Package | Purpose |
|---------|---------|
| `httpx>=0.27.0` | HTTP client |
| `supabase>=2.0.0` | Supabase client |
| `python-dotenv>=1.0.0` | Environment variables |
| `sentence-transformers>=2.2.0` | Embedding models (all-MiniLM-L6-v2 for ranking, BAAI/bge-base-en-v1.5 for article embeddings) |
| `vecs>=0.4.0` | pgvector Python client (optional) |
| `numpy>=1.24.0` | Array operations |
| `trafilatura>=1.6.0` | Content extraction (preferred) |
| `lxml>=4.9.0` | XML parsing |
| `newspaper4k>=0.9.0` | Fast HTTP extraction + metadata |
| `crawl4ai>=0.4.0` | Browser-based crawling |
| `google-genai>=1.0.0` | Gemini API (LLM analysis, briefing, TTS) |

---

## CLI Quick Reference

```bash
cd scripts && source .venv/bin/activate

# --- Ingestion Pipeline ---
python wsj_ingest.py                                         # Ingest 6 WSJ RSS feeds
python wsj_ingest.py --export                                # Export unsearched → JSONL
python wsj_to_google_news.py --delay-item 2 --delay-query 1  # Search Google News
python embedding_rank.py --top-k 5 --min-score 0.3           # Rank by similarity
python resolve_ranked.py --delay 3 --update-db               # Resolve URLs → DB
python wsj_ingest.py --mark-searched output/wsj_items.jsonl   # Mark searched

# --- Crawling ---
python crawl_ranked.py --delay 3 --update-db                 # Crawl from JSONL
python crawl_ranked.py --from-db --delay 2                   # Crawl pending from DB
python crawl_article.py "https://example.com/article" stealth --save  # Single article

# --- Post-Process ---
python wsj_ingest.py --mark-processed-from-db                # Mark quality crawls processed
python wsj_ingest.py --update-domain-status                  # Update domain stats + auto-block
python wsj_ingest.py --retry-low-relevance                   # Retry low-relevance items
python wsj_ingest.py --stats                                 # Show DB statistics

# --- LLM ---
python llm_backfill.py --limit 10 --delay 0.5                # Backfill LLM analysis
python llm_backfill.py --dry-run                              # Preview only

# --- Briefing ---
python scripts/generate_briefing.py                           # Full run (EN+KO, TTS+DB)
python scripts/generate_briefing.py --dry-run                 # Read-only preview
python scripts/generate_briefing.py --lang ko --skip-tts      # KO only, no audio
python scripts/generate_briefing.py --date 2026-02-13         # Specific date
```

---

## Cost Summary

**Briefing generation per run (~$0.324):**

| Component | Est. Cost |
|-----------|-----------|
| Curation (Gemini Pro, 4K think) | ~$0.006 |
| EN Briefing (Gemini Pro, 4K think) | ~$0.051 |
| KO Briefing (Gemini Pro, 4K think) | ~$0.063 |
| EN TTS (Chirp 3 HD, ~9K chars) | ~$0.144 |
| KO TTS (Gemini TTS, ~6K chars) | ~$0.060 |

**Monthly:** ~$9.70/month (daily) or ~$7.10/month (weekdays only)

**LLM analysis (backfill):** ~$0.00016/article (Gemini 2.5 Flash)
