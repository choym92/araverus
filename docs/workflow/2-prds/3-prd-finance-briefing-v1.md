<!-- Created: 2026-02-10 -->
# PRD: Finance Briefing Generator v1

## Goal
Prototype a daily finance briefing generator in Jupyter notebook. Compare two LLM summarization approaches, evaluate output quality, and establish the pipeline for automated briefing generation.

## Background
- Pipeline collects ~200+ WSJ articles/day across 6 categories
- ~45% have quality crawl results (content + LLM analysis)
- `wsj_briefings` and `wsj_briefing_items` tables ready in Supabase
- Existing data: `wsj_items`, `wsj_crawl_results`, `wsj_llm_analysis`

## Scope: Notebook Only
This PRD covers the Jupyter notebook prototype. Not production automation, not TTS, not frontend.

## Requirements

### 1. Data Query
- Fetch today's articles from `wsj_items` (yesterday afternoon + today morning)
- Join with `wsj_crawl_results` and `wsj_llm_analysis`
- Filter quality crawls: `relevance_score >= 0.6 OR llm_same_event = true`
- Exclude already-briefed items via `wsj_briefing_items` junction table

### 2. Input Assembly
Two approaches to compare:

**Option A — Metadata only**
- All articles: `wsj_items.title` + `wsj_items.description`
- Quality crawl articles add: `llm_analysis.summary` + `key_entities` + `key_numbers`

**Option B — Full content**
- All articles: `wsj_items.title` + `wsj_items.description`
- Quality crawl articles add: `crawl_results.content` (first 800 chars) + `key_entities` + `key_numbers`
- No `llm_summary` (LLM reads content directly, avoids anchoring bias)

### 3. LLM Briefing Generation
- Input: assembled article set (15-30 articles)
- Output: ~700-1400 word narrative briefing (5-10 min TTS length)
- Language: English
- Model: test with Claude and/or GPT-4o
- Prompt: instruct to synthesize, group by theme, highlight key numbers

### 4. Comparison
- Run both A and B on the same article set
- Compare: quality, depth, accuracy of numbers/entities, readability
- Measure: token usage, cost, latency

### 5. Save to DB
- Save winning briefing to `wsj_briefings`
- Insert article mappings to `wsj_briefing_items`
- Record `model` and `item_count`

## Notebook Structure

```
Cell 1: Setup & imports
Cell 2: Query today's articles from Supabase
Cell 3: Join with crawl results + LLM analysis
Cell 4: Filter & assemble inputs (A vs B)
Cell 5: Generate briefing — Option A (metadata)
Cell 6: Generate briefing — Option B (content)
Cell 7: Side-by-side comparison
Cell 8: Save to Supabase (wsj_briefings + wsj_briefing_items)
```

## Data Flow
```
wsj_items (today, unbriefed)
  + wsj_crawl_results (quality crawl filter)
  + wsj_llm_analysis (summary, entities, numbers)
  → assemble input (A or B)
  → LLM generate briefing
  → wsj_briefings (insert)
  → wsj_briefing_items (insert junction)
```

## Out of Scope
- TTS audio generation (Phase 2)
- Category-based briefings (future — start with ALL)
- Frontend player (Phase 3)
- Production automation / GitHub Actions integration
- Prompt optimization (iterate after v1 baseline)

## Success Criteria
- Notebook produces a readable 5-10 min briefing from today's data
- Clear winner between A and B (or understanding of tradeoffs)
- Briefing saved to `wsj_briefings` with correct junction table entries
