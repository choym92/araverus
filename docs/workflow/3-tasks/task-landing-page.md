<!-- Created: 2025-12-01 -->
# Task List: Landing Page Redesign

Based on PRD: `docs/workflow/2_prds/prd-landing-page.md`

---

## Relevant Files

- `src/app/layout.tsx` - Add Playfair Display font import and CSS variable
- `src/app/globals.css` - Add `--font-serif` to `@theme inline` block
- `src/components/ParticleBackground.tsx` - **NEW** - Client component wrapping tsParticles with dynamic import
- `src/components/Hero.tsx` - Replace gradient background with particles, update content and CTAs
- `src/app/page.tsx` - Minor adjustments if needed for layout
- `public/resume.pdf` - **NEW** - Resume PDF file for download
- `package.json` - Will be updated by npm install

### Notes

- All new components must use `'use client'` directive for browser-only features
- tsParticles requires `dynamic()` import with `ssr: false` for Next.js compatibility
- Test with `npm run build` after each major change to catch type errors early

---

## Tasks

- [x] 1.0 Setup Dependencies & Font Configuration
  - [x] 1.1 Install tsParticles packages: `npm install @tsparticles/react @tsparticles/slim`
  - [x] 1.2 Import `Playfair_Display` from `next/font/google` in `layout.tsx`
  - [x] 1.3 Configure Playfair Display with `variable: "--font-playfair"` and `style: ["normal", "italic"]`
  - [x] 1.4 Add `${playfair.variable}` to the body className in `layout.tsx`
  - [x] 1.5 Add `--font-serif: var(--font-playfair);` to `@theme inline` in `globals.css`
  - [x] 1.6 Run `npm run build` to verify no type errors

- [ ] 2.0 Create ParticleBackground Component
  - [ ] 2.1 Create new file `src/components/ParticleBackground.tsx` with `'use client'` directive
  - [ ] 2.2 Import `dynamic` from `next/dynamic` and set up lazy loading with `ssr: false`
  - [ ] 2.3 Import `loadSlim` from `@tsparticles/slim` for smaller bundle
  - [ ] 2.4 Create `particlesInit` callback using `useCallback` to initialize engine
  - [ ] 2.5 Create `options` config using `useMemo` with PRD particle settings:
    - Color: `#1A1A1A` (near-black)
    - Size: min 1, max 2 (very small)
    - Speed: 0.2 (extremely slow)
    - Links: enabled with opacity 0.1 (very faint)
    - Interactivity: disabled (calm, no mouse interaction)
  - [ ] 2.6 Accept `className` prop for positioning flexibility
  - [ ] 2.7 Run `npm run build` to verify component compiles

- [ ] 3.0 Update Hero Component with New Design
  - [ ] 3.1 Import `ParticleBackground` component and `Link` from `next/link`
  - [ ] 3.2 Remove existing gradient background divs (pink/purple/blue blobs)
  - [ ] 3.3 Add `ParticleBackground` inside a container div with `aria-hidden="true"`
  - [ ] 3.4 Add gradient mask overlay (`bg-gradient-to-r from-white via-white/80 to-transparent`) to fade particles on left
  - [ ] 3.5 Update headline to "Continual Learning" / "of Paul Cho" with `font-serif italic` styling
  - [ ] 3.6 Update subheadline to "Building AI systems, financial tools, and lifelong learning projects."
  - [ ] 3.7 Change content container from `text-center` to left-aligned
  - [ ] 3.8 Update Primary CTA: label "Resume", `href="/resume.pdf"`, add `download` attribute
  - [ ] 3.9 Update Secondary CTA: label "Finance", use `<Link href="/finance">`
  - [ ] 3.10 Add focus ring styles to both CTAs for keyboard accessibility

- [ ] 4.0 Apply Monochrome Styling & Layout Adjustments
  - [ ] 4.1 Update headline text color to `text-neutral-900` for primary, `text-neutral-600` for "of Paul Cho"
  - [ ] 4.2 Update subheadline to `text-neutral-500`
  - [ ] 4.3 Ensure hero card background is pure white (`bg-white`)
  - [ ] 4.4 Style Primary CTA: `bg-neutral-900 text-white hover:bg-neutral-800`
  - [ ] 4.5 Style Secondary CTA: `border border-neutral-300 bg-white text-neutral-900 hover:bg-neutral-50`
  - [ ] 4.6 Verify particle container is positioned to show particles on right/bottom (gradient mask handles left fade)
  - [ ] 4.7 Ensure content has `z-10` and particles have lower z-index

- [ ] 5.0 Add Resume PDF & Wire Up CTAs
  - [ ] 5.1 Add placeholder or actual `resume.pdf` file to `public/` directory
  - [ ] 5.2 Verify Resume CTA downloads file when clicked
  - [ ] 5.3 Verify Finance CTA navigates to `/finance` page
  - [ ] 5.4 Test both CTAs work on mobile and desktop

- [ ] 6.0 Accessibility & Reduced Motion Support
  - [ ] 6.1 Wrap `ParticleBackground` render in `{!reduceMotion && ...}` conditional
  - [ ] 6.2 Ensure `useReducedMotion()` hook is imported from framer-motion (already exists)
  - [ ] 6.3 Verify headline/background contrast meets WCAG AA (4.5:1 ratio) - near-black on white passes
  - [ ] 6.4 Confirm both CTAs have visible `:focus` states with `focus:ring-2 focus:ring-offset-2`
  - [ ] 6.5 Test keyboard navigation: Tab through CTAs, Enter to activate
  - [ ] 6.6 Test with browser "prefers-reduced-motion" setting enabled

- [ ] 7.0 Testing & Verification
  - [ ] 7.1 Run `npm run lint` and fix any issues
  - [ ] 7.2 Run `npm run build` and ensure no type errors
  - [ ] 7.3 Test in browser at localhost - verify particles render and animate slowly
  - [ ] 7.4 Test responsive design on mobile viewport (particles should still work, consider reducing count)
  - [ ] 7.5 Run Lighthouse audit and verify performance score > 90
  - [ ] 7.6 Verify sidebar and header functionality still works
  - [ ] 7.7 Check browser console for any errors or warnings
