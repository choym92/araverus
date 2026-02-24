export const revalidate = 7200 // ISR: cache page for 2 hours

import { createServiceClient } from '@/lib/supabase-server'
import { NewsService } from '@/lib/news-service'
import type { NewsItem } from '@/lib/news-service'
import nextDynamic from 'next/dynamic'
import NewsShell from './_components/NewsShell'
import ArticleCard from './_components/ArticleCard'

const BriefingPlayer = nextDynamic(
  () => import('./_components/BriefingPlayer'),
  {
    loading: () => (
      <div className="rounded-lg border border-neutral-200 p-5 animate-pulse">
        <div className="h-5 w-48 rounded bg-neutral-200 mb-3" />
        <div className="h-3 w-32 rounded bg-neutral-200 mb-4" />
        <div className="h-10 w-full rounded-lg bg-neutral-200 mb-3" />
        <div className="flex items-center gap-3">
          <div className="h-8 w-8 rounded-full bg-neutral-200" />
          <div className="h-2 flex-1 rounded-full bg-neutral-200" />
          <div className="h-3 w-10 rounded bg-neutral-200" />
        </div>
      </div>
    ),
  },
)
import FilterButton from './_components/FilterButton'
import Link from 'next/link'
import { readFile } from 'fs/promises'
import path from 'path'

const CATEGORIES = [
  { label: 'All', slug: '' },
  { label: 'Markets', slug: 'BUSINESS_MARKETS' },
  { label: 'Tech', slug: 'TECH' },
  { label: 'Economy', slug: 'ECONOMY' },
  { label: 'World', slug: 'WORLD' },
  { label: 'Politics', slug: 'POLITICS' },
] as const

const TABS = [
  { label: 'Today', value: 'today' },
  { label: 'Stories', value: 'stories' },
  { label: 'Search', value: 'search' },
] as const

interface NewsPageProps {
  searchParams: Promise<{ category?: string; tab?: string; keywords?: string; keyword?: string }>
}

/** Aggregate keywords from articles with counts, sorted by frequency */
function aggregateKeywords(items: NewsItem[]): { keyword: string; count: number }[] {
  const counts = new Map<string, number>()
  for (const item of items) {
    if (item.keywords) {
      for (const kw of item.keywords) {
        counts.set(kw, (counts.get(kw) || 0) + 1)
      }
    }
  }
  return Array.from(counts.entries())
    .map(([keyword, count]) => ({ keyword, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 20)
}

/** Aggregate subcategories from articles with counts, sorted by frequency */
function aggregateSubcategories(items: NewsItem[]): { keyword: string; count: number }[] {
  const counts = new Map<string, number>()
  for (const item of items) {
    if (item.subcategory) {
      // Capitalize for display: "ai" → "AI", "trade" → "Trade"
      const label = item.subcategory.length <= 3
        ? item.subcategory.toUpperCase()
        : item.subcategory.charAt(0).toUpperCase() + item.subcategory.slice(1)
      counts.set(label, (counts.get(label) || 0) + 1)
    }
  }
  return Array.from(counts.entries())
    .map(([keyword, count]) => ({ keyword, count }))
    .sort((a, b) => b.count - a.count)
}

export default async function NewsPage({ searchParams }: NewsPageProps) {
  const params = await searchParams
  const category = params.category
  const tab = params.tab || 'today'
  // Support both ?keywords=A,B (new) and ?keyword=A (legacy)
  const activeKeywords: string[] = params.keywords
    ? params.keywords.split(',').map((k) => k.trim()).filter(Boolean)
    : params.keyword
      ? [params.keyword]
      : []
  const supabase = createServiceClient()
  const service = new NewsService(supabase)

  // Fetch today's articles first, backfill with older ones if needed to fill the layout
  const todayCutoff = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString()

  const [{ en: enBriefing, ko: koBriefing }, todayItems, allItems] = await Promise.all([
    service.getLatestBriefings(),
    service.getNewsItems({ category, limit: 30, since: todayCutoff }),
    service.getNewsItems({ category, limit: 30 }),
  ])

  // Today's articles first, then backfill with older ones (deduped)
  const todayIds = new Set(todayItems.map(i => i.id))
  const olderBackfill = allItems.filter(i => !todayIds.has(i.id))
  const items = [...todayItems, ...olderBackfill].slice(0, 30)

  const briefing = enBriefing || koBriefing

  // Parse JSONB fields that may be stored as strings (pipeline double-stringify bug)
  const parseJsonField = <T,>(val: T | string | null | undefined): T | undefined => {
    if (typeof val === 'string') try { return JSON.parse(val) } catch { return undefined }
    return (val ?? undefined) as T | undefined
  }
  if (enBriefing) {
    enBriefing.chapters = parseJsonField(enBriefing.chapters) ?? null
    enBriefing.sentences = parseJsonField(enBriefing.sentences) ?? null
  }
  if (koBriefing) {
    koBriefing.chapters = parseJsonField(koBriefing.chapters) ?? null
    koBriefing.sentences = parseJsonField(koBriefing.sentences) ?? null
  }

  // Filter by keywords/subcategory (OR match) — show article if ANY keyword or subcategory matches
  const activeSet = new Set(activeKeywords.map((k) => k.toLowerCase()))
  const filteredItems = activeSet.size > 0
    ? items.filter((item) => {
        // Match against keywords
        if (item.keywords?.some((kw) => activeSet.has(kw.toLowerCase()))) return true
        // Match against subcategory (capitalized form used in filter pills)
        if (item.subcategory) {
          const label = item.subcategory.length <= 3
            ? item.subcategory.toUpperCase()
            : item.subcategory.charAt(0).toUpperCase() + item.subcategory.slice(1)
          if (activeSet.has(label.toLowerCase())) return true
        }
        return false
      })
    : items

  // Collect visible thread IDs for timeline fetches
  const visibleThreadIds = [...new Set(
    filteredItems.filter(i => i.thread_id).map(i => i.thread_id!)
  )]

  // Parallel fetch: briefingSources + threadMeta + threadTimelines + local files
  const ttsDir = path.join(process.cwd(), 'notebooks/tts_outputs/text')
  const [briefingSources, threadMeta, ...rest] = await Promise.all([
    briefing ? service.getBriefingSources(briefing.id) : Promise.resolve([] as { title: string; feed_name: string; link: string; source: string | null }[]),
    service.getThreadsByIds(visibleThreadIds),
    ...visibleThreadIds.map(id => service.getThreadTimeline(id).catch(() => [] as NewsItem[])),
    readFile(path.join(ttsDir, 'chapters-en-2026-02-16.json'), 'utf-8').then(JSON.parse).catch(() => undefined),
    readFile(path.join(ttsDir, 'chapters-ko-2026-02-16.json'), 'utf-8').then(JSON.parse).catch(() => undefined),
    readFile(path.join(ttsDir, 'sentences-en-2026-02-16.json'), 'utf-8').then(JSON.parse).catch(() => undefined),
    readFile(path.join(ttsDir, 'sentences-ko-2026-02-16.json'), 'utf-8').then(JSON.parse).catch(() => undefined),
    readFile(path.join(ttsDir, 'briefing-pro-friendly-2026-02-16.txt'), 'utf-8').catch(() => undefined),
    readFile(path.join(ttsDir, 'briefing-ko-pro-2026-02-16.txt'), 'utf-8').catch(() => undefined),
  ])

  // Split rest: first N are timelines, last 6 are local files
  const timelines = rest.slice(0, visibleThreadIds.length) as NewsItem[][]
  const [localChaptersEn, localChaptersKo, localSentencesEn, localSentencesKo, localTranscriptEn, localTranscriptKo] = rest.slice(visibleThreadIds.length)

  const threadTimelines = new Map<string, NewsItem[]>(
    visibleThreadIds.map((id, i) => [id, timelines[i]])
  )

  // Aggregate keywords for filter bar
  const allKeywords = aggregateKeywords(items)
  const allSubcategories = aggregateSubcategories(items)

  // Sort: importance → crawled → threaded → recency
  const importanceRank: Record<string, number> = { must_read: 0, worth_reading: 1, optional: 2 }
  const sortedItems = [...filteredItems].sort((a, b) => {
    const ia = importanceRank[a.importance ?? 'optional'] ?? 2
    const ib = importanceRank[b.importance ?? 'optional'] ?? 2
    if (ia !== ib) return ia - ib
    // Crawled articles have richer cards (summary, keywords, image, source)
    const ca = a.summary ? 0 : 1
    const cb = b.summary ? 0 : 1
    if (ca !== cb) return ca - cb
    // Prefer articles with threads (storylines)
    const ta = a.thread_id ? 0 : 1
    const tb = b.thread_id ? 0 : 1
    if (ta !== tb) return ta - tb
    // Then by recency
    return new Date(b.published_at).getTime() - new Date(a.published_at).getTime()
  })

  // Card slicing for 3-column layout
  const featured = sortedItems[0] || null
  const leftStories = sortedItems.slice(1, 6)
  const rightStories = sortedItems.slice(6, 12)
  const belowFold = sortedItems.slice(12)

  // Parse date string directly to avoid timezone shift (e.g. "2026-02-18" → "Feb 18, 2026")
  const briefingDate = briefing
    ? (() => {
        const [y, m, d] = briefing.date.split('-').map(Number)
        return new Date(y, m - 1, d).toLocaleDateString('en-US', {
          month: 'short',
          day: 'numeric',
          year: 'numeric',
        })
      })()
    : null

  // Build URL helper for tab switching
  const buildTabUrl = (tabValue: string) => {
    const p = new URLSearchParams()
    if (tabValue !== 'today') p.set('tab', tabValue)
    if (category) p.set('category', category)
    if (activeKeywords.length > 0) p.set('keywords', activeKeywords.join(','))
    const qs = p.toString()
    return `/news${qs ? `?${qs}` : ''}`
  }

  /** Helper to build thread props for an article */
  const threadPropsFor = (item: NewsItem) => ({
    id: item.id,
    threadTimeline: item.thread_id ? threadTimelines.get(item.thread_id) ?? null : null,
    threadTitle: item.thread_id ? threadMeta.get(item.thread_id)?.title ?? null : null,
  })

  return (
    <NewsShell>
      {/* Tab + Category nav bar */}
      <nav
        className="border-b border-neutral-200 bg-white sticky top-20 z-10"
        aria-label="News navigation"
      >
        <div className="px-6 md:px-12 lg:px-16">
          {/* Tabs */}
          <div className="flex items-center gap-6 border-b border-neutral-100">
            {TABS.map((t) => {
              const isActive = tab === t.value
              const isDisabled = t.value !== 'today'
              return (
                <Link
                  key={t.value}
                  href={isDisabled ? '#' : buildTabUrl(t.value)}
                  className={`px-1 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors ${
                    isActive
                      ? 'border-neutral-900 text-neutral-900'
                      : isDisabled
                        ? 'border-transparent text-neutral-300 cursor-not-allowed'
                        : 'border-transparent text-neutral-500 hover:text-neutral-700'
                  }`}
                  aria-disabled={isDisabled}
                  tabIndex={isDisabled ? -1 : undefined}
                >
                  {t.label}
                  {isDisabled && <span className="text-[10px] ml-1 text-neutral-300">Soon</span>}
                </Link>
              )
            })}
          </div>

          {/* Category pills + filter button */}
          <div className="flex items-center gap-1 py-2">
            <div className="flex items-center gap-1 overflow-x-auto flex-1 min-w-0">
              {CATEGORIES.map((cat) => {
                const isActive = cat.slug === '' ? !category : category === cat.slug
                const kwParam = activeKeywords.length > 0 ? `keywords=${encodeURIComponent(activeKeywords.join(','))}` : ''
                const href = cat.slug
                  ? `/news?category=${cat.slug}${kwParam ? `&${kwParam}` : ''}`
                  : `/news${kwParam ? `?${kwParam}` : ''}`
                return (
                  <Link
                    key={cat.slug}
                    href={href}
                    className={`px-3 py-1.5 text-xs font-medium whitespace-nowrap rounded-full transition-colors ${
                      isActive
                        ? 'bg-neutral-900 text-white'
                        : 'bg-neutral-100 text-neutral-600 hover:bg-neutral-200'
                    }`}
                  >
                    {cat.label}
                  </Link>
                )
              })}
            </div>
            {/* Filter button — outside overflow container so dropdown is visible */}
            {(allSubcategories.length > 0 || allKeywords.length > 0) && (
              <FilterButton allSubcategories={allSubcategories} allKeywords={allKeywords} activeKeywords={activeKeywords} />
            )}
          </div>
        </div>
      </nav>

      <div className="px-6 md:px-12 lg:px-16 py-6">

        {/* Active filter indicator */}
        {activeKeywords.length > 0 && (
          <div className="mb-4 flex items-center gap-2 flex-wrap">
            <span className="text-sm text-neutral-500">
              Filtering by:{' '}
              {activeKeywords.map((kw, i) => (
                <span key={kw}>
                  {i > 0 && ', '}
                  <strong className="text-neutral-900">{kw}</strong>
                </span>
              ))}
            </span>
            <Link
              href={`/news${category ? `?category=${category}` : ''}`}
              className="text-xs text-neutral-400 hover:text-neutral-600 underline"
            >
              ×Clear
            </Link>
            <span className="text-xs text-neutral-400">
              ({filteredItems.length} article{filteredItems.length !== 1 ? 's' : ''})
            </span>
          </div>
        )}

        {/* Empty state */}
        {filteredItems.length === 0 && (
          <div className="text-center py-16">
            <p className="text-neutral-500 text-lg">
              {activeKeywords.length > 0
                ? `No articles found for "${activeKeywords.join(', ')}".`
                : 'No articles available yet.'}
            </p>
            <p className="text-neutral-400 text-sm mt-2">
              {activeKeywords.length > 0 ? (
                <Link href="/news" className="underline hover:text-neutral-600">
                  Clear filter
                </Link>
              ) : (
                'The finance pipeline is still collecting data.'
              )}
            </p>
          </div>
        )}

        {/* Today tab: WSJ 3-column layout */}
        {tab === 'today' && filteredItems.length > 0 && (
          <>
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-0 border-b border-neutral-200 pb-8 mb-8">
              {/* Audio Briefing Player — first on mobile, center area on desktop */}
              <div className="order-first lg:order-none lg:col-start-4 lg:col-span-6 lg:row-start-1 lg:px-6 mb-6">
                <BriefingPlayer
                  date={briefingDate ?? new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                  duration={briefing?.audio_duration ?? 0}
                  sourceCount={briefing?.item_count ?? briefingSources.length}
                  sources={briefingSources}
                  en={{
                    audioUrl: enBriefing?.audio_url || '/audio/chirp3-en-pro-friendly-2026-02-16.wav',
                    chapters: enBriefing?.chapters ?? localChaptersEn,
                    transcript: enBriefing?.briefing_text || localTranscriptEn,
                    sentences: enBriefing?.sentences ?? localSentencesEn,
                  }}
                  ko={{
                    audioUrl: koBriefing?.audio_url || '/audio/gemini-tts-ko-kore-2026-02-16.wav',
                    chapters: koBriefing?.chapters ?? localChaptersKo,
                    transcript: koBriefing?.briefing_text || localTranscriptKo,
                    sentences: koBriefing?.sentences ?? localSentencesKo,
                  }}
                  defaultLang="en"
                />
              </div>

              {/* Left column — text stories (order-2 on mobile: after center) */}
              <div className="order-2 lg:order-none lg:col-span-3 lg:row-start-1 lg:row-span-2 lg:border-r lg:border-neutral-200 lg:pr-6">
                {leftStories.map((item) => (
                  <ArticleCard
                    key={item.id}
                    headline={item.title}
                    summary={item.summary ?? item.description}
                    source={item.source}
                    category={item.feed_name}
                    timestamp={item.published_at}
                    imageUrl={null}
                    link={item.link}
                    variant="standard"
                    slug={item.slug}
                    importance={item.importance}
                    keywords={item.keywords}
                    activeKeywords={activeKeywords}
                    {...threadPropsFor(item)}
                  />
                ))}
              </div>

              {/* Center — featured hero + below-fold (order-1 on mobile: right after player) */}
              <div className="order-1 lg:order-none lg:col-start-4 lg:col-span-6 lg:row-start-2 lg:px-6">
                {featured && (
                  <ArticleCard
                    headline={featured.title}
                    summary={featured.summary ?? featured.description}
                    source={featured.source}
                    category={featured.feed_name}
                    timestamp={featured.published_at}
                    imageUrl={featured.top_image}
                    link={featured.link}
                    variant="featured"
                    slug={featured.slug}
                    importance={featured.importance}
                    keywords={featured.keywords}
                    activeKeywords={activeKeywords}
                    {...threadPropsFor(featured)}
                  />
                )}

                {belowFold.length > 0 && (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 mt-6 pt-6 border-t border-neutral-200">
                    {belowFold.slice(0, 4).map((item) => (
                      <ArticleCard
                        key={item.id}
                        headline={item.title}
                        summary={item.summary ?? item.description}
                        source={item.source}
                        category={item.feed_name}
                        timestamp={item.published_at}
                        imageUrl={item.top_image}
                        link={item.link}
                        variant="standard"
                        slug={item.slug}
                        importance={item.importance}
                        keywords={item.keywords}
                        activeKeywords={activeKeywords}
                        {...threadPropsFor(item)}
                      />
                    ))}
                  </div>
                )}
              </div>

              {/* Right column — standard cards with thread carousels (order-3 on mobile: after left) */}
              <div className="order-3 lg:order-none lg:col-span-3 lg:row-start-1 lg:row-span-2 lg:border-l lg:border-neutral-200 lg:pl-6">
                {rightStories.map((item) => (
                  <ArticleCard
                    key={item.id}
                    headline={item.title}
                    summary={item.summary ?? item.description}
                    source={item.source}
                    category={item.feed_name}
                    timestamp={item.published_at}
                    imageUrl={null}
                    link={item.link}
                    variant="standard"
                    slug={item.slug}
                    importance={item.importance}
                    keywords={item.keywords}
                    activeKeywords={activeKeywords}
                    {...threadPropsFor(item)}
                  />
                ))}
              </div>
            </div>

            {/* Below-fold remaining stories */}
            {belowFold.length > 4 && (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-x-8">
                {belowFold.slice(4).map((item) => (
                  <ArticleCard
                    key={item.id}
                    headline={item.title}
                    summary={item.summary ?? item.description}
                    source={item.source}
                    category={item.feed_name}
                    timestamp={item.published_at}
                    imageUrl={item.top_image}
                    link={item.link}
                    variant="standard"
                    slug={item.slug}
                    importance={item.importance}
                    keywords={item.keywords}
                    activeKeywords={activeKeywords}
                    {...threadPropsFor(item)}
                  />
                ))}
              </div>
            )}
          </>
        )}

        {/* Stories tab placeholder */}
        {tab === 'stories' && (
          <div className="text-center py-16">
            <p className="text-neutral-500 text-lg">Story timelines coming soon.</p>
            <p className="text-neutral-400 text-sm mt-2">
              Narrative threads across days will appear here once data accumulates.
            </p>
          </div>
        )}

        {/* Search tab placeholder */}
        {tab === 'search' && (
          <div className="text-center py-16">
            <p className="text-neutral-500 text-lg">Semantic search coming soon.</p>
            <p className="text-neutral-400 text-sm mt-2">
              Search by meaning across all articles using embeddings.
            </p>
          </div>
        )}

        {/* Footer */}
        <div className="border-t border-neutral-200 mt-12 pt-6 text-center">
          <p className="text-xs text-neutral-400">
            Data sourced from public RSS feeds and News APIs.
          </p>
        </div>
      </div>
    </NewsShell>
  )
}
