<!-- Updated: 2026-02-25 -->
# TODO: Security & Website Completeness

Security audit and missing features identified 2026-02-25.

---

## Critical (즉시)

- [x] **Remove hardcoded admin email** — Replaced with server-side `user_profiles.role` check in `blog/page.tsx`.
- [ ] **Enable RLS on blog tables** — Deprioritized: blog is MDX-based, tables will be removed during Sanity CMS migration. See `auth-rls-migration.md` for SQL if needed.
- [ ] **Implement `sanitizeHtml()`** — Deprioritized: Sanity CMS migration planned.

## High (단기)

- [x] **Add `src/middleware.ts`** — Supabase session refresh via `@supabase/ssr` middleware.
- [x] **Add security headers** — via `next.config.ts` `headers()`: CSP (report-only), X-Frame-Options, HSTS, Referrer-Policy, Permissions-Policy.
- [x] **Restrict `images.remotePatterns`** — Removed `http` wildcard. `https` wildcard remains (news images). TODO: image proxy API.
- [x] **Remove `console.log(user.email)`** — Stripped PII from all auth console output.
- [x] **Dashboard server-side guard** — `requireUser()` in Server Component, client logic extracted to `DashboardClient.tsx`.

## Medium

- [x] **Add `sitemap.xml`** — `app/sitemap.ts` with static routes + dynamic blog posts, 1h revalidation.
- [x] **Add `robots.txt`** — `app/robots.ts`, disallows `/dashboard` and `/admin`.
- [x] **Add custom error pages** — `not-found.tsx` (404), `error.tsx` (boundary), `global-error.tsx` (root).
- [ ] **Validate slug in `mdx.ts`** — `getPostBySlug(slug)` uses `path.join(BLOG_DIR, slug, ...)` without filtering `../`. Add path traversal check.
- [ ] **Add `.env.example`** — Document required environment variables for onboarding.
- [ ] **Add RLS for pipeline tables** — `wsj_items`, `wsj_crawl_results`, etc. currently have no RLS.

## Low (있으면 좋은 것)

- [ ] **Analytics** — No tracking at all. Consider Vercel Analytics, Plausible, or Umami.
- [ ] **PWA manifest** — Icons exist (`icon-192.png`, `icon-512.png`) but no `manifest.json` → not installable.
- [ ] **Root page OpenGraph / Twitter Card** — Blog posts have OG tags, but root `/` and `/news` list pages don't.
- [ ] **Cookie consent / privacy policy** — Supabase sets auth cookies. May need consent banner for GDPR regions.
- [ ] **Skip-to-content link** — Accessibility best practice, missing from root layout.
- [ ] **`prefers-reduced-motion`** — 3D landing page (Three.js, particles) should respect motion preference.
- [ ] **Remove unused `zod` dependency** — In `package.json` but no validation schemas use it (or start using it for input validation).
