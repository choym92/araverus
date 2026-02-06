<!-- Updated: 2026-02-06 -->
# Araverus — Project Architecture

Paul Cho's personal website, blog, and finance briefing platform.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Framework | Next.js 15 (App Router), React 19, TypeScript 5 |
| Styling | Tailwind CSS 4 |
| Auth/DB/Storage | Supabase (Postgres + Auth + Storage) |
| Blog | MDX static generation (Git + Obsidian authoring) |
| Animations | Framer Motion, tsParticles |
| Finance Pipeline | Python scripts, GitHub Actions |
| AI/LLM | OpenAI (GPT-4o-mini for analysis + briefing) |
| CI/CD | Vercel (frontend), GitHub Actions (finance pipeline) |

---

## System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                           ARAVERUS                                   │
├─────────────────┬──────────────────────┬────────────────────────────┤
│   Website       │   Blog (MDX)         │   Finance Pipeline         │
│   (Next.js)     │                      │   (Python + GH Actions)    │
├─────────────────┼──────────────────────┼────────────────────────────┤
│ Landing page    │ content/blog/        │ scripts/                   │
│ /resume         │ ├── slug/index.mdx   │ ├── wsj_ingest.py          │
│ /finance        │ └── public/blog/     │ ├── crawl_ranked.py        │
│ /blog           │                      │ ├── llm_analysis.py        │
│ /admin          │ Categories:          │ └── ...9 scripts total     │
│ /login          │ Publication,Tutorial │                            │
│ /news           │ Insight, Release     │ Daily at 6 AM ET           │
├─────────────────┴──────────────────────┴────────────────────────────┤
│                         Supabase                                     │
│  Auth · Postgres · Storage                                           │
│  Tables: user_profiles, blog_posts, blog_assets                      │
│  Tables: wsj_items, wsj_crawl_results, wsj_domain_status,           │
│          wsj_llm_analysis, briefs, audio_assets                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Folder Structure

```
araverus/
├── src/
│   ├── app/                    # Next.js routes (server-first)
│   │   ├── page.tsx            # Landing page (hero + particles)
│   │   ├── blog/               # Blog list + [slug] pages
│   │   ├── finance/            # Finance briefing page
│   │   ├── resume/             # Resume viewer (PDF embed)
│   │   ├── admin/              # Admin panel (role-gated)
│   │   ├── login/              # Auth page
│   │   ├── news/               # News page
│   │   ├── api/                # API routes
│   │   └── rss.xml/            # RSS feed generation
│   ├── components/             # Reusable UI (client only when needed)
│   │   ├── Hero.tsx            # Landing hero with particle bg
│   │   ├── ParticleBackground.tsx  # tsParticles (dynamic import, ssr:false)
│   │   ├── Sidebar.tsx         # Collapsible nav sidebar
│   │   └── ...
│   ├── hooks/                  # Custom React hooks
│   └── lib/                    # Services, utils, clients
│       ├── blog.service.ts     # Blog CRUD via Supabase
│       ├── authz.ts            # Server-side auth guards
│       └── finance/            # (Deprecated TS library, unused)
├── content/blog/               # MDX blog posts (Git-managed)
├── scripts/                    # Python finance pipeline
├── .github/workflows/          # GitHub Actions
├── supabase/migrations/        # DB migrations
├── docs/                       # Project documentation
└── public/                     # Static assets (images, resume.pdf, logo.svg)
```

---

## Key Design Principles

1. **Server-first**: App Router uses Server Components by default. Client only for interaction/state/DOM APIs.
2. **Service layer**: DB logic goes through `BlogService` etc., never direct in components.
3. **Role-based auth**: `user_profiles.role = 'admin'` (no hardcoded emails). Server-side guards via `authz.ts`.
4. **Tailwind only**: No inline styles except justified utility overrides.
5. **Edit over create**: Prefer modifying existing files over creating new ones.

---

## Three Main Systems

### 1. Landing Page & Website

- **Hero**: Particle constellation animation (tsParticles) with logo-shaped polygon mask
- **Design**: Monochrome, Playfair Display serif headlines, Inter body text
- **Pages**: /, /resume, /finance, /blog, /admin, /login, /news
- **A11y**: `prefers-reduced-motion` respected, WCAG AA contrast, keyboard navigation

### 2. Blog (MDX)

- **Source**: `content/blog/<slug>/index.mdx` with frontmatter metadata
- **Assets**: `public/blog/<slug>/` (images, covers)
- **Categories**: Publication, Tutorial, Insight, Release
- **Features**: Static generation, draft system, RSS feed at `/rss.xml`
- **Authoring**: Git + Obsidian → Push → Vercel auto-deploy
- **Guide**: See `docs/blog-writing-guide.md`

### 3. Finance TTS Briefing Pipeline

- **Purpose**: Collect WSJ news, find free alternative sources, crawl content, verify relevance, generate TTS briefing scripts
- **Stack**: Python scripts → GitHub Actions (daily 6 AM ET) → Supabase
- **Full docs**: See `docs/architecture-finance-pipeline.md`

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
- Guide: See `docs/auth-migration-guide.md`

---

## Environment Variables

```env
# Supabase
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=       # Server only, never expose

# Site
NEXT_PUBLIC_SITE_URL=http://localhost:3000

# Finance Pipeline (GitHub Actions secrets)
SUPABASE_URL=
SUPABASE_KEY=
OPENAI_API_KEY=
```

---

## Commands

```bash
npm run dev       # Dev server
npm run build     # Production build (type check)
npm run lint      # ESLint
npm start         # Production server
```

---

## Related Docs

| Doc | Content |
|-----|---------|
| `docs/architecture-finance-pipeline.md` | Finance pipeline deep dive |
| `docs/schema.md` | All database tables |
| `docs/blog-writing-guide.md` | MDX blog authoring guide |
| `docs/auth-migration-guide.md` | Auth migration reference |
| `docs/project-history.md` | Project evolution timeline |
| `CLAUDE.md` | Development rules and workflow |
