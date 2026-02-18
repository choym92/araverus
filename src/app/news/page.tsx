import { createClient } from '@/lib/supabase-server'
import { NewsService } from '@/lib/news-service'
import type { NewsItem } from '@/lib/news-service'
import NewsShell from './_components/NewsShell'
import BriefingPlayer from './_components/BriefingPlayer'
import ArticleCard from './_components/ArticleCard'
import KeywordPills from './_components/KeywordPills'
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
  searchParams: Promise<{ category?: string; tab?: string; keyword?: string }>
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

/** Group articles by thread_id */
function groupByThread(items: NewsItem[]): {
  threaded: Map<string, { threadId: string; articles: NewsItem[] }>
  ungrouped: NewsItem[]
} {
  const threaded = new Map<string, { threadId: string; articles: NewsItem[] }>()
  const ungrouped: NewsItem[] = []

  for (const item of items) {
    if (item.thread_id) {
      const group = threaded.get(item.thread_id)
      if (group) {
        group.articles.push(item)
      } else {
        threaded.set(item.thread_id, { threadId: item.thread_id, articles: [item] })
      }
    } else {
      ungrouped.push(item)
    }
  }

  // Sort articles within each thread: must_read first, then by published_at desc
  const importanceOrder: Record<string, number> = { must_read: 0, worth_reading: 1, optional: 2 }
  for (const group of threaded.values()) {
    group.articles.sort((a, b) => {
      const ia = importanceOrder[a.importance || 'optional'] ?? 2
      const ib = importanceOrder[b.importance || 'optional'] ?? 2
      if (ia !== ib) return ia - ib
      return new Date(b.published_at).getTime() - new Date(a.published_at).getTime()
    })
  }

  return { threaded, ungrouped }
}

export default async function NewsPage({ searchParams }: NewsPageProps) {
  const params = await searchParams
  const category = params.category
  const tab = params.tab || 'today'
  const activeKeyword = params.keyword || null
  const supabase = await createClient()
  const service = new NewsService(supabase)

  const [{ en: enBriefing, ko: koBriefing }, items] = await Promise.all([
    service.getLatestBriefings(),
    service.getNewsItems({ category, limit: 30 }),
  ])

  const briefing = enBriefing || koBriefing
  const briefingSources = briefing
    ? await service.getBriefingSources(briefing.id)
    : []

  // TODO: Remove local file reads once pipeline uploads to Supabase Storage
  const ttsDir = path.join(process.cwd(), 'notebooks/tts_outputs/text')
  const [localChaptersEn, localChaptersKo, localSentencesEn, localSentencesKo, localTranscriptEn, localTranscriptKo] = await Promise.all([
    readFile(path.join(ttsDir, 'chapters-en-2026-02-16.json'), 'utf-8').then(JSON.parse).catch(() => undefined),
    readFile(path.join(ttsDir, 'chapters-ko-2026-02-16.json'), 'utf-8').then(JSON.parse).catch(() => undefined),
    readFile(path.join(ttsDir, 'sentences-en-2026-02-16.json'), 'utf-8').then(JSON.parse).catch(() => undefined),
    readFile(path.join(ttsDir, 'sentences-ko-2026-02-16.json'), 'utf-8').then(JSON.parse).catch(() => undefined),
    readFile(path.join(ttsDir, 'briefing-pro-friendly-2026-02-16.txt'), 'utf-8').catch(() => undefined),
    readFile(path.join(ttsDir, 'briefing-ko-pro-2026-02-16.txt'), 'utf-8').catch(() => undefined),
  ])

  // Filter by keyword if active
  const filteredItems = activeKeyword
    ? items.filter((item) =>
        item.keywords?.some((kw) => kw.toLowerCase() === activeKeyword.toLowerCase())
      )
    : items

  // Aggregate keywords for filter bar
  const allKeywords = aggregateKeywords(items)

  // Group by thread for today tab
  const { threaded, ungrouped } = groupByThread(filteredItems)

  // For non-threaded layout (backward compat)
  const featured = filteredItems[0] || null
  const leftStories = filteredItems.slice(1, 6)
  const rightStories = filteredItems.slice(6, 13)
  const belowFold = filteredItems.slice(13)

  const briefingDate = briefing
    ? new Date(briefing.date).toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
      })
    : null

  // Build URL helper for tab switching
  const buildTabUrl = (tabValue: string) => {
    const params = new URLSearchParams()
    if (tabValue !== 'today') params.set('tab', tabValue)
    if (category) params.set('category', category)
    if (activeKeyword) params.set('keyword', activeKeyword)
    const qs = params.toString()
    return `/news${qs ? `?${qs}` : ''}`
  }

  const hasThreads = threaded.size > 0

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

          {/* Category pills */}
          <div className="flex items-center gap-1 overflow-x-auto py-2">
            {CATEGORIES.map((cat) => {
              const isActive = cat.slug === '' ? !category : category === cat.slug
              const href = cat.slug
                ? `/news?category=${cat.slug}${activeKeyword ? `&keyword=${encodeURIComponent(activeKeyword)}` : ''}`
                : `/news${activeKeyword ? `?keyword=${encodeURIComponent(activeKeyword)}` : ''}`
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
        </div>
      </nav>

      <div className="px-6 md:px-12 lg:px-16 py-6">
        {/* Keyword filter bar */}
        {allKeywords.length > 0 && (
          <div className="mb-6 flex items-center gap-3 overflow-x-auto pb-2">
            <span className="text-xs text-neutral-400 font-medium shrink-0">Topics:</span>
            <KeywordPills
              keywords={allKeywords.map((k) => k.keyword)}
              activeKeyword={activeKeyword}
              linkable
            />
          </div>
        )}

        {/* Active filter indicator */}
        {activeKeyword && (
          <div className="mb-4 flex items-center gap-2">
            <span className="text-sm text-neutral-500">
              Filtering by: <strong className="text-neutral-900">{activeKeyword}</strong>
            </span>
            <Link
              href={`/news${category ? `?category=${category}` : ''}`}
              className="text-xs text-neutral-400 hover:text-neutral-600 underline"
            >
              Clear filter
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
              {activeKeyword
                ? `No articles found for "${activeKeyword}".`
                : 'No articles available yet.'}
            </p>
            <p className="text-neutral-400 text-sm mt-2">
              {activeKeyword ? (
                <Link href="/news" className="underline hover:text-neutral-600">
                  Clear filter
                </Link>
              ) : (
                'The finance pipeline is still collecting data.'
              )}
            </p>
          </div>
        )}

        {/* Today tab: thread-grouped layout */}
        {tab === 'today' && filteredItems.length > 0 && hasThreads && (
          <div className="space-y-10">
            {/* Audio Briefing Player */}
            <div className="max-w-3xl mx-auto">
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

            {/* Thread groups */}
            {Array.from(threaded.values()).map((group) => (
              <section key={group.threadId}>
                <h2 className="font-serif text-lg text-neutral-900 border-b-2 border-neutral-900 pb-2 mb-4">
                  {/* Thread title from first article's metadata — falls back to category */}
                  {group.articles[0]?.feed_name
                    ? `${group.articles.length} articles`
                    : 'Related Stories'}
                </h2>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-x-6">
                  {group.articles.map((item) => (
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
                      activeKeyword={activeKeyword}
                    />
                  ))}
                </div>
              </section>
            ))}

            {/* Ungrouped articles */}
            {ungrouped.length > 0 && (
              <section>
                <h2 className="font-serif text-lg text-neutral-900 border-b-2 border-neutral-900 pb-2 mb-4">
                  Other Stories
                </h2>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-x-6">
                  {ungrouped.map((item) => (
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
                      activeKeyword={activeKeyword}
                    />
                  ))}
                </div>
              </section>
            )}
          </div>
        )}

        {/* Fallback: WSJ 3-column layout (when no threads available) */}
        {tab === 'today' && filteredItems.length > 0 && !hasThreads && (
          <>
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-0 border-b border-neutral-200 pb-8 mb-8">
              {/* Left column — text stories */}
              <div className="lg:col-span-3 lg:border-r lg:border-neutral-200 lg:pr-6">
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
                    activeKeyword={activeKeyword}
                  />
                ))}
              </div>

              {/* Center — audio player + featured hero */}
              <div className="lg:col-span-6 lg:px-6">
                {/* Audio Briefing Player */}
                <div className="mb-6">
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
                    activeKeyword={activeKeyword}
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
                        activeKeyword={activeKeyword}
                      />
                    ))}
                  </div>
                )}
              </div>

              {/* Right sidebar */}
              <div className="lg:col-span-3 lg:border-l lg:border-neutral-200 lg:pl-6">
                <h3 className="font-serif text-lg text-neutral-900 border-b-2 border-neutral-900 pb-2 mb-3">
                  Latest
                </h3>
                {rightStories.map((item) => (
                  <ArticleCard
                    key={item.id}
                    headline={item.title}
                    summary={null}
                    source={item.source}
                    category={item.feed_name}
                    timestamp={item.published_at}
                    imageUrl={null}
                    link={item.link}
                    variant="compact"
                    slug={item.slug}
                    importance={item.importance}
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
                    activeKeyword={activeKeyword}
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
            Data sourced from public RSS feeds and crawled articles. Not affiliated with The Wall Street Journal.
          </p>
        </div>
      </div>
    </NewsShell>
  )
}
