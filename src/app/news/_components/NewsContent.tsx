'use client'

import { useSearchParams } from 'next/navigation'
import nextDynamic from 'next/dynamic'
import Link from 'next/link'
import type { NewsItem, StoryThread } from '@/lib/news-service'
import type { BriefingSource, BriefingLangData } from './BriefingPlayer'
import ArticleCard from './ArticleCard'
import FilterButton from './FilterButton'

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
}

export default function NewsContent({
  items,
  briefingPlayerData,
  threadTimelines,
  threadMeta,
  allKeywords,
  allSubcategories,
}: NewsContentProps) {
  const searchParams = useSearchParams()
  const category = searchParams.get('category') || undefined
  const tab = searchParams.get('tab') || 'today'
  // Support both ?keywords=A,B (new) and ?keyword=A (legacy)
  const activeKeywords: string[] = searchParams.get('keywords')
    ? searchParams.get('keywords')!.split(',').map((k) => k.trim()).filter(Boolean)
    : searchParams.get('keyword')
      ? [searchParams.get('keyword')!]
      : []

  // Client-side filtering by category
  const filteredByCategory = category
    ? items.filter(item => item.feed_name === category)
    : items

  // Client-side filtering by keywords/subcategory (OR match)
  const activeSet = new Set(activeKeywords.map((k) => k.toLowerCase()))
  const filteredItems = activeSet.size > 0
    ? filteredByCategory.filter((item) => {
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
    : filteredByCategory

  // Card slicing for 3-column layout
  const featured = filteredItems[0] || null
  const leftStories = filteredItems.slice(1, 6)
  const rightStories = filteredItems.slice(6, 12)
  const belowFold = filteredItems.slice(12)

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
    threadTimeline: item.thread_id ? threadTimelines[item.thread_id] ?? null : null,
    threadTitle: item.thread_id ? threadMeta[item.thread_id]?.title ?? null : null,
  })

  return (
    <>
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
                  date={briefingPlayerData.date}
                  duration={briefingPlayerData.duration}
                  sourceCount={briefingPlayerData.sourceCount}
                  sources={briefingPlayerData.sources}
                  en={briefingPlayerData.en}
                  ko={briefingPlayerData.ko}
                  defaultLang={briefingPlayerData.defaultLang}
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
    </>
  )
}
