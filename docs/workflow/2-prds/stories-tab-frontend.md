<!-- Created: 2026-03-01 -->
# Plan: Stories Tab — Frontend

## Goal
Stories 탭을 활성화하고, Parent Thread → Sub-thread 계층 구조 UI를 구현한다. 백엔드(DB, 파이프라인)는 별도 세션에서 진행 중이므로 여기서는 프론트엔드만 다룬다.

## Assumptions (from backend plan)
- `wsj_parent_threads` 테이블: `id`, `title`, `created_at`, `updated_at`
- `wsj_story_threads.parent_id` FK → `wsj_parent_threads(id)`, nullable
- Heat score는 query-time 계산 (기존과 동일)
- Orphan sub-threads (`parent_id = NULL`)은 "Uncategorized" 섹션으로 표시

---

## Step 1 — Service Layer (`src/lib/news-service.ts`)

### New interfaces
```typescript
export interface ParentThread {
  id: string
  title: string
}

// Extend existing StoryThread
export interface StoryThreadWithDetails extends StoryThread {
  parent_id: string | null
  heat: number
  recentArticles: Pick<NewsItem, 'id' | 'title' | 'slug' | 'published_at' | 'importance'>[]
}

export interface ParentThreadGroup {
  parent: ParentThread | null   // null = orphan group
  subThreads: StoryThreadWithDetails[]
  totalHeat: number             // sum of sub-thread heats, used for sorting
}
```

### New method: `getActiveThreadsGrouped(category?: string)`
```
1. Fetch wsj_story_threads (active=true) + join wsj_parent_threads via parent_id
2. For each thread, fetch top 3 recent wsj_items (for preview)
3. Calculate heat score per sub-thread (same formula as existing: Σ importance_weight × e^(-0.3 × days))
4. Group by parent_id → ParentThreadGroup[]
5. Sort parents by totalHeat desc
6. Within each parent, sort sub-threads by heat desc
7. If category filter active, only include sub-threads with matching feed_name articles
```

**Category filtering**: Sub-threads are cross-category (articles from multiple categories can be in one thread). Filter by checking if ANY article in the thread matches the category.

---

## Step 2 — Server Component (`src/app/news/page.tsx`)

Add conditional fetch when `tab=stories`:

```typescript
// Only fetch when stories tab is active (protect Today tab perf)
const parentThreadGroups = tab === 'stories'
  ? await service.getActiveThreadsGrouped(category)
  : []
```

Pass `parentThreadGroups` to `NewsContent` as new prop.

---

## Step 3 — Unlock Stories Tab (`NewsContent.tsx`)

**Line 161**: Change disabled logic
```typescript
// Before:
const isDisabled = t.value !== 'today'
// After:
const isDisabled = t.value === 'search'
```

**Remove "Soon" label** for Stories (Search keeps it).

**Props**: Add `parentThreadGroups: ParentThreadGroup[]` to `NewsContentProps`.

**Category pills**: Already visible — keep them. When category changes, server re-fetches with category filter.

---

## Step 4 — New Component: `StoriesTab.tsx`

### Layout
```
Stories Tab
├── ParentThreadCard ("Federal Reserve & Rate Policy")
│   ├── SubThreadRow ("Fed Holds Rates at 4.5%")
│   │   ├── 🔥 heat indicator + article count + date range
│   │   └── [Expanded]: article list (title, date, importance badge)
│   ├── SubThreadRow ("Powell Senate Hearing")
│   └── SubThreadRow ("Rate Cut Q3 Expectations")
│
├── ParentThreadCard ("AI Industry")
│   ├── SubThreadRow (...)
│   └── SubThreadRow (...)
│
└── Uncategorized (orphan sub-threads, if any)
    └── SubThreadRow (...)
```

### Interaction
- **Sub-thread row**: Click to expand/collapse (accordion style, multiple can be open)
- **Expanded state**: Shows article list with title, date, importance pill
  - Article title links to `/news/[slug]` (existing detail page)
- **State**: `useState<Set<string>>` tracking expanded thread IDs
- **Animation**: Framer Motion `AnimatePresence` for smooth expand/collapse

### Visual Design (matches existing monochrome + Tailwind)
- Parent title: `text-lg font-semibold text-neutral-900`
- Sub-thread row: `border-b border-neutral-100 py-3`
- Heat badge: `🔥` count (1-3) based on heat thresholds
- Article count: `text-xs text-neutral-400` (e.g., "5 articles · Feb 23 - Mar 1")
- Importance pills: same as Today tab (`must_read` = black, `worth_reading` = neutral)
- Empty state: "No active stories." with neutral text

---

## Step 5 — Category Filter Integration

When category pill is clicked on Stories tab:
1. URL changes to `/news?tab=stories&category=TECH`
2. Server re-fetches `getActiveThreadsGrouped('TECH')`
3. Only sub-threads containing articles from that category are shown
4. Parent threads with no matching sub-threads are hidden

---

## Files to Change

| File | Action | Description |
|------|--------|-------------|
| `src/lib/news-service.ts` | Modify | Add `ParentThread`, `StoryThreadWithDetails`, `ParentThreadGroup` interfaces + `getActiveThreadsGrouped()` method |
| `src/app/news/page.tsx` | Modify | Conditional fetch for stories tab, pass to NewsContent |
| `src/app/news/_components/NewsContent.tsx` | Modify | Unlock Stories tab, add prop, render StoriesTab |
| `src/app/news/_components/StoriesTab.tsx` | Create | New component for Stories tab UI |

---

## Risks & Considerations

1. **Performance**: `getActiveThreadsGrouped()` does N+1 queries (1 per thread for articles). Mitigate by batching article fetches or using a single joined query.
2. **Empty state**: If backend hasn't run parent grouping yet, all threads are orphans. Handle gracefully — show flat list with message.
3. **Heat calculation**: Currently done in frontend JS. For Stories tab we need it in service layer — extract to shared util.

---

## Not In Scope (handled by backend plan)
- `wsj_parent_threads` table creation
- `wsj_story_threads.parent_id` column migration
- LLM grouping pipeline (`9_group_threads.py`)
- Thread status migration (active boolean → status text)
