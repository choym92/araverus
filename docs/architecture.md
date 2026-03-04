<!-- Updated: 2026-03-04 -->
# Araverus — Project Architecture

Financial intelligence platform powered by AI, machine learning, and neural networks.

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
| Analytics | Vercel Analytics + Google Analytics (GA4: G-ZF8PZ75W1H, property "Araverus") |
| CI/CD | Vercel (frontend), GitHub Actions + Mac Mini (pipeline) |

---

## System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                           ARAVERUS                                  │
├─────────────────┬──────────────────────────────────────────────────┤
│   Website       │   News Pipeline                                    │
│   (Next.js)     │   (Python + GH Actions)                            │
├─────────────────┼──────────────────────────────────────────────────┤
│ / → redirect    │ scripts/                                           │
│ /news           │ ├── 1_wsj_ingest.py                               │
│ /login          │ ├── 6_crawl_ranked.py                             │
│ /api/revalidate │ ├── 8_generate_briefing.py                        │
│                 │ └── ...9 scripts total                            │
│                 │ Daily at 6 AM ET                                  │
├─────────────────┴──────────────────────────────────────────────────┤
│                         Supabase                                     │
│  Auth · Postgres · Storage                                           │
│  Tables: user_profiles                                               │
│  Tables: wsj_items, wsj_crawl_results, wsj_domain_status,           │
│          wsj_llm_analysis, wsj_briefings, wsj_briefing_items,       │
│          wsj_story_threads, wsj_embeddings                           │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Folder Structure

```
araverus/
├── src/
│   ├── middleware.ts            # Supabase session refresh (auth token renewal)
│   ├── app/                    # Next.js routes (server-first)
│   │   ├── page.tsx            # Root redirect → /news
│   │   ├── news/               # News page (WSJ-style 3-col + audio briefing)
│   │   │   ├── page.tsx        # Server component (data fetching)
│   │   │   ├── layout.tsx      # Metadata
│   │   │   ├── [slug]/         # Article detail page
│   │   │   ├── c/[category]/   # Category-specific routes (ISR cached)
│   │   │   └── _components/    # NewsShell, BriefingPlayer, ArticleCard
│   │   ├── auth/callback/      # OAuth callback (server-side PKCE code exchange)
│   │   ├── login/              # Auth page (Google OAuth sign-in)
│   │   ├── not-found.tsx       # Custom 404 page
│   │   ├── error.tsx           # Error boundary
│   │   ├── global-error.tsx    # Root error boundary
│   │   ├── sitemap.ts          # Dynamic sitemap generation
│   │   ├── robots.ts           # Robots.txt generation
│   │   ├── api/                # API routes
│   │   │   ├── revalidate/    # On-demand ISR (pipeline → cache bust)
│   │   │   └── news/          # Pagination API for load-more
│   │   ├── rss.xml/            # RSS feed generation
│   │   └── podcast.xml/        # Podcast feed generation
│   ├── components/             # Reusable UI (client only when needed)
│   │   ├── Header.tsx          # Site header (logo-header.svg)
│   │   ├── Sidebar.tsx         # Collapsible nav sidebar (News only)
│   │   └── (archived)          # Hero, ParticleBackground, WaveGrid → archive/
│   ├── hooks/                  # Custom React hooks
│   └── lib/                    # Services, utils, clients
│       ├── news-service.ts     # News queries (NewsService class)
│       ├── authz.ts            # Server-side auth guards
│       ├── supabase-server.ts  # Server Supabase client
│       └── supabase.ts         # Browser Supabase client
├── scripts/                    # Python news pipeline
├── archive/                    # Archived: blog, landing, resume, admin, blog libs
├── .github/workflows/          # GitHub Actions
├── docs/                       # Project documentation
└── public/                     # Static assets (images, logo.svg, logo-header.svg, audio)
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

### 1. Website & Authentication

- **Home**: `/` redirects to `/news` (Server component redirect)
- **Pages**: /news, /login, /auth/callback
- **Header**: Araverus logo (logo-header.svg, SVG inline, transparent bg). Logged-in state shows "Welcome, [first name]" (text only, no avatar). Dropdown shows full name + email + sign out.
- **Sidebar**: Navigation (News only, no Home link)
- **A11y**: WCAG AA contrast, keyboard navigation, focus states
- **Auth**: Google OAuth with Supabase (role-based admin access)

### 2. News Platform

- **Purpose**: Collect WSJ news, find free alternative sources, crawl content, verify relevance, thread related stories, generate EN/KO audio briefings
- **Pipeline**: Python scripts → GitHub Actions (daily 6 AM ET) + Mac Mini (launchd)
- **Frontend**: `/news` — WSJ-style 3-column layout with audio briefing player (EN/KO), category filtering, story threading
- **Feeds**: RSS at `/rss.xml`, Podcast RSS at `/podcast.xml` (branded as Araverus)
- **Backend docs**: See `docs/1-news-backend.md`
- **Frontend docs**: See `docs/2-news-frontend.md`

---

## Auth Flow

```
User → /login or Header "Log in" button
  → signInWithOAuth({ provider: 'google', redirectTo: NEXT_PUBLIC_SITE_URL/auth/callback })
  → Supabase Auth → Google OAuth consent screen
  → Google redirects → Supabase callback (PKCE)
  → Supabase redirects → /auth/callback (server-side route handler)
  → exchangeCodeForSession() → session cookie set
  → Redirect to / (logged in)
```

**Provider**: Google OAuth (GCP project: `atlantean-depth-339623`)
**PKCE flow**: Code exchange handled server-side in `/auth/callback/route.ts` (not client-side)
**Redirect URL**: Always uses `NEXT_PUBLIC_SITE_URL` (not `window.location.origin`) to avoid Vercel Deployment Protection on preview URLs
**Auto profile**: `on_auth_user_created` trigger creates `user_profiles` row on first login with Google name + avatar
**GCP OAuth client config**:
- Authorized Redirect URIs: `https://obqjrbwguutgtsjaivrh.supabase.co/auth/v1/callback` (required by Supabase)
- Authorized JavaScript Origins: not needed (Supabase uses server-side redirect, not client-side JS)
- Consent screen shows `supabase.co` domain because redirect URI goes through Supabase — changeable only via Supabase Custom Domain (Pro plan)

- `requireUser()`: Redirects to `/login` if not authenticated
- `requireAdmin()`: Requires `role = 'admin'` in `user_profiles`, returns 404 otherwise
- `user_profiles.id` = `auth.users.id` (direct FK, no separate `user_id`)
- RLS policies enforce row-level access on user_profiles, blog_posts, blog_assets

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

# Pipeline → Vercel cache revalidation
REVALIDATION_SECRET=             # Shared secret for /api/revalidate
SITE_URL=https://araverus.com     # Production URL (default)
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
