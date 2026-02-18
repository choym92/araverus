<!-- Created: 2026-02-15 -->
# Idea: News Frontend — WSJ-Inspired Finance News Page

## Overview
Build `chopaul.com/news` as a standalone, WSJ-inspired news page that surfaces the existing finance pipeline data (articles, briefings, audio) in a professional editorial layout.

---

## Architecture Diagram

```mermaid
graph TB
    subgraph "Data Sources (Supabase)"
        DB_BRIEF[wsj_briefings<br/>briefing_text, audio_url, audio_duration]
        DB_ITEMS[wsj_items<br/>title, description, feed_name, subcategory]
        DB_CRAWL[wsj_crawl_results<br/>content, top_image, source]
        DB_LLM[wsj_llm_analysis<br/>summary, sentiment, tickers]
    end

    subgraph "Server Layer"
        SVC[NewsService<br/>src/lib/news-service.ts]
        PAGE[news/page.tsx<br/>Server Component]
        LAYOUT[news/layout.tsx<br/>Standalone Layout]
    end

    subgraph "Client Components"
        PLAYER[BriefingPlayer<br/>HTML5 Audio API]
        CARDS[ArticleCard<br/>featured / standard / compact]
        NAV[CategoryNav<br/>Markets, Tech, Economy...]
    end

    subgraph "Page Structure"
        MAST[Masthead<br/>'CHOPAUL NEWS']
        NAVBAR[Category Nav Bar]
        AUDIO[Audio Briefing Player]
        MAIN[Main Column 8/12]
        SIDE[Sidebar 4/12]
    end

    DB_BRIEF --> SVC
    DB_ITEMS --> SVC
    DB_CRAWL --> SVC
    DB_LLM --> SVC
    SVC --> PAGE
    PAGE --> LAYOUT

    LAYOUT --> MAST
    MAST --> NAVBAR
    NAVBAR --> AUDIO
    AUDIO --> PLAYER

    PAGE --> MAIN
    PAGE --> SIDE
    MAIN --> CARDS
    NAVBAR --> NAV
```

## Page Layout Wireframe

```mermaid
block-beta
    columns 12

    header["CHOPAUL NEWS — Masthead (Playfair Display serif)"]:12
    nav["Markets | Tech | Economy | World | Business | Politics        🔍"]:12
    player["🎧 Daily Briefing — Feb 15, 2026 | ▶ ━━━━━━━━━○━━━━ 3:42 / 5:15 | 1x"]:12

    space:12

    block:main:8
        featured["FEATURED STORY<br/>Large headline + image + summary"]
        divider1["─────────────────────────"]
        col1["Standard Card 1<br/>headline + summary"]
        col2["Standard Card 2<br/>headline + summary"]
        divider2["─────────────────────────"]
        section["TECHNOLOGY Section"]
        c1["Card"] c2["Card"] c3["Card"]
    end

    block:sidebar:4
        popular["MOST READ<br/>1. Headline...<br/>2. Headline...<br/>3. Headline..."]
        categories["BY CATEGORY<br/>filter chips"]
        excerpt["BRIEFING EXCERPT<br/>Today's summary text..."]
    end
```

## Component Tree

```mermaid
graph LR
    subgraph "news/layout.tsx (Server)"
        L[NewsLayout]
        L --> M[NewsMasthead]
        L --> CN[CategoryNav]
    end

    subgraph "news/page.tsx (Server)"
        P[NewsPage]
        P --> BP[BriefingPlayer 🔊<br/>Client Component]
        P --> FG[FeaturedGrid]
        P --> SB[Sidebar]

        FG --> AC1[ArticleCard featured]
        FG --> AC2[ArticleCard standard]
        FG --> AC3[ArticleCard compact]

        SB --> MR[MostRead]
        SB --> CF[CategoryFilter]
        SB --> BE[BriefingExcerpt]
    end
```

## Data Flow

```mermaid
sequenceDiagram
    participant User
    participant Page as news/page.tsx (Server)
    participant Svc as NewsService
    participant DB as Supabase

    User->>Page: GET /news?category=TECH
    Page->>Svc: getLatestBriefing()
    Svc->>DB: SELECT from wsj_briefings ORDER BY date DESC LIMIT 1
    DB-->>Svc: { briefing_text, audio_url, date }

    Page->>Svc: getNewsItems('TECH', 20)
    Svc->>DB: SELECT wsj_items JOIN wsj_crawl_results<br/>WHERE feed_name='TECH' AND processed=true
    DB-->>Svc: [{ title, description, top_image, source, ... }]

    Page-->>User: Render: Masthead + Player + Grid + Sidebar
```

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Audio player | Native HTML5 Audio API | Zero bundle cost, full UI control, simple needs |
| Layout | Standalone (not reusing site shell) | WSJ-style editorial experience, own masthead |
| Card style | WSJ editorial grid | Featured hero + 2-col grid + category sections |
| Styling | WSJ tokens in `@theme` (Tailwind v4) | Namespaced `news-*` colors, no global pollution |
| Fonts | Playfair Display (headlines) + Inter (UI) | Already loaded in root layout |
| Data | Server Components + NewsService | No client-side fetching, fast TTFB |
| Category filter | URL search params (`?category=TECH`) | Shareable, SEO-friendly, Server Component compatible |

## Implementation Steps

1. **News Layout + WSJ Design Tokens** — `news/layout.tsx` + globals.css `@theme` additions
2. **Audio Briefing Player** — Custom `BriefingPlayer` client component
3. **News Data Service** — `NewsService` class fetching from Supabase
4. **Article Card Component** — `ArticleCard` with 3 variants
5. **Page Assembly** — Wire up grid layout with real data
6. **Category Routing** — Filter by category via search params

## WSJ Design Reference
- Colors: midnight `#111`, coal `#333`, smoke `#ebebeb`, blue `#0274b6`, red `#e10000`, gold `#816d4d`
- Typography: 17px base, serif headlines, sans-serif UI/meta
- Layout: 1280px max-width, 12-col grid (8+4 sidebar), 1px border dividers everywhere
- Header: Large serif title → category nav (dark bar) → content
