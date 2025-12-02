<!-- Updated: 2025-12-01 -->
# PRD: Landing Page Redesign

## Overview

**Goal:** Transform the current placeholder landing page into a polished, professional personal website inspired by [Google Antigravity](https://antigravity.google/product) — featuring a particle constellation animation, monochrome design, and clean typography.

**Tagline:** "Continual Learning of Paul Cho"

---

## Design Principles

> These principles guide all design decisions. When in doubt, refer back here.

1. **Calm, minimal, and Google-like** — Never flashy, never "gamer aesthetic"
2. **White space is a feature** — Text on screen should not exceed 2-3 lines
3. **Animation is texture, not spectacle** — Background particles exist to add subtle depth, not to impress
4. **Content-first** — The message matters more than the effects

---

## Current State

The existing landing page (`src/app/page.tsx` + `src/components/Hero.tsx`) includes:
- Header with logo + "Paul Cho" branding
- Collapsible sidebar (Home, Blog, Finance, Contact)
- Hero card with soft gradient background (pink/purple/blue)
- Placeholder text: "Undergoing Construction...."
- Two CTAs: "Learn more" + "Get started" (non-functional)
- Framer Motion animations (fade-in, floating gradient blobs)

**What we keep:**
- Overall layout structure (header, sidebar, main content area)
- Framer Motion for UI transitions
- Responsive design patterns

**What we change:**
- Hero design and content
- Color scheme → monochrome
- Background → particle animation
- Typography styling

---

## Design Requirements

### 1. Color Scheme: Monochrome

| Element | Color |
|---------|-------|
| Background | `#FFFFFF` (white) |
| Primary text | `#1A1A1A` (near-black) |
| Secondary text | `#6B7280` (gray-500) |
| Particles/dots | `#1A1A1A` (near-black) — subtle, small |
| Connecting lines | `rgba(26, 26, 26, 0.1)` — very faint or disabled |
| CTAs | Black primary, outlined secondary |

### 2. Typography

| Element | Style |
|---------|-------|
| Headline | Large (4xl-6xl), light/normal weight, italic serif for emphasis |
| Subheadline | Medium (lg-xl), normal weight, muted color |
| Body | Base size, Inter font (already configured) |

**Font choice:** Serif italic for headline (like Antigravity's editorial style), Inter for everything else.

### 3. Layout Structure

```
┌─────────────────────────────────────────────────────────┐
│ [Logo] Paul Cho    ☰        [nav items...]    [Login]   │  ← Header
├─────────────────────────────────────────────────────────┤
│         │                                               │
│ Sidebar │   ┌─────────────────────────────────────┐     │
│         │   │                                     │     │
│  Home   │   │  Continual Learning        · · ·    │     │
│  Blog   │   │     of Paul Cho          ·   ·   ·  │     │
│ Finance │   │                        · · · · · ·  │     │
│ Contact │   │  [subheadline]       · · · · · · ·  │     │
│         │   │                    · · · · · · · ·  │     │
│         │   │  [CTA] [CTA]     · · · · · · · · ·  │     │
│         │   │                · · · · · · · · · ·  │     │
│         │   └─────────────────────────────────────┘     │
│         │                                               │
└─────────────────────────────────────────────────────────┘
```

**Key layout note:** Particles are concentrated on the **right/bottom curved region** only. The left side where text lives stays clean and uncluttered.

### 4. Particle Animation Specification

**Inspiration:** Google Antigravity's dot field effect

#### Antigravity-Specific Tuning

Unlike typical constellation effects, Antigravity's particles are:

- **Dust/mist feel, not geometric** — Links are very faint or disabled entirely
- **Extremely slow movement** — Barely noticeable even after 30-60 seconds of watching
- **Localized placement** — Not full-screen; particles exist only in a curved region (right/bottom of hero), keeping text area clean
- **Small and dense** — Many tiny dots rather than fewer large ones

#### Particle Config (tsParticles)

```typescript
{
  particles: {
    number: { value: 120, density: { enable: true, area: 800 } },
    color: { value: "#1A1A1A" },
    shape: { type: "circle" },
    size: { value: { min: 1, max: 2 } },  // Very small
    opacity: { value: { min: 0.2, max: 0.6 } },
    links: {
      enable: true,        // Start with links, experiment with false in Phase 2
      distance: 100,
      color: "#1A1A1A",
      opacity: 0.1,        // Very faint
      width: 0.5
    },
    move: {
      enable: true,
      speed: 0.2,          // Extremely slow (0.2-0.5)
      direction: "none",
      random: true,
      straight: false,
      outModes: { default: "out" }
    }
  },
  interactivity: {
    events: {
      onHover: { enable: false },  // Keep it calm, no mouse interaction initially
      onClick: { enable: false }
    }
  },
  detectRetina: true
}
```

#### Technical Approach

**Recommended:** tsParticles with `@tsparticles/react` + `@tsparticles/slim`

```typescript
// src/components/ParticleBackground.tsx
'use client';

import dynamic from "next/dynamic";

const Particles = dynamic(
  () => import("@tsparticles/react").then((m) => m.default),
  { ssr: false }
);

// ... component implementation
```

### 5. Hero Content

**Headline:**
```
Continual Learning
of Paul Cho
```

**Subheadline:**
```
Building AI systems, financial tools, and lifelong learning projects.
```

**CTAs (defined):**

| CTA | Label | Action | Style |
|-----|-------|--------|-------|
| Primary | "Resume" | Navigate to `/resume` page (web viewer with download option) | Black filled, rounded |
| Secondary | "Finance" | Navigate to `/finance` | Outlined, rounded |

---

## Technical Implementation

### Dependencies to Add

```bash
npm install @tsparticles/react @tsparticles/slim
```

### Files to Modify

| File | Changes |
|------|---------|
| `src/components/Hero.tsx` | Replace gradient background with particle canvas, update content |
| `src/components/ParticleBackground.tsx` | **NEW** — Client component with dynamic import |
| `src/app/page.tsx` | Minor adjustments if needed |
| `tailwind.config.ts` | Add serif font (e.g., `Playfair Display` or `Lora`) for headline |

### Component Architecture

```
Hero.tsx (Client component)
├── ParticleBackground.tsx (Client - dynamic import, ssr: false)
│   └── <Particles /> from @tsparticles/react
├── Content container (left-aligned, z-index above particles)
│   ├── Headline (serif italic)
│   ├── Subheadline
│   └── CTAs
└── Particle region mask (CSS clip-path for right/bottom area)
```

### Dynamic Import Pattern

```typescript
// ParticleBackground.tsx - MUST use dynamic import for Next.js
'use client';

import { useCallback, useMemo } from "react";
import dynamic from "next/dynamic";
import type { Engine } from "@tsparticles/engine";
import { loadSlim } from "@tsparticles/slim";

const Particles = dynamic(
  () => import("@tsparticles/react").then((m) => m.default),
  { ssr: false, loading: () => null }
);

export default function ParticleBackground() {
  const particlesInit = useCallback(async (engine: Engine) => {
    await loadSlim(engine);
  }, []);

  const options = useMemo(() => ({
    // ... particle config from above
  }), []);

  return <Particles id="tsparticles" init={particlesInit} options={options} />;
}
```

### Performance Considerations

1. **Dynamic import with `ssr: false`** — Critical for Next.js
2. **Reduce particle count on mobile** — 60-80 instead of 120
3. **Use `loadSlim`** — Smaller bundle than `loadFull`
4. **Respect `prefers-reduced-motion`** — Disable animation entirely
5. **Z-index layering** — Particles at `z-index: 0`, content at `z-index: 10`
6. **Memoize options** — Prevent unnecessary re-renders

---

## Acceptance Criteria

### Core Functionality
- [ ] Particle animation renders smoothly (60fps)
- [ ] Particles appear only in right/bottom region (text area clean)
- [ ] Extremely slow, barely perceptible movement
- [ ] Links very faint or disabled (dust/mist feel)
- [ ] Monochrome color scheme applied
- [ ] Headline displays "Continual Learning of Paul Cho" in serif italic
- [ ] Subheadline displays descriptor text
- [ ] Primary CTA ("Resume") links to resume PDF or `/resume` page
- [ ] Secondary CTA ("Finance") links to `/finance`

### Technical Quality
- [ ] `ParticleBackground` uses dynamic import with `ssr: false` (code splitting)
- [ ] Build passes with no type errors
- [ ] Lighthouse performance score > 90

### Responsive & Accessibility
- [ ] Responsive on mobile, tablet, desktop
- [ ] `prefers-reduced-motion` respected (animation disabled if set)
- [ ] Hero text/background contrast meets WCAG AA (4.5:1 ratio)
- [ ] Buttons are keyboard-focusable with visible `:hover`/`:focus` states
- [ ] Sidebar and header functionality preserved

---

## Decisions Made

1. **Serif font:** Playfair Display
2. **Particle color:** Near-black (`#1A1A1A`)
3. **Resume format:** PDF download

---

## Timeline & Phases

### Phase 1: Core Implementation
- [ ] Add tsParticles dependencies
- [ ] Create `ParticleBackground.tsx` with dynamic import
- [ ] Update `Hero.tsx` with new content and layout
- [ ] Apply monochrome styling
- [ ] Add serif font for headline

### Phase 2: Polish & Experimentation
- [ ] Fine-tune particle speed (target: barely perceptible)
- [ ] Experiment with `links.enable: false` for pure dust effect
- [ ] Implement curved region mask for particle placement
- [ ] Add subtle mouse interaction (optional — test if it feels calm)
- [ ] Responsive adjustments (reduce particles on mobile)
- [ ] Performance optimization

### Phase 3: Content & Sections (Future)
- [ ] Add resume (PDF in `/public` or dedicated page)
- [ ] Add sections below hero:
  - **Recent Projects** — 3 project cards
  - **Latest Writing** — 3 blog post previews
  - **Now** — One paragraph on current focus
- [ ] Scroll-triggered fade-in animations for sections

---

## References

- [Google Antigravity](https://antigravity.google/product) — Design inspiration
- [tsParticles GitHub](https://github.com/tsparticles/tsparticles) — Particle library
- [tsParticles React](https://github.com/tsparticles/react) — React integration
- [Stack Overflow: tsParticles + Next.js SSR](https://stackoverflow.com/questions/77395525/is-it-in-any-way-possible-to-use-tsparticles-with-next-js-and-ssr) — SSR handling
- [Codrops: Three.js Particles](https://tympanus.net/codrops/2019/01/17/interactive-particles-with-three-js/) — Advanced reference
