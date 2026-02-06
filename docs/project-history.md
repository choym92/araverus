<!-- Created: 2026-02-06 -->
# Araverus — Project History

Timeline of how the project evolved, from initial setup to current state.

---

## Aug 12, 2025 — Project Foundation

- Created araverus as a personal website with Next.js 15 + Supabase
- Set up role-based auth system (replaced email hardcoding with `user_profiles.role`)
- Created `CLAUDE.md` with context engineering for Claude Code automation
- Established `docs/cc/` for daily session tracking

## Aug 13, 2025 — Blog & Automation

- **MDX migration**: Moved blog from TipTap (database-driven) to MDX (static files)
  - Removed ~2,600 lines of TipTap code, added ~2,800 lines of MDX system
  - Zero runtime DB dependency, Git-based authoring
- Created 6 Claude Code workflow commands (agent-reviewer, gen-pr, eod, etc.)
- Set up MCP integration (Context7 + Serena)
- Built RSS feed at `/rss.xml`
- Blog categories: Publication, Tutorial, Insight, Release

## Aug 14, 2025 — Blog Polish

- Migrated from Geist to Inter font
- Added animated sidebar with smooth slide-in arrows
- Updated categories to Journal/Playbook (later reverted)
- Created shared blog layout eliminating header re-renders
- PR #2 merged to main (+1,501 / -268 lines)

## Aug 15, 2025 — Finance v1 (Python Quant Sidecar)

- Built first finance system: Python quant sidecar in `quant/` directory
- Yahoo Finance data fetching, RSI/SMA signal generation
- Supabase DB integration, GitHub Actions for daily updates
- `/finance` page with stock dashboard
- Fetched data for AAPL, MSFT, GOOGL, TSLA, NVDA (120 records)

## Aug 19, 2025 — Finance v1 Completion

- Completed M0 finance platform
- Live `/finance` tab displaying Yahoo Finance data

## Aug 29, 2025 — Pivot & Consolidation

- Consolidated overlapping trading systems in `quant/`
- Pivoted from "price prediction" to "market intelligence"
  - Insight: gathering data + LLM narrative > trying to beat the market
- Planned 30+ macro indicators, regime classification, daily email reports
- Created `quant/sp500_ml/` directory (later removed)

## Sep 3, 2025 — Clean Slate Reset

- **Complete project reset**: User wanted to start fresh
- Deleted entire `quant/` directory
- Disabled GitHub Actions automation
- Cleared all `.claude/commands/`
- Enhanced CLAUDE.md with structured workflows (PRD → Tasks → Implementation)
- Added MCP usage guidelines

## Late 2025 — Landing Page Redesign

- Redesigned landing page inspired by Google Antigravity
- Added tsParticles with logo-shaped polygon mask (three interlocking rings)
- Monochrome design, Playfair Display serif headlines
- Created `/resume` page with PDF viewer
- Two phases completed: core particle background + logo-shaped particles

## Dec 29, 2025 — Finance v2 Begins (WSJ TTS Briefing)

- Started new finance pipeline approach: WSJ RSS → free alternatives → TTS briefing
- Designed ticker-based system (NVDA/GOOG) with SEC EDGAR + Google News
- Created PRD with 8-table database schema
- Key pivot: Instead of stock prediction, build a daily news briefing system

## Jan 2026 — Finance Pipeline Implementation

- **Pivoted from ticker-based to WSJ RSS-based approach**
  - WSJ RSS feeds (6 categories) as source of truth instead of individual tickers
  - Google News search for free alternative articles
  - Hybrid crawling: newspaper4k (fast) → crawl4ai (browser fallback)
- Built 9 Python scripts, 4-job GitHub Actions workflow
- Implemented quality checks:
  - Garbage detection (CSS/JS, paywall, repeated words)
  - Embedding relevance scoring (`all-MiniLM-L6-v2`)
  - LLM relevance verification (GPT-4o-mini)
- Created 4 database tables: `wsj_items`, `wsj_crawl_results`, `wsj_domain_status`, `wsj_llm_analysis`
- Pipeline runs daily at 6 AM ET via GitHub Actions
- **Phase 1 complete**: Data collection pipeline fully operational

## Jan 28, 2026 — Documentation Consolidation

- Audited codebase vs task documentation
- Confirmed Python pipeline is the active track (TypeScript library abandoned)
- Archived completed task files
- Created briefing generation plan (Phase 2)

## Feb 6, 2026 — Docs Cleanup

- Consolidated 5 finance docs into single `architecture-finance-pipeline.md`
- Updated all architecture and schema docs
- Created project history (this file)

---

## Current State (Feb 2026)

**Working:**
- Website with landing page, blog, resume viewer
- Finance data collection pipeline (Phase 1 complete)
- Daily GitHub Actions at 6 AM ET

**Remaining:**
- **Phase 2**: Briefing script generation (`generate_briefing.py`)
- **Phase 3**: TTS audio + frontend player
- Landing page Phase 3: Below-the-fold sections (projects, blog previews)

---

## Key Pivots

| When | From | To | Why |
|------|------|----|-----|
| Aug 2025 | TipTap blog | MDX static blog | Zero DB dependency, Git authoring |
| Aug 2025 | Price prediction | Market intelligence | More realistic and valuable |
| Sep 2025 | Complex quant system | Clean slate | Start fresh, reduce complexity |
| Dec 2025 | Ticker-based finance | WSJ RSS-based | Broader coverage, simpler architecture |
