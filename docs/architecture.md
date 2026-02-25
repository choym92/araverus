<!-- Updated: 2026-02-25 -->
# Araverus — Project Architecture

Paul Cho's personal website, blog, and news briefing platform.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Framework | Next.js 15 (App Router), React 19, TypeScript 5 |
| Styling | Tailwind CSS 4 |
| Auth/DB/Storage | Supabase (Postgres + Auth + Storage) |
| Blog | MDX static generation (Git + Obsidian authoring) |
| Animations | Framer Motion, tsParticles |
| News Pipeline | Python scripts, GitHub Actions + Mac Mini (launchd) |
| AI/LLM | Gemini 2.5 Pro (briefing + TTS), GPT-4o-mini (analysis), Chirp 3 HD (EN TTS) |
| CI/CD | Vercel (frontend), GitHub Actions + Mac Mini (pipeline) |

---

## System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                           ARAVERUS                                  │
├─────────────────┬──────────────────────┬────────────────────────────┤
│   Website       │   Blog (MDX)         │   News Pipeline            │
│   (Next.js)     │                      │   (Python + GH Actions)    │
├─────────────────┼──────────────────────┼────────────────────────────┤
│ Landing page    │ content/blog/        │ scripts/                   │
│ /resume         │ ├── slug/index.mdx   │ ├── 1_wsj_ingest.py          │
│ /blog           │ └── public/blog/     │ ├── 6_crawl_ranked.py        │
│ /news           │                      │ ├── 8_generate_briefing.py   │
│ /admin          │ Categories:          │ └── ...9 scripts total     │
│ /login          │ Publication,Tutorial │                            │
│ /dashboard      │ Insight, Release     │ Daily at 6 AM ET           │
├─────────────────┴──────────────────────┴────────────────────────────┤
│                         Supabase                                     │
│  Auth · Postgres · Storage                                           │
│  Tables: user_profiles, blog_posts, blog_assets                      │
│  Tables: wsj_items, wsj_crawl_results, wsj_domain_status,           │
│          wsj_llm_analysis, wsj_briefings, wsj_briefing_items         │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Folder Structure

```
araverus/
├── src/
│   ├── middleware.ts            # Supabase session refresh (auth token renewal)
│   ├── app/                    # Next.js routes (server-first)
│   │   ├── page.tsx            # Landing page (hero + particles)
│   │   ├── blog/               # Blog list + [slug] pages
│   │   ├── news/               # News page (WSJ-style 3-col + audio briefing)
│   │   │   ├── page.tsx        # Server component (data fetching)
│   │   │   ├── layout.tsx      # Metadata
│   │   │   └── _components/    # NewsShell, BriefingPlayer, ArticleCard
│   │   ├── resume/             # Resume viewer (PDF embed)
│   │   ├── admin/              # Admin panel (role-gated)
│   │   ├── login/              # Auth page
│   │   ├── dashboard/          # Dashboard page (server-guarded)
│   │   ├── not-found.tsx       # Custom 404 page
│   │   ├── error.tsx           # Error boundary
│   │   ├── global-error.tsx    # Root error boundary
│   │   ├── sitemap.ts          # Dynamic sitemap generation
│   │   ├── robots.ts           # Robots.txt generation
│   │   ├── api/                # API routes
│   │   └── rss.xml/            # RSS feed generation
│   ├── components/             # Reusable UI (client only when needed)
│   │   ├── Hero.tsx            # Landing hero with particle bg
│   │   ├── ParticleBackground.tsx  # tsParticles (dynamic import, ssr:false)
│   │   ├── Header.tsx          # Site header
│   │   ├── Sidebar.tsx         # Collapsible nav sidebar
│   │   └── WaveGrid.tsx        # Wave grid animation
│   ├── hooks/                  # Custom React hooks
│   └── lib/                    # Services, utils, clients
│       ├── blog.service.ts     # Blog CRUD via Supabase
│       ├── news-service.ts     # News queries (NewsService class)
│       ├── authz.ts            # Server-side auth guards
│       ├── supabase-server.ts  # Server Supabase client
│       ├── supabase.ts         # Browser Supabase client
│       └── mdx.ts              # MDX utilities
├── content/blog/               # MDX blog posts (Git-managed)
├── scripts/                    # Python news pipeline
├── .github/workflows/          # GitHub Actions
├── docs/                       # Project documentation
└── public/                     # Static assets (images, resume.pdf, logo.svg, audio)
```

---

## Key Design Principles

1. **Server-first**: App Router uses Server Components by default. Client only for interaction/state/DOM APIs.
2. **Service layer**: DB logic goes through `BlogService`, `NewsService` etc., never direct in components.
3. **Role-based auth**: `user_profiles.role = 'admin'` (no hardcoded emails). Server-side guards via `authz.ts`.
4. **Tailwind only**: No inline styles except justified utility overrides.
5. **Edit over create**: Prefer modifying existing files over creating new ones.

---

## Three Main Systems

### 1. Landing Page & Website

- **Hero**: Particle constellation animation (tsParticles) with logo-shaped polygon mask
- **Design**: Monochrome, Playfair Display serif headlines, Inter body text
- **Pages**: /, /resume, /blog, /admin, /login, /dashboard, /news
- **A11y**: `prefers-reduced-motion` respected, WCAG AA contrast, keyboard navigation

### 2. Blog (MDX)

- **Source**: `content/blog/<slug>/index.mdx` with frontmatter metadata
- **Assets**: `public/blog/<slug>/` (images, covers)
- **Categories**: Publication, Tutorial, Insight, Release
- **Features**: Static generation, draft system, RSS feed at `/rss.xml`
- **Authoring**: Git + Obsidian → Push → Vercel auto-deploy
- **Guide**: See `docs/3-blog-writing-guide.md`

### 3. News Platform

- **Purpose**: Collect WSJ news, find free alternative sources, crawl content, verify relevance, generate EN/KO audio briefings
- **Pipeline**: Python scripts → GitHub Actions (daily 6 AM ET) + Mac Mini (launchd)
- **Frontend**: `/news` — WSJ-style 3-column layout with audio briefing player (EN/KO), category filtering
- **Backend docs**: See `docs/1-news-backend.md`
- **Frontend docs**: See `docs/2-news-frontend.md`

---

## Auth Flow

```
User → Supabase Auth (cookie/session)
  → Server Component → requireUser() or requireAdmin()
  → user_profiles.role check
  → Render or redirect
```

- `requireUser()`: Redirects to `/login` if not authenticated
- `requireAdmin()`: Requires `role = 'admin'`, returns 404 otherwise
- RLS policies enforce row-level access on blog_posts, blog_assets

---

## Environment Variables

```env
# Supabase
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=       # Server only, never expose

# Site
NEXT_PUBLIC_SITE_URL=http://localhost:3000

# News Pipeline (GitHub Actions / Mac Mini secrets)
SUPABASE_URL=
SUPABASE_KEY=
OPENAI_API_KEY=
GOOGLE_API_KEY=                  # Gemini (briefing + KO TTS)
GOOGLE_CLOUD_PROJECT=            # Chirp 3 HD (EN TTS)
```

---

## Commands

```bash
npm run dev       # Dev server
npm run build     # Production build (type check)
npm run lint      # ESLint
npm run test      # Vitest
npm start         # Production server
```

---

## Related Docs

| Doc | Content |
|-----|---------|
| `docs/schema.md` | All database tables |
| `docs/3-blog-writing-guide.md` | MDX blog authoring guide |
| `docs/1-news-backend.md` | News pipeline scripts, briefing generation |
| `docs/2-news-frontend.md` | `/news` page components, data flow, BriefingPlayer |
| `docs/claude-code-setup.md` | Skills, agents, hooks, automation reference |
| `CLAUDE.md` | Development rules and workflow |
