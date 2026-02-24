<!-- Created: 2026-02-22 -->
# Audit: crawl_article.py

Phase 3 · Library · Article Crawler — 1103 LOC (post-refactor, was 1334, -17%)

---

## Why This Script Exists

The pipeline needs actual article text, not just URLs. This is the crawler that converts URLs into clean markdown content. Uses a hybrid approach: try newspaper4k (fast HTTP, ~0.5s) first, fall back to browser crawling via crawl4ai + Playwright (~5-30s) for JS-heavy or protected sites.

**Cost:** Free (local crawling). Runtime: 0.5-30s per article depending on extraction path.

---

## Architecture: Hybrid Extraction

```
URL → newspaper4k (fast, 0.5s)
  ├── Success → return content + metadata (authors, date, image)
  └── Fail/blocked domain → crawl4ai + Playwright (slow, 5-30s)
        ├── known domain → domain-specific CSS selector
        └── unknown domain → 2-pass fallback:
              Pass 1: generic pruning (excluded_tags)
              Pass 2: article CSS selectors (if Pass 1 < 500 chars)
        → trafilatura HTML extraction (preferred)
        → crawl4ai markdown cleaning (fallback)
        → section cutting → quality metrics → result
```

---

## CLI Commands (1, standalone testing)

| Argument | Default | Action |
|----------|---------|--------|
| `url` (positional) | required | URL to crawl |
| `mode` (positional) | undetected | basic, stealth, or undetected |
| `--save` | false | Save content to file |
| `--force` | false | Crawl even if domain is blocked |
| `--no-domain-selector` | false | Disable domain-specific CSS selectors |

Not called by `run_pipeline.sh` — this is a library imported by `6_crawl_ranked.py`.

---

## Key Functions

### Content Extraction
- `_try_newspaper4k()` — Fast HTTP extraction with metadata
- `_build_result()` — Standardized result from crawl4ai, tries trafilatura first
- `_extract_with_trafilatura()` — HTML → text using trafilatura (precision mode)
- `clean_article_content()` — Pattern-based markdown cleaning (100+ skip/stop patterns)
- `_deduplicate_content()` — Detect CSS selector duplication artifacts

### Quality Control
- `_compute_quality()` — Quality score: length, short_line_ratio, link_line_ratio, boilerplate_ratio
- `_cut_at_section_markers()` — Cut at "Related Articles", "References", etc.

### Crawling
- `crawl_article()` — Main entry point (async, used by 6_crawl_ranked.py)
- `_do_crawl()` → `_crawl_basic()` / `_crawl_stealth()` / `_crawl_undetected()`

### Domain Configuration
- `DOMAIN_CONFIG` — CSS selectors / excluded tags for 13 known domains
- `get_domain_config()` — Lookup by domain substring matching

---

## Data Flow

```
URL (from 6_crawl_ranked.py)
    │
    ├── Google News URL? → resolve via google_news_resolver (sync)
    │
    ├── Domain blocked? → return skip result
    │
    ├── newspaper4k → success? → return (fast path)
    │
    └── crawl4ai + Playwright (slow path)
        ├── known domain → CSS selector
        └── unknown domain → 2-pass fallback
            → trafilatura or crawl4ai markdown
            → section cutting → quality metrics
            │
            ▼ return dict
{success, status_code, title, markdown, markdown_length, domain, quality, extraction_method, ...}
```

---

## Shared Dependencies

| Module | What's Used | Why |
|--------|-------------|-----|
| `google_news_resolver` | `is_google_news_url()`, `resolve_google_news_url()` | URL resolution (was duplicated, now shared) |
| `domain_utils` | `is_blocked_domain()`, `load_blocked_domains()` | Domain filtering |
| `crawl4ai` | `AsyncWebCrawler`, `BrowserConfig`, `CrawlerRunConfig` | Browser-based crawling |
| `trafilatura` | `trafilatura.extract()` | HTML→text (optional, preferred) |
| `newspaper` (newspaper4k) | `newspaper.article()` | Fast HTTP extraction (optional) |
| `httpx` | `httpx.Client` | HTTP for Google News resolver |

---

## Refactoring Notes

### Done (this session)
- **Removed 220 LOC duplicate Google News resolver** — was copy of google_news_resolver.py
  - `is_google_news_url()`, `decode_google_news_url_direct()`, `fetch_google_news_batchexecute()`,
    `fetch_google_news_canonical()`, `resolve_google_news_url()` — all deleted
  - Now imports from `google_news_resolver` (sync, brief blocking in async context is fine)
- Manual argv parsing → `argparse` with positional url + mode
- Removed unused `import base64`, `import json` (were used by deleted resolver)
- Removed duplicate `sys.path.insert` in main() (now at module level)
- Updated Phase label: "Phase 3 · Library · Article Crawler"
- **1334 → 1103 LOC (-231 lines, -17%)**

### Not Changed
| Pattern | Why Kept |
|---------|----------|
| async architecture | crawl4ai is async, Playwright requires it |
| `DOMAIN_CONFIG` hardcoded map | 13 domains, DB would be overkill |
| `clean_article_content()` massive pattern lists | Working heuristics, site-specific |
| `get_domain()` (duplicate of `extract_domain`) | Internal to this module, tiny function |
| `trafilatura`/`newspaper4k` optional try/except imports | Correct pattern for optional deps |
| `_crawl_undetected` lazy imports | Correct — heavy crawl4ai adapters |
