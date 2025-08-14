# PRP: Modern Blog Article UI v1

## Objective
Transform `/blog/[slug]` article pages with modern typography, card layout, and enhanced code blocks to improve readability and professional appearance.

## Scope
- **IN**: Blog post detail pages (`/blog/[slug]/*`)
- **IN**: `app/blog/[slug]/layout.tsx` creation (3-column grid/card/background shell)
- **IN**: Typography theme, card layout, code syntax highlighting
- **IN**: Responsive grid structure for future ToC
- **OUT**: Blog listing page, homepage, admin pages
- **OUT**: Dark mode, comments, search, image lightbox

## Constraints
- Server-first rendering (MDX processing stays server-side)
- Minimal edits to existing files
- Blog-scoped CSS (no global style pollution)
- All styles must be under `.blog` wrapper scope using `:where()` for low specificity
- Tailwind 4 with `@theme inline` (no config file)
- Tailwind v4 loads plugins via `@plugin` directive in CSS, fallback to custom `.blog :where(.prose)` styles if plugin fails
- Must pass `npm run lint` and `npm run build`

## Codebase Context

### Current Implementation
- **File**: `src/app/blog/[slug]/page.tsx` (L1-217)
  - Uses `next-mdx-remote/rsc` for MDX rendering
  - Has `rehype-highlight` with GitHub Dark theme
  - Basic prose classes without Typography plugin
  - Simple max-width container layout
  - Will focus on MDX render + header meta only after refactor

- **File**: `src/app/globals.css` (L1-27)
  - Tailwind 4 with `@theme inline` directive
  - CSS variables for theming
  - No blog-specific styles
  - Will add `@plugin` directive for Typography

- **File**: `package.json` (L11-29)
  - Has `highlight.js` for code highlighting
  - Missing `@tailwindcss/typography` plugin
  - Missing `rehype-pretty-code` and `shiki`

## External References
- [Tailwind Typography Plugin](https://tailwindcss.com/docs/typography-plugin) - Prose styling
- [Rehype Pretty Code](https://rehype-pretty-code.netlify.app/) - Enhanced code blocks
- [Tailwind v4 Plugins](https://tailwindcss.com/docs/v4-beta#plugins) - Plugin usage in v4

## Implementation Blueprint

### Phase A: Install Dependencies
```bash
npm install @tailwindcss/typography rehype-pretty-code shiki
```

### Phase B: Create Layout Shell
1. **File**: `src/app/blog/[slug]/layout.tsx` (NEW)
   - 3-column grid structure (ToC | Content | Rail)
   - Gradient background wrapper
   - Card container with shadow and backdrop blur
   - `.blog` class wrapper for CSS scoping

### Phase C: Add Typography Plugin & Theme CSS
1. **File**: `src/app/globals.css`
   - Add `@plugin "@tailwindcss/typography"` after `@import "tailwindcss"`
   - Add `.blog :where(.prose)` theme variables for low specificity
   - Define heading scales with clamp() for responsive sizing
   - Add code block dark theme styles
   - Include mobile-friendly scrolling styles

### Phase D: Update Blog Post Page
1. **File**: `src/app/blog/[slug]/page.tsx`
   - Remove layout wrapper code (moved to layout.tsx)
   - Focus on MDX content and header meta only
   - **Remove** `rehype-highlight` completely
   - Add `rehype-pretty-code` as single code highlighter
   - Configure Shiki with github-dark theme

### Phase E: Verify MDX Components
1. **File**: `src/components/mdx/components.tsx`
   - Test compatibility with new prose theme
   - Adjust spacing if needed
   - Ensure Figure component works with new styles

## File Plan

### CREATE: `src/app/blog/[slug]/layout.tsx`
- **Lines**: ~25 lines
- **Purpose**: Grid structure, card wrapper, gradient background
- **Key elements**: 3-column responsive grid, sticky ToC area, shadow card

### MODIFY: `package.json`
- **Lines**: Add 3 dependencies to "dependencies" section
- **Changes**: 
  ```json
  "@tailwindcss/typography": "^0.5.10",
  "rehype-pretty-code": "^0.10.2", 
  "shiki": "^0.14.7"
  ```

### MODIFY: `src/app/globals.css`
- **Lines**: After L1, add plugin directive
- **Lines**: After L27, add ~45 lines of blog styles
- **Changes**: 
  - `@plugin "@tailwindcss/typography"`
  - `.blog :where(.prose)` theme variables
  - Responsive heading scales
  - Code block styles

### MODIFY: `src/app/blog/[slug]/page.tsx`
- **Lines**: L79-94 (remove outer wrapper)
- **Lines**: L151-152 (update prose classes)
- **Lines**: L156-165 (replace rehype pipeline)
- **Changes**: 
  - Remove gradient/card wrapper (handled by layout)
  - Remove `rehype-highlight` import and usage
  - Add `rehype-pretty-code` with Shiki config

## Ordered Task List

1. [ ] Install npm packages (@tailwindcss/typography, rehype-pretty-code, shiki)
2. [ ] Create new `src/app/blog/[slug]/layout.tsx` with grid structure
3. [ ] Add `@plugin` directive to globals.css
4. [ ] Add `.blog :where(.prose)` theme CSS with responsive scales
5. [ ] Add code block dark theme styles with proper border radius
6. [ ] Update page.tsx: Remove outer wrapper elements
7. [ ] Update page.tsx: Remove rehype-highlight imports
8. [ ] Update page.tsx: Add rehype-pretty-code with Shiki configuration
9. [ ] Update page.tsx: Adjust prose classes for new theme
10. [ ] Test render with `/blog/claude-code-automation`
11. [ ] Verify MDX components compatibility
12. [ ] Run validation gates

## Validation Gates

### Syntax & Build
```bash
npm run lint
npm run build
```

### Visual Testing
- Load `/blog/claude-code-automation` in browser
- Verify heading hierarchy and spacing
- Check code block syntax highlighting with line numbers
- Test horizontal scroll on mobile for code blocks
- Verify card shadow and gradient background
- Ensure mobile code block horizontal scroll doesn't interfere with vertical scroll

### Responsive Testing
- iPhone 15 (390px): Single column, smooth scroll, readable code
- iPad (768px): Content centered, good padding
- Desktop (1440px): 3-column grid visible, ToC area ready

### Accessibility & Performance
- Lighthouse Accessibility: Target ≥ 95
- CLS (Cumulative Layout Shift): Target < 0.02
- Focus ring visibility on interactive elements
- Link contrast ratio meets WCAG AA standards
- Mobile code blocks scroll smoothly without vertical interference

## Rollback Plan
```bash
# Revert all changes
git restore -SW src/app/blog/[slug]/page.tsx src/app/blog/[slug]/layout.tsx src/app/globals.css package.json package-lock.json

# Remove layout file if created
rm -f src/app/blog/[slug]/layout.tsx

# Remove added dependencies
npm uninstall @tailwindcss/typography rehype-pretty-code shiki

# Reinstall to clean state
npm install
```

## Risks & Mitigations

### Risk: Tailwind v4 @plugin directive compatibility
- **Mitigation**: Plugin loads via CSS `@plugin` directive in v4
- **Fallback**: If plugin fails, use custom `.blog :where(.prose)` styles (included in CSS)
- **Test**: Check build logs for plugin loading errors

### Risk: rehype-highlight and rehype-pretty-code conflict
- **Mitigation**: Complete removal of rehype-highlight before adding rehype-pretty-code
- **Check**: Ensure no duplicate tokenization in output HTML

### Risk: Shiki build time increase
- **Mitigation**: Start with single theme (github-dark) and minimal language set
- **Monitor**: Check build time before/after
- **Fallback**: Immediate rollback to rehype-highlight if >5s increase

### Risk: CSS specificity conflicts
- **Mitigation**: `.blog` scoping with `:where()` for low specificity
- **Check**: Verify other pages unaffected, test cascade issues

### Risk: Layout/Page split causes hydration issues
- **Mitigation**: Layout handles only visual shell, page handles dynamic content
- **Test**: Check browser console for hydration warnings

## Definition of Done
- [ ] Typography scales properly (h1: 44-56px, h2: 29-36px, body: 16-17px)
- [ ] Code blocks have dark theme with syntax highlighting and line numbers
- [ ] Card layout with gradient background renders correctly
- [ ] Mobile horizontal scroll works for wide code blocks without vertical interference
- [ ] All prose elements (lists, quotes, tables) styled consistently
- [ ] Focus indicators and link contrast meet WCAG AA standards
- [ ] Layout.tsx successfully wraps page content with grid structure
- [ ] Lighthouse a11y ≥ 95, CLS < 0.02
- [ ] `npm run lint` passes
- [ ] `npm run build` succeeds
- [ ] No visual regressions on other pages
- [ ] No hydration errors in console

## Implementation Order
Recommended sequence for minimal risk:
1. **A** - Install packages (reversible)
2. **B** - Create layout.tsx (new file, no conflicts)
3. **C** - Add CSS styles (scoped, safe)
4. **D** - Update page.tsx (careful with rehype swap)
5. **E** - Verify components (testing only)

## Confidence Score: 9.5/10
Very high confidence due to:
- Clear separation of concerns (layout vs page)
- Safe CSS scoping with `:where()`
- Proven plugin patterns for Tailwind v4
- Clean rollback strategy
- Isolated changes to single route