# PRP: MDX-Based Static Blog Migration

## Objective
- Replace TipTap/DB-based blog with MDX static generation pipeline using Git+Obsidian authoring, eliminating runtime Supabase dependency for blog content.

## Scope
- In-scope: MDX rendering, file-based posts, draft filtering, custom components, TipTap removal
- Out-of-scope: Other admin features, auth system, non-blog Supabase usage

## Constraints & Global Rules
- Follow `CLAUDE.md` (server-first, role-based admin, minimal edits)
- Use existing patterns (services, hooks, folder conventions)
- No secrets in code; no destructive DB ops
- Keep Next.js 15, existing auth, site pages

## Codebase References (exact)
- `src/app/blog/[slug]/page.tsx:179-225` — ReactMarkdown pattern to extend for MDX
- `src/app/blog/[slug]/page.tsx:44-59` — SEO metadata generation pattern to keep
- `src/app/blog/page.tsx:369-517` — Blog list UI components to adapt
- `src/app/blog/page.tsx:77-91` — API fetch pattern to replace with filesystem
- `src/lib/blog.service.ts:127-159` — DB queries to replace with MDX parsing
- `src/app/admin/blog/write/page.tsx:6-50` — TipTap editor to remove
- `package.json:14-17` — TipTap packages to remove

## External References (URLs)
- Next.js MDX RSC: https://nextjs.org/docs/app/building-your-application/configuring/mdx#remote-mdx
- next-mdx-remote: https://github.com/hashicorp/next-mdx-remote#react-server-components-rsc--nextjs-app-directory-support
- Gray-matter frontmatter: https://github.com/jonschlinkert/gray-matter#usage
- Next.js generateStaticParams: https://nextjs.org/docs/app/api-reference/functions/generate-static-params

## Implementation Blueprint

### Pseudocode Flow
```typescript
// Blog List (SSG)
1. fs.readdir('content/blog/*')
2. Parse each index.mdx frontmatter
3. Filter drafts (frontmatter.draft !== true in production)
4. Filter by category if activeTab !== 'All' (frontmatter.category)
5. Sort by date desc
6. Render list with covers from public/blog/<slug>/

// Blog Detail (SSG)
1. fs.readFile(`content/blog/${slug}/index.mdx`)
2. Parse frontmatter + content
3. If draft && production → notFound()
4. Compile MDX with next-mdx-remote/rsc + custom components
5. Render with SEO metadata

// Frontmatter Schema
interface Frontmatter {
  title: string
  date: string
  category: 'Publication' | 'Insight' | 'Release' | 'Tutorial'
  tags?: string[]
  draft?: boolean
  coverImage?: string
  excerpt?: string
}
```

### File Plan
**Create:**
- `src/lib/mdx.ts` — getAllPosts(), getPostBySlug(), parseMDX() using fs + gray-matter
- `src/components/mdx/Figure.tsx` — Image with caption component
- `src/components/mdx/components.tsx` — MDX component mapping
- `content/blog/hello-world/index.mdx` — Sample post
- `public/blog/hello-world/cover.jpg` — Sample image

**Modify:**
- `src/app/blog/page.tsx` — Replace API call with getAllPosts()
- `src/app/blog/[slug]/page.tsx` — Replace BlogService with getPostBySlug(), use next-mdx-remote/rsc
- `package.json` — Remove @tiptap/*, add next-mdx-remote, gray-matter, remark-gfm, rehype-slug, rehype-autolink-headings
- ~~next.config.js~~ — No MDX loader needed with next-mdx-remote

**Remove:**
- `src/app/admin/blog/write/` — Entire editor directory
- `src/app/api/blog/` — All blog API routes
- `src/app/api/admin/` — Blog-related admin APIs
- `src/lib/blog.service.ts` — Blog CRUD methods (keep auth parts)

### Draft Policy
- **Development**: Drafts visible for preview
- **Production**: Drafts excluded from list, detail pages return 404

### Error Handling
- 404 for non-existent slugs or draft posts in production
- Graceful fallback for missing images (placeholder)
- Console warnings for malformed frontmatter

### Security/A11y Notes
- No runtime DB queries = no SQL injection risk
- Keep existing auth for other admin areas
- Ensure MDX components have proper ARIA labels
- Keyboard navigation for blog list grid

## Ordered Task List

### Phase A: Add MDX Pipeline (no deletion)
1) Install deps: `npm i next-mdx-remote gray-matter remark-gfm rehype-slug rehype-autolink-headings`
2) Create `src/lib/mdx.ts` with getAllPosts(category?), getPostBySlug(), getCategories()
3) Create `content/blog/hello-world/index.mdx` sample post with category: 'Tutorial'
4) Add `public/blog/hello-world/cover.jpg` sample image
5) Create `src/components/mdx/Figure.tsx` and `components.tsx`

### Phase B: Switch to MDX Source  
6) Update `src/app/blog/page.tsx` to use getAllPosts(activeTab !== 'All' ? activeTab : undefined)
7) Update `src/app/blog/[slug]/page.tsx` to use getPostBySlug() with next-mdx-remote/rsc
8) Add generateStaticParams() for SSG
9) Implement draft filtering logic (dev vs prod)
10) Keep existing filterTabs UI and wire to category filter

### Phase C: Remove TipTap
11) Delete `src/app/admin/blog/write/` directory
12) Delete `src/app/api/blog/` directory
13) Remove TipTap methods from `src/lib/blog.service.ts`
14) Uninstall TipTap packages from package.json
15) Remove unused imports and types

### Phase D: Documentation & Redirects
16) Update `docs/automation-overview.md` with MDX workflow (3 lines)
17) Add authoring guide to `docs/dev-notes.md` (5 lines + category usage)
18) Optional: Add redirects in next.config.js if legacy routes exist

## Validation Gates (must run)
- Syntax/Style: `npm run lint`
- Type Check: `npm run build`
- Package verification:
  - `npm ls | grep -i tiptap` → should error or empty
  - `git grep -iE "tiptap|prosemirror"` → no results
  - `git grep "app/api/blog"` → no results
- Route smoke:
  - Open `/blog` → should list all posts
  - Click 'Tutorial' tab → should filter to Tutorial category only
  - Open `/blog/hello-world` → should render MDX
  - Open `/blog/draft-post` → should 404 in production
- Optional redirects test if legacy routes exist

## Rollback Plan
- `git restore -SW src/ content/ public/ package.json`
- Or revert entire commit: `git reset --hard HEAD~1`
- Re-enable TipTap routes if needed via feature flag

## Risks & Gotchas
- **SEO Impact**: Ensure redirects from old DB slugs if different
- **Build Time**: Many MDX files may slow builds (use ISR if needed)
- **Image Sizes**: Repo growth with images (CDN migration later)
- **Draft Leaks**: Ensure NODE_ENV check for draft rendering
- **Migration**: Existing DB posts need manual MDX conversion

## Definition of Done
- All validation gates pass
- `/blog` shows MDX posts with covers
- Category tabs (Publication/Tutorial/Insight/Release) filter posts correctly
- `/blog/<slug>` renders MDX with custom components  
- Draft posts hidden in production, visible in dev
- TipTap completely removed (grep + npm ls verified)
- Docs updated with authoring workflow including category usage

## Confidence
- Score (1–10): **9**
- Why:
  - Clear migration path with phased approach
  - Using battle-tested next-mdx-remote for RSC
  - Low risk with gradual removal strategy
  - Draft handling explicitly defined