<!-- Created: 2026-02-10 -->
# Idea: Daily Finance Briefing + TTS

## What
Automated daily finance briefing — summarize the day's news into a 5-10 minute audio briefing from existing pipeline data, served on the website.

## Current State
- `wsj_items` — WSJ RSS articles (title, description, category)
- `wsj_crawl_results` — crawled articles with LLM relevance scoring
- GitHub Actions pipeline daily at 6 AM ET
- ~720 crawled articles/week, 100% crawl success rate

## Phase 1: Summary Generation
- Input: if quality crawl exists (relevance >= 0.6 OR llm_same_event) → crawled content; else → title + description
- Output: ~700-1400 word briefing (5-10 min TTS)
- Time window: yesterday afternoon + today morning (cronjob runs AM)
- Tracking: `briefed` flag on `wsj_items` + new `wsj_briefings` table
- All categories first, category-based later

## Phase 2: TTS
- Candidates: Google Cloud TTS, OpenAI TTS, ElevenLabs
- Evaluate: voice quality, cost, latency, max input length
- Tone: prototype multiple styles, pick after testing
- Language: English

## Phase 3: Storage & Delivery
- Audio: Supabase Storage bucket (5GB free, CDN, same client)
- Metadata: `wsj_briefings` table (date, text, audio_url, duration, category)
- Frontend: audio player component
- Optional: podcast RSS feed

## Data Flow
```
wsj_items + wsj_crawl_results
  → filter (unbriefed, time window, relevance)
  → LLM summarization → briefing text
  → TTS API → audio file
  → Supabase Storage → save URL to wsj_briefings
  → mark wsj_items.briefed = true
  → frontend player
```

## Open Questions
- Category-based: one combined or separate per category?
- Cost budget for TTS?
- Where in the website UI does the player live?
- Afternoon news → next day briefing, tracked via `briefed` flag

## Next Step
Jupyter notebook prototype: query data, test LLM summary prompts, test TTS APIs.
