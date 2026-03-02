<!-- Created: 2026-03-01 -->
# Plan: Filter Side Panel

## Goal
Replace the dropdown `FilterButton` with a persistent slide-in right panel that pushes content left (doesn't overlay), stays open while browsing.

## Current State
- `FilterButton.tsx` — dropdown popover, opens on click, closes on outside click
- Used in `NewsContent.tsx` nav bar (right side of category row)
- Keywords and subcategories passed as props from `page.tsx`
- Filter state lives in URL (`?keywords=A,B`)

## Layout Analysis
- `NewsShell` wraps content with `pt-20`; left Sidebar uses the same push-content pattern (`lg:ml-[var(--sidebar-w)]`)
- `NewsContent` outer content area: `px-6 md:px-16 lg:px-24`
- 3-column `grid-cols-12` inside (col-span-3 | col-span-6 | col-span-3)
- Nav bar: `sticky top-20 z-10 bg-white`

## Proposed Approach

### Mechanism
- `filterPanelOpen` state lives in `NewsContent` (already a client component)
- Panel: `fixed right-0 top-20 h-[calc(100vh-5rem)] w-72 bg-white border-l border-neutral-200 z-20` — slides in from right
- Content shift: when open on lg+, add `lg:pr-72` to the outer `<div className="px-6 md:px-16 lg:px-24 ...">` — content area narrows, no overlay
- Nav toggle button replaces the old `FilterButton` (same position, same styling)

### Mobile behavior
- Panel overlays content on small screens (no content shift, just a slide-in with backdrop)
- Only `lg:pr-72` shift applied on desktop

## Files to Change

| File | Action | Description |
|------|--------|-------------|
| `src/app/news/_components/FilterPanel.tsx` | Create | New sticky right panel with keywords/subcategories |
| `src/app/news/_components/NewsContent.tsx` | Modify | Add filterPanelOpen state, toggle button, pr-72 shift, render FilterPanel |
| `src/app/news/_components/FilterButton.tsx` | Delete | Replaced by FilterPanel + toggle button in nav |

## FilterPanel Component Design
```
┌─────────────────────────┐
│  Filter          ✕      │  ← close button, sticky header
├─────────────────────────┤
│  Clear all              │  ← only when active keywords > 0
├─────────────────────────┤
│  REGION                 │
│  US · EU · Asia · ...   │  ← pill-style, same as before
├─────────────────────────┤
│  TOPICS                 │
│  AI · Fed · Trade · ... │  ← pill list, no scroll limit
│  (scrollable)           │
└─────────────────────────┘
```

- Panel scrolls independently (overflow-y-auto on inner body)
- Active keywords: filled pill (bg-neutral-900 text-white)
- Inactive: plain text hover
- Keyword toggle: same URL mutation logic as current FilterButton

## Toggle Button in Nav
- Same position as current FilterButton (right of category bar, border-l)
- Style: `text-[11px] uppercase tracking-widest font-bold text-neutral-400 hover:text-neutral-900`
- Shows active count badge when keywords selected
- Icon: SlidersHorizontal (same as before)
- Text: "Filter" when closed, "Filter" when open (icon changes color to neutral-900)

## Animation
- `translate-x-0` ↔ `translate-x-full` with `transition-transform duration-200`
- Content padding: `transition-[padding] duration-200`

## Database Changes
None

## Risks & Considerations
- Nav bar is `sticky top-20 z-10`; panel is `z-20` — panel overlaps nav on mobile (acceptable, close button visible)
- On desktop the panel sits below nav naturally (top-20 = same as nav bottom)
- No URL state for panel open/closed — intentionally ephemeral (resets on navigation)
