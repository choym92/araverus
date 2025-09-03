## FEATURE
Remove TipTap-based editor & DB posts. Add MDX-based static blog pipeline:
- Posts live in `content/blog/<slug>/index.mdx`
- Images in `public/blog/<slug>/*`
- App Router renders static pages (SSG/ISR)
- No in-browser writing; authoring via Obsidian + Git

## CONTEXT
- Admin = 1 (personal site), overkill features not needed
- Keep Next.js 15, Tailwind, existing site pages and auth (for other areas)
- Goal: $0 cost, fast, secure, simple (no DB/Supabase for blog)

## EXAMPLES / REFERENCES
- Follow `CLAUDE.md` (server-first, minimal edits) 
- Use `/blog/:slug` for posts; add `/blog` index list
- Drafts should not build or list (frontmatter: `draft: true`)
- MDX can embed custom components (e.g., <Figure />)

## DELIVERABLES
1) Content structure:
   - `content/blog/<slug>/index.mdx`
   - `public/blog/<slug>/cover.jpg` (and other images)
2) Rendering:
   - `src/app/blog/[slug]/page.tsx` (read MDX, render SSG, 404 drafts)
   - `src/app/blog/page.tsx` (list posts by date desc)
   - MDX helpers: `src/lib/mdx.ts`, components: `src/components/mdx/Figure.tsx`, `src/components/mdx/components.tsx`
3) Cleanup:
   - Remove TipTap UI/routes/pages and API that exist only for writing
   - Remove TipTap deps from package.json
   - Keep auth/admin for other areas; remove "write in browser" affordances
4) Docs:
   - `docs/automation-overview.md`에 블로그 소스/경로/배포 흐름 3줄 추가
   - `README` 또는 `docs/dev-notes.md`에 작성 규칙 5줄 추가

## SUCCESS CRITERIA
- `/blog` shows list (title/date/tags/cover)
- `/blog/<slug>` renders MDX with images (fast)
- Draft posts (`draft: true`) not built nor listed
- `npm run lint && npm run build` clean
- `git grep -i tiptap` → 결과 없음(삭제 완료)
- No runtime calls to Supabase for blog content

## VALIDATION
- Lint/Build
- Route smoke: open `/blog` & `/blog/<existing-sample>` 
- grep: `@tiptap`, `prosemirror`, old editor routes
- Changed files summary

## RISKS
- Route/SEO mapping: define redirects if legacy paths exist
- Repo size growth w/ many images → acceptable for now; can move to CDN later
- Remove code carefully: minimal edits, prefer deprecate→delete in same PR

## SLICE PLAN (order)
A) Add MDX pipeline & minimal sample post (no deletion yet)
B) Switch blog list/detail to MDX source
C) Remove TipTap UI/routes/deps (search+delete+verify)
D) Docs + redirects (if any)