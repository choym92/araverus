'use client'

import { useState, useCallback } from 'react'
import { useSearchParams } from 'next/navigation'
import nextDynamic from 'next/dynamic'
import Link from 'next/link'
import type { NewsItem, StoryThread, ParentThreadGroup } from '@/lib/news-service'
import type { BriefingSource, BriefingLangData } from './BriefingPlayer'
import ArticleCard from './ArticleCard'
import FilterPanel from './FilterPanel'
import StoriesTab from './StoriesTab'

const BriefingPlayer = nextDynamic(
  () => import('./BriefingPlayer'),
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

const CATEGORIES = [
  { label: 'All', slug: '', href: '/news' },
  { label: 'Markets', slug: 'BUSINESS_MARKETS', href: '/news/c/markets' },
  { label: 'Tech', slug: 'TECH', href: '/news/c/tech' },
  { label: 'Economy', slug: 'ECONOMY', href: '/news/c/economy' },
  { label: 'World', slug: 'WORLD', href: '/news/c/world' },
  { label: 'Politics', slug: 'POLITICS', href: '/news/c/politics' },
] as const

const TABS = [
  { label: 'Today', value: 'today' },
  { label: 'Stories', value: 'stories' },
  { label: 'Search', value: 'search' },
] as const

interface NewsContentProps {
  items: NewsItem[]
  briefingPlayerData: {
    date: string
    duration: number
    sourceCount: number
    sources: BriefingSource[]
    en: BriefingLangData
    ko: BriefingLangData
    defaultLang: 'en' | 'ko'
  }
  threadTimelines: Record<string, NewsItem[]>
  threadMeta: Record<string, StoryThread>
  allKeywords: { keyword: string; count: number }[]
  allSubcategories: { keyword: string; count: number }[]
  serverCategory?: string
  parentThreadGroups: ParentThreadGroup[]
}

export default function NewsContent({
  items,
  briefingPlayerData,
  threadTimelines,
  threadMeta,
  allKeywords,
  allSubcategories,
  serverCategory,
  parentThreadGroups,
}: NewsContentProps) {
  const searchParams = useSearchParams()
  const category = serverCategory || undefined
  const tab = searchParams.get('tab') || 'today'
  // Support both ?keywords=A,B (new) and ?keyword=A (legacy)
  const activeKeywords: string[] = searchParams.get('keywords')
    ? searchParams.get('keywords')!.split(',').map((k) => k.trim()).filter(Boolean)
    : searchParams.get('keyword')
      ? [searchParams.get('keyword')!]
      : []

  const [filterPanelOpen, setFilterPanelOpen] = useState(false)

  // Load More state
  const [extraItems, setExtraItems] = useState<NewsItem[]>([])
  const [loadingMore, setLoadingMore] = useState(false)
  const [hasMore, setHasMore] = useState(true)

  // Deduplicate by id (extra items may overlap with initial items)
  const seen = new Set<string>()
  const allItems = [...items, ...extraItems].filter(item => {
    if (seen.has(item.id)) return false
    seen.add(item.id)
    return true
  })

  // Client-side filtering by keywords/subcategory (OR match)
  const activeSet = new Set(activeKeywords.map((k) => k.toLowerCase()))
  const filteredItems = activeSet.size > 0
    ? allItems.filter((item) => {
        if (item.keywords?.some((kw) => activeSet.has(kw.toLowerCase()))) return true
        if (item.subcategory) {
          const label = item.subcategory.length <= 3
            ? item.subcategory.toUpperCase()
            : item.subcategory.charAt(0).toUpperCase() + item.subcategory.slice(1)
          if (activeSet.has(label.toLowerCase())) return true
        }
        return false
      })
    : allItems

  // Pick the most important recent article as featured hero
  const featuredIndex = filteredItems.findIndex(item => item.importance === 'must_read' && item.summary)
  const featured = featuredIndex >= 0 ? filteredItems[featuredIndex] : filteredItems[0] || null
  const remaining = filteredItems.filter((_, i) => i !== (featuredIndex >= 0 ? featuredIndex : 0))

  // Card slicing for 3-column layout — balanced left/right
  const sideCount = Math.min(Math.floor(remaining.length / 2), 5)
  const leftStories = remaining.slice(0, sideCount)
  const rightStories = remaining.slice(sideCount, sideCount * 2)
  const belowFold = remaining.slice(sideCount * 2)

  // Build URL helper for tab switching
  const basePath = category
    ? CATEGORIES.find(c => c.slug === category)?.href ?? '/news'
    : '/news'
  const buildTabUrl = (tabValue: string) => {
    const p = new URLSearchParams()
    if (tabValue !== 'today') p.set('tab', tabValue)
    if (activeKeywords.length > 0) p.set('keywords', activeKeywords.join(','))
    const qs = p.toString()
    return `${basePath}${qs ? `?${qs}` : ''}`
  }

  /** Helper to build thread props for an article */
  const threadPropsFor = (item: NewsItem) => ({
    threadTimeline: item.thread_id ? threadTimelines[item.thread_id] ?? null : null,
    threadTitle: item.thread_id ? threadMeta[item.thread_id]?.title ?? null : null,
  })

  /** Load more articles */
  const handleLoadMore = useCallback(async () => {
    setLoadingMore(true)
    try {
      const offset = items.length + extraItems.length
      const params = new URLSearchParams({ offset: String(offset), limit: '20' })
      if (category) params.set('category', category)
      const res = await fetch(`/api/news?${params}`)
      if (!res.ok) throw new Error('Failed to load')
      const data = await res.json()
      setExtraItems(prev => [...prev, ...data.items])
      setHasMore(data.hasMore)
    } catch {
      // Silently fail — user can retry
    } finally {
      setLoadingMore(false)
    }
  }, [items.length, extraItems.length, category])

  return (
    <>
      <FilterPanel
        allSubcategories={allSubcategories}
        allKeywords={allKeywords}
        activeKeywords={activeKeywords}
        isOpen={filterPanelOpen}
        onClose={() => setFilterPanelOpen(false)}
        onOpen={() => setFilterPanelOpen(true)}
      />

      {/* Tab + Category nav bar */}
      <nav
        className={`bg-white sticky top-20 z-10 transition-[padding] duration-200 ${filterPanelOpen ? 'lg:pr-72' : ''}`}
        aria-label="News navigation"
      >
        <div className="px-6 md:px-14 lg:px-[4.5rem]">
          {/* Tabs — typography hierarchy (size + weight) */}
          <div className="flex items-center gap-5 py-3">
            {TABS.map((t) => {
              const isActive = tab === t.value
              const isDisabled = t.value === 'search'
              return (
                <Link
                  key={t.value}
                  href={isDisabled ? '#' : buildTabUrl(t.value)}
                  className={`text-base transition-colors ${
                    isActive
                      ? 'font-semibold text-neutral-900'
                      : isDisabled
                        ? 'font-normal text-neutral-300 cursor-not-allowed'
                        : 'font-normal text-neutral-400 hover:text-neutral-900'
                  }`}
                  aria-disabled={isDisabled}
                  tabIndex={isDisabled ? -1 : undefined}
                >
                  {t.label}
                  {isDisabled && <span className="text-[10px] ml-1">Soon</span>}
                </Link>
              )
            })}
          </div>

          {/* Category nav — WSJ-style uppercase bold */}
          <div className="flex items-center border-b border-neutral-200">
            <div className="flex items-center justify-center flex-1">
              {CATEGORIES.map((cat) => {
                const isActive = cat.slug === '' ? !category : category === cat.slug
                const tabParam = tab !== 'today' ? `tab=${tab}` : ''
                const kwParam = activeKeywords.length > 0 ? `keywords=${encodeURIComponent(activeKeywords.join(','))}` : ''
                const qs = [tabParam, kwParam].filter(Boolean).join('&')
                const href = `${cat.href}${qs ? `?${qs}` : ''}`
                return (
                  <Link
                    key={cat.slug}
                    href={href}
                    className={`px-8 py-3 text-xs uppercase tracking-widest whitespace-nowrap transition-colors border-b -mb-px ${
                      isActive
                        ? 'border-neutral-900 text-neutral-900 font-bold'
                        : 'border-transparent text-neutral-400 font-bold hover:text-neutral-900'
                    }`}
                  >
                    {cat.label}
                  </Link>
                )
              })}
            </div>
          </div>
        </div>
      </nav>

      <div className={`px-6 md:px-16 lg:px-24 py-6 transition-[padding] duration-200 ${filterPanelOpen ? 'lg:pr-72' : ''}`}>

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
              href={basePath}
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
                <Link href={basePath} className="underline hover:text-neutral-600">
                  Clear filter
                </Link>
              ) : (
                'The finance pipeline is still collecting data.'
              )}
            </p>
          </div>
        )}

        {/* Today tab: WSJ 3-column layout for first date group, grid for older */}
        {tab === 'today' && filteredItems.length > 0 && (
          <>
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-0 border-b border-neutral-200 pb-8 mb-8">
              {/* Left column — text stories (order-2 on mobile: after center) */}
              <div className="order-2 lg:order-none lg:col-span-3 lg:row-start-1 lg:border-r lg:border-neutral-200 lg:pr-6">
                {leftStories.map((item) => (
                  <ArticleCard
                    key={item.id}
                    headline={item.headline || item.title}
                    summary={item.summary ?? item.description}
                    sourceCount={item.source_count}
                    category={item.feed_name}
                    subcategory={item.subcategory}
                    timestamp={item.published_at}
                    imageUrl={item.top_image}
                    link={item.link}
                    variant="standard"
                    slug={item.slug}
                    importance={item.importance}
                    keywords={item.keywords}
                    activeKeywords={activeKeywords}
                    itemId={item.id}
                    {...threadPropsFor(item)}
                  />
                ))}
              </div>

              {/* Center — briefing + featured hero + below-fold (order-first on mobile) */}
              <div className="order-first lg:order-none lg:col-start-4 lg:col-span-6 lg:row-start-1 lg:px-6">
                <div className="mb-6">
                  <BriefingPlayer
                    date={briefingPlayerData.date}
                    duration={briefingPlayerData.duration}
                    sourceCount={briefingPlayerData.sourceCount}
                    sources={briefingPlayerData.sources}
                    en={briefingPlayerData.en}
                    ko={briefingPlayerData.ko}
                    defaultLang={briefingPlayerData.defaultLang}
                  />
                </div>
                {featured && (
                  <ArticleCard
                    headline={featured.headline || featured.title}
                    summary={featured.summary ?? featured.description}
                    sourceCount={featured.source_count}
                    category={featured.feed_name}
                    subcategory={featured.subcategory}
                    timestamp={featured.published_at}
                    imageUrl={featured.top_image}
                    link={featured.link}
                    variant="featured"
                    slug={featured.slug}
                    importance={featured.importance}
                    keywords={featured.keywords}
                    activeKeywords={activeKeywords}
                    itemId={featured.id}
                    {...threadPropsFor(featured)}
                  />
                )}

                {belowFold.length > 0 && (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 mt-6 pt-6 border-t border-neutral-200">
                    {belowFold.slice(0, 4).map((item) => (
                      <ArticleCard
                        key={item.id}
                        headline={item.headline || item.title}
                        summary={item.summary ?? item.description}
                        sourceCount={item.source_count}
                        category={item.feed_name}
                        timestamp={item.published_at}
                        imageUrl={item.top_image}
                        link={item.link}
                        variant="standard"
                        slug={item.slug}
                        importance={item.importance}
                        keywords={item.keywords}
                        activeKeywords={activeKeywords}
                        itemId={item.id}
                        {...threadPropsFor(item)}
                      />
                    ))}
                  </div>
                )}
              </div>

              {/* Right column — standard cards with thread carousels (order-3 on mobile: after left) */}
              <div className="order-3 lg:order-none lg:col-span-3 lg:row-start-1 lg:border-l lg:border-neutral-200 lg:pl-6">
                {rightStories.map((item) => (
                  <ArticleCard
                    key={item.id}
                    headline={item.headline || item.title}
                    summary={item.summary ?? item.description}
                    sourceCount={item.source_count}
                    category={item.feed_name}
                    subcategory={item.subcategory}
                    timestamp={item.published_at}
                    imageUrl={item.top_image}
                    link={item.link}
                    variant="standard"
                    slug={item.slug}
                    importance={item.importance}
                    keywords={item.keywords}
                    activeKeywords={activeKeywords}
                    itemId={item.id}
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
                    headline={item.headline || item.title}
                    summary={item.summary ?? item.description}
                    sourceCount={item.source_count}
                    category={item.feed_name}
                    subcategory={item.subcategory}
                    timestamp={item.published_at}
                    imageUrl={item.top_image}
                    link={item.link}
                    variant="standard"
                    slug={item.slug}
                    importance={item.importance}
                    keywords={item.keywords}
                    activeKeywords={activeKeywords}
                    itemId={item.id}
                    {...threadPropsFor(item)}
                  />
                ))}
              </div>
            )}

            {/* Load More */}
            {hasMore && (
              <div className="py-10">
                <button
                  onClick={handleLoadMore}
                  disabled={loadingMore}
                  className="group w-full flex items-center gap-4 text-left disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <div className="flex-1 h-px bg-neutral-200" />
                  <span className="text-xs uppercase tracking-widest font-medium text-neutral-400 group-hover:text-neutral-900 transition-colors flex items-center gap-2">
                    {loadingMore ? (
                      <>
                        <svg className="animate-spin h-3.5 w-3.5" viewBox="0 0 24 24" fill="none">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                        </svg>
                        Loading
                      </>
                    ) : (
                      <>
                        More Articles
                        <svg className="w-3.5 h-3.5 group-hover:translate-y-0.5 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                        </svg>
                      </>
                    )}
                  </span>
                  <div className="flex-1 h-px bg-neutral-200" />
                </button>
              </div>
            )}
          </>
        )}

        {/* Stories tab */}
        {tab === 'stories' && (
          <StoriesTab groups={parentThreadGroups} />
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
    </>
  )
}
