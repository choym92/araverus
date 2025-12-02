<!-- Updated: 2025-12-02 (Phase 2 complete) -->
# Task List: Landing Page Redesign

Based on PRD: `docs/workflow/2-prds/prd-landing-page.md`

---

## Relevant Files

### Phase 1 (Complete)
- `src/app/layout.tsx` - Playfair Display font import and CSS variable
- `src/app/globals.css` - `--font-serif` in `@theme inline` block
- `src/components/ParticleBackground.tsx` - Client component wrapping tsParticles
- `src/components/Hero.tsx` - Hero with particles, content and CTAs
- `src/app/resume/page.tsx` - Resume page with PDF viewer
- `public/resume.pdf` - Resume PDF file *(user to provide)*

### Phase 2 (Logo Particles)
- `public/logo.svg` - **NEW** - SVG version of logo for polygon mask
- `src/components/ParticleBackground.tsx` - **UPDATE** - Add polygon mask plugin
- `src/components/LogoParticles.tsx` - **NEW** (optional) - Dedicated logo particle component
- `package.json` - Add `@tsparticles/plugin-polygon-mask`

### Notes

- All new components must use `'use client'` directive for browser-only features
- tsParticles requires `dynamic()` import with `ssr: false` for Next.js compatibility
- Test with `npm run build` after each major change to catch type errors early
- Resume opens as web page first, with download option available
- **Polygon Mask requires SVG with valid `<path>` elements** - PNG won't work directly
- SVG must be served from same origin (place in `/public` folder)

---

## Tasks

- [x] 1.0 Setup Dependencies & Font Configuration
  - [x] 1.1 Install tsParticles packages: `npm install @tsparticles/react @tsparticles/slim`
  - [x] 1.2 Import `Playfair_Display` from `next/font/google` in `layout.tsx`
  - [x] 1.3 Configure Playfair Display with `variable: "--font-playfair"` and `style: ["normal", "italic"]`
  - [x] 1.4 Add `${playfair.variable}` to the body className in `layout.tsx`
  - [x] 1.5 Add `--font-serif: var(--font-playfair);` to `@theme inline` in `globals.css`
  - [x] 1.6 Run `npm run build` to verify no type errors

- [x] 2.0 Create ParticleBackground Component
  - [x] 2.1 Create new file `src/components/ParticleBackground.tsx` with `'use client'` directive
  - [x] 2.2 Import `dynamic` from `next/dynamic` and set up lazy loading with `ssr: false`
  - [x] 2.3 Import `loadSlim` from `@tsparticles/slim` for smaller bundle
  - [x] 2.4 Create `particlesInit` callback using `useCallback` to initialize engine
  - [x] 2.5 Create `options` config using `useMemo` with PRD particle settings:
    - Color: `#1A1A1A` (near-black)
    - Size: min 1, max 2 (very small)
    - Speed: 0.2 (extremely slow)
    - Links: enabled with opacity 0.1 (very faint)
    - Interactivity: disabled (calm, no mouse interaction)
  - [x] 2.6 Accept `className` prop for positioning flexibility
  - [x] 2.7 Run `npm run build` to verify component compiles

- [x] 3.0 Update Hero Component with New Design
  - [x] 3.1 Import `ParticleBackground` component and `Link` from `next/link`
  - [x] 3.2 Remove existing gradient background divs (pink/purple/blue blobs)
  - [x] 3.3 Add `ParticleBackground` inside container with `aria-hidden="true"` and `pointer-events-none`
  - [x] 3.4 Add gradient mask overlay (`bg-gradient-to-r from-white via-white/80 to-transparent`) to fade particles on left
  - [x] 3.5 Update headline to "Continual Learning" / "of Paul Cho" with `font-serif italic` styling
  - [x] 3.6 Ensure Hero has single `<h1>` for SEO & a11y (headline should be h1)
  - [x] 3.7 Update subheadline to "Building AI systems, financial tools, and lifelong learning projects."
  - [x] 3.8 Change content container from `text-center` to left-aligned
  - [x] 3.9 Update Primary CTA: label "Resume", `<Link href="/resume">` (opens resume page, not direct download)
  - [x] 3.10 Update Secondary CTA: label "Finance", `<Link href="/finance">`
  - [x] 3.11 Add `aria-label` to CTAs for screen reader clarity (e.g., "View resume" / "Open finance tools")
  - [x] 3.12 Add focus ring styles to both CTAs for keyboard accessibility

- [x] 4.0 Apply Monochrome Styling & Layout Adjustments
  - [x] 4.1 Update headline text color to `text-neutral-900` for primary, `text-neutral-600` for "of Paul Cho"
  - [x] 4.2 Update subheadline to `text-neutral-500`
  - [x] 4.3 Ensure hero card background is pure white (`bg-white`)
  - [x] 4.4 Verify page background vs hero card contrast (e.g., `bg-neutral-50` page vs `bg-white` card)
  - [x] 4.5 Style Primary CTA: `bg-neutral-900 text-white hover:bg-neutral-800`
  - [x] 4.6 Style Secondary CTA: `border border-neutral-300 bg-white text-neutral-900 hover:bg-neutral-50`
  - [x] 4.7 ParticleBackground container: `absolute inset-0 -z-10 pointer-events-none`
  - [x] 4.8 Content wrapper: `relative z-10`

- [x] 5.0 Create Resume Page & Wire Up CTAs
  - [ ] 5.1 Add `resume.pdf` file to `public/` directory *(User action required)*
  - [x] 5.2 Create `src/app/resume/page.tsx` - displays PDF in web viewer (iframe or embed)
  - [x] 5.3 Add "Download PDF" button on resume page (`<a href="/resume.pdf" download>`)
  - [ ] 5.4 Verify `/resume.pdf` returns 200 (not 404) *(Requires 5.1)*
  - [x] 5.5 Verify Resume CTA navigates to `/resume` page
  - [x] 5.6 Verify Finance CTA navigates to `/finance` page
  - [ ] 5.7 Test both CTAs work on mobile and desktop *(Manual testing)*

- [x] 6.0 Accessibility & Reduced Motion Support
  - [x] 6.1 Wrap `ParticleBackground` render in `{!reduceMotion && ...}` conditional
  - [x] 6.2 Ensure `useReducedMotion()` hook is imported from framer-motion (already exists)
  - [x] 6.3 Verify headline/background contrast meets WCAG AA (4.5:1 ratio) - near-black on white passes
  - [x] 6.4 Confirm both CTAs have visible `:focus` states with `focus:ring-2 focus:ring-offset-2`
  - [x] 6.5 Verify CTAs have `aria-label` or SR-only text for screen readers
  - [ ] 6.6 Test keyboard navigation: Tab through CTAs, Enter to activate *(Manual testing)*
  - [ ] 6.7 Test with browser "prefers-reduced-motion" setting enabled *(Manual testing)*

- [x] 7.0 Testing & Verification
  - [x] 7.1 Run `npm run lint` and fix any issues
  - [x] 7.2 Run `npm run build` and ensure no type errors
  - [ ] 7.3 Test in browser at localhost - verify particles render and animate slowly *(Manual testing)*
  - [ ] 7.4 Test responsive design on mobile viewport *(Manual testing)*
  - [ ] 7.5 Check mobile particle performance, reduce count if needed (60-80 instead of 120) *(Manual testing)*
  - [ ] 7.6 Cross-browser test: Chrome, Safari, Firefox - verify Hero and particles work *(Manual testing)*
  - [ ] 7.7 Run Lighthouse audit and verify performance score > 90 *(Manual testing)*
  - [ ] 7.8 Verify sidebar and header functionality still works *(Manual testing)*
  - [ ] 7.9 Check browser console for any errors or warnings *(Manual testing)*

---

## Phase 2: Logo-Shaped Particle Effect (Antigravity-style)

**Goal:** Transform the particle background into a logo-shaped particle formation, inspired by Google Antigravity's effect where particles form and gravitate towards the logo shape.

**Reference:** [Google Antigravity](https://antigravity.google/product) - particles form the product shape on the right side

### Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Plugin | `@tsparticles/plugin-polygon-mask` | Spawns particles along SVG path - creates logo outline effect |
| Logo Format | SVG with `<path>` elements | Required by polygon mask; PNG won't work |
| Particle Placement | Right side of hero card | Text on left, logo particles on right (like Antigravity) |
| Movement | Subtle drift along path | Particles stay in formation with gentle movement |

---

- [x] 8.0 Prepare Logo SVG for Polygon Mask
  - [x] 8.1 Obtain or create SVG version of logo (three interlocking rings)
    - Option A: Export from original design tool ✓ (Used this approach)
    - Option B: Trace PNG to SVG using vectorization tool
    - Option C: Manually recreate as SVG paths
  - [x] 8.2 Optimize SVG structure for polygon mask:
    - ✓ Uses `<path>` elements (3 paths for the three rings)
    - ✓ viewBox: `0 0 1024 544`
    - ✓ Removed unnecessary attributes (opacity, stroke, enable-background, etc.)
    - ✓ Changed fill to `#1A1A1A` (design system color)
  - [x] 8.3 Validate SVG path data:
    - ✓ All 3 paths end with `z` (closed)
    - ✓ Build passes with no errors
  - [x] 8.4 Save optimized SVG to `public/logo.svg` ✓
  - [ ] 8.5 Test SVG loads correctly: verify `/logo.svg` returns 200 *(Manual test in browser)*

- [x] 9.0 Install & Configure Polygon Mask Plugin
  - [x] 9.1 Install plugin: `npm install @tsparticles/plugin-polygon-mask` ✓
  - [x] 9.2 Update `ParticleBackground.tsx` imports ✓
  - [x] 9.3 Load plugin in `initParticlesEngine` ✓
  - [x] 9.4 Run `npm run build` to verify no type errors ✓

- [x] 10.0 Configure Polygon Mask Options
  - [x] 10.1 **VERIFY API first**: Property name is `polygon` ✓
  - [x] 10.2 Add polygon mask configuration ✓
    - `polygon.enable: true`, `url: '/logo.svg'`, `type: 'inline'`
    - `position: { x: 65, y: 50 }` (right side)
    - `scale: 0.5`, `inline.arrangement: 'equidistant'`
    - `move: { radius: 5, type: 'radius' }`
  - [x] 10.3 **Understand the distinction** ✓
  - [x] 10.4 Adjust particle settings for logo effect ✓
    - Particle count: 100, Size: 1-2px
    - Links: distance 30, opacity 0.15
  - [x] 10.5 Position logo on right side of hero ✓
  - [ ] 10.6 Test polygon mask renders correctly in browser *(Manual testing)*

- [x] 11.0 Fine-Tune Particle Behavior
  - [x] 11.1 Configure movement ✓ (`move.type: 'radius'`, `move.radius: 5`)
  - [x] 11.2 Adjust particle density ✓ (`inline.arrangement: 'equidistant'`)
  - [x] 11.3 Configure links ✓ (enabled with low opacity 0.15 for constellation effect)
  - [ ] 11.4 Test particle behavior matches Antigravity reference *(Manual testing)*

- [x] 12.0 Layout Integration & Responsive Design
  - [x] 12.1 Update Hero component layout ✓
    - Gradient mask preserved for text readability
    - Logo particles positioned on right (x: 65%)
  - [x] 12.2 **Defensive checks** ✓
    - `<h1>` semantic structure preserved
    - `pointer-events-none` on particle container
    - `aria-hidden="true"` on particle container
  - [x] 12.3 Handle responsive sizing ✓
    - Desktop: Full logo particles visible
    - Mobile: Particles hidden (`hidden md:block`)
  - [ ] 12.4 Test hero layout at all breakpoints *(Manual testing)*
  - [ ] 12.5 Verify text remains readable with logo particles *(Manual testing)*

- [x] 13.0 Performance & Accessibility
  - [x] 13.1 Optimize for mobile ✓ (particles hidden on mobile via `hidden md:block`)
  - [ ] 13.2 Test performance on low-end devices *(Manual testing)*
  - [x] 13.3 `prefers-reduced-motion` works ✓ (`useReducedMotion()` hides particles)
  - [ ] 13.4 Verify no FOUC during load *(Manual testing)*
  - [ ] 13.5 Run Lighthouse audit - target performance score > 85 *(Manual testing)*

- [x] 14.0 Polish & Final Testing
  - [x] 14.1 Fine-tune timing and easing ✓ (speed: 0.3, move.radius: 5)
  - [x] 14.2 Colors configured ✓ (#1A1A1A matching design system)
  - [ ] 14.3 Cross-browser test: Chrome, Safari, Firefox *(Manual testing)*
  - [ ] 14.4 Test on real mobile devices *(Manual testing)*
  - [ ] 14.5 Check console for any errors or warnings *(Manual testing)*
  - [ ] 14.6 Update PRD with final particle configuration *(Optional)*
  - [x] 14.7 Commit all changes with descriptive message ✓

---

## Alternative Approaches (If Polygon Mask Doesn't Work)

If polygon mask proves too complex or doesn't achieve desired effect:

### Option B: Canvas Mask Plugin
- Uses raster image (PNG) instead of SVG
- Particles fill non-transparent areas of image
- Install: `npm install @tsparticles/plugin-canvas-mask`
- Simpler setup but less precise than polygon mask

### Option C: Absorbers Plugin (Gravity Effect)
- Particles get pulled toward a central point
- Good for "black hole" or "vortex" effect
- Won't form exact logo shape, but creates gravitational pull
- Install: `npm install @tsparticles/plugin-absorbers`

### Option D: Custom Implementation
- Sample logo image pixels to get coordinate points
- Use those coordinates as particle spawn positions
- More control but requires custom code
- Reference: Canvas pixel sampling approach
