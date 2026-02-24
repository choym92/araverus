<!-- Created: 2026-02-23 -->
# Project Roadmap

## Current State

The news pipeline is the most substantial piece of engineering in this project:
- Python ~10,000 LOC, 5-phase pipeline (ingest → search → rank → crawl → briefing)
- Wilson score auto-domain blocking, 17 failure classifications
- EN/KO bilingual audio with CTC sentence alignment
- ~$11/month operational cost

But visitors see a blog with 3 posts. The hidden 90% of the iceberg is invisible.

**Core problem**: Not a feature gap — a visibility gap.

---

## Phase 1: Technical Debt Cleanup

**Goal**: Solid foundation before building more.

| Item | Problem | Fix |
|------|---------|-----|
| Audio storage | Local WAV fallback when `audio_url` is null | Supabase Storage upload in pipeline |
| Hardcoded dates | `page.tsx` reads local files with `fs/promises` | DB-driven, remove local file hacks |
| JSONB double-stringify | Data layer workaround | Fix at insert time |
| Test coverage | 0 tests for pipeline | Core path validation: output schema, service layer |

**Done when**: Pipeline runs end-to-end with no local file dependencies. Audio plays from Supabase Storage.

---

## Phase 2: Stories Tab

**Goal**: Ship the most differentiated feature.

**Why Stories before Search**:
- `wsj_story_threads` data already exists in DB
- Cross-day narrative timelines are something even NYT/WSJ don't do well
- "How this issue evolved over the past week" is genuinely valuable UX
- Search can be added quickly later (pgvector infra ready)

**Scope**:
- Timeline view showing thread evolution across days
- Thread detail page with all member articles
- Heat score visualization

---

## Phase 3: Make the Invisible Visible

**Goal**: Highest ROI — show what's already built.

### Blog Content

3 posts is not enough. But the stories are already there:

| Topic | Angle |
|-------|-------|
| "Building an AI News Pipeline for $11/month" | 5-phase architecture, cost optimization |
| "Auto-Managing News Source Quality with Wilson Score" | Domain blocking system |
| "Bilingual TTS Briefing System" | CTC alignment, chapter extraction |

### "How This Works" on /news

Add a pipeline architecture section to the news page so visitors immediately see "this person built this" — not just a news list.

---

## Numbering Convention

When new feature areas are added, continue the docs numbering:
- **1.x** — News backend (pipeline, search, threading, embedding)
- **2.x** — News frontend
- **3.x** — Blog
- **4.x** — Next feature area
