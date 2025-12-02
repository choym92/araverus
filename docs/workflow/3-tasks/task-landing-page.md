<!-- Updated: 2025-12-01 -->
# Task List: Landing Page Redesign

Based on PRD: `docs/workflow/2_prds/prd-landing-page.md`

---

## Relevant Files

- `src/app/layout.tsx` - Add Playfair Display font import and CSS variable
- `src/app/globals.css` - Add `--font-serif` to `@theme inline` block
- `src/components/ParticleBackground.tsx` - **NEW** - Client component wrapping tsParticles with dynamic import
- `src/components/Hero.tsx` - Replace gradient background with particles, update content and CTAs
- `src/app/page.tsx` - Minor adjustments if needed for layout
- `src/app/resume/page.tsx` - **NEW** - Resume page with PDF viewer and download option
- `public/resume.pdf` - **NEW** - Resume PDF file
- `package.json` - Will be updated by npm install

### Notes

- All new components must use `'use client'` directive for browser-only features
- tsParticles requires `dynamic()` import with `ssr: false` for Next.js compatibility
- Test with `npm run build` after each major change to catch type errors early
- Resume opens as web page first, with download option available

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
