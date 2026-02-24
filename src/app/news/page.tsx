export const revalidate = 7200 // ISR: cache page for 2 hours

import { Suspense } from 'react'
import { createServiceClient } from '@/lib/supabase-server'
import { NewsService } from '@/lib/news-service'
import type { NewsItem } from '@/lib/news-service'
import NewsShell from './_components/NewsShell'
import NewsContent from './_components/NewsContent'
import { readFile } from 'fs/promises'
import path from 'path'

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

/** Skeleton for Suspense fallback while client component hydrates */
function NewsContentSkeleton() {
  const Bone = ({ className, style }: { className?: string; style?: React.CSSProperties }) => (
    <div className={`animate-pulse rounded bg-neutral-200 ${className ?? ''}`} style={style} />
  )
  return (
    <>
      <nav className="border-b border-neutral-200 bg-white sticky top-20 z-10">
        <div className="px-6 md:px-12 lg:px-16">
          <div className="flex items-center gap-6 border-b border-neutral-100 py-2.5">
            <Bone className="h-4 w-12" />
            <Bone className="h-4 w-14" />
            <Bone className="h-4 w-14" />
          </div>
          <div className="flex items-center gap-1 py-2">
            {[10, 16, 10, 14, 12, 14].map((w, i) => (
              <Bone key={i} className="h-7 rounded-full" style={{ width: `${w * 4}px` }} />
            ))}
          </div>
        </div>
      </nav>
      <div className="px-6 md:px-12 lg:px-16 py-6">
        <Bone className="h-64 w-full rounded-lg" />
      </div>
    </>
  )
}

export default async function NewsPage() {
  // No searchParams access — ISR compatible
  const supabase = createServiceClient()
  const service = new NewsService(supabase)

  // Fetch today's articles first, backfill with older ones if needed
  const todayCutoff = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString()

  const [{ en: enBriefing, ko: koBriefing }, todayItems, allItems] = await Promise.all([
    service.getLatestBriefings(),
    service.getNewsItems({ limit: 50, since: todayCutoff }),
    service.getNewsItems({ limit: 50 }),
  ])

  // Today's articles first, then backfill with older ones (deduped)
  const todayIds = new Set(todayItems.map(i => i.id))
  const olderBackfill = allItems.filter(i => !todayIds.has(i.id))
  const items = [...todayItems, ...olderBackfill].slice(0, 50)

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

  // Collect ALL thread IDs (no client-side filtering — fetch everything for ISR cache)
  const visibleThreadIds = [...new Set(
    items.filter(i => i.thread_id).map(i => i.thread_id!)
  )]

  // Parallel fetch: briefingSources + threadMeta + threadTimelines + local files
  const ttsDir = path.join(process.cwd(), 'notebooks/tts_outputs/text')
  const [briefingSources, threadMetaMap, ...rest] = await Promise.all([
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

  // Convert Maps to plain objects (JSON-serializable for Client Component props)
  const threadTimelines: Record<string, NewsItem[]> = {}
  visibleThreadIds.forEach((id, i) => { threadTimelines[id] = timelines[i] })
  const threadMeta: Record<string, { id: string; title: string; member_count: number; first_seen: string; last_seen: string }> = Object.fromEntries(threadMetaMap)

  // Aggregate keywords for filter bar
  const allKeywords = aggregateKeywords(items)
  const allSubcategories = aggregateSubcategories(items)

  // Sort: importance → crawled → threaded → recency
  const importanceRank: Record<string, number> = { must_read: 0, worth_reading: 1, optional: 2 }
  const sortedItems = [...items].sort((a, b) => {
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

  // Parse briefing date (avoid timezone shift)
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

  // Prepare briefing player data (all serializable)
  const briefingPlayerData = {
    date: briefingDate ?? new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }),
    duration: briefing?.audio_duration ?? 0,
    sourceCount: briefing?.item_count ?? briefingSources.length,
    sources: briefingSources,
    en: {
      audioUrl: enBriefing?.audio_url || '/audio/chirp3-en-pro-friendly-2026-02-16.wav',
      chapters: enBriefing?.chapters ?? localChaptersEn ?? null,
      transcript: enBriefing?.briefing_text || localTranscriptEn || undefined,
      sentences: enBriefing?.sentences ?? localSentencesEn ?? null,
    },
    ko: {
      audioUrl: koBriefing?.audio_url || '/audio/gemini-tts-ko-kore-2026-02-16.wav',
      chapters: koBriefing?.chapters ?? localChaptersKo ?? null,
      transcript: koBriefing?.briefing_text || localTranscriptKo || undefined,
      sentences: koBriefing?.sentences ?? localSentencesKo ?? null,
    },
    defaultLang: 'en' as const,
  }

  return (
    <NewsShell>
      <Suspense fallback={<NewsContentSkeleton />}>
        <NewsContent
          items={sortedItems}
          briefingPlayerData={briefingPlayerData}
          threadTimelines={threadTimelines}
          threadMeta={threadMeta}
          allKeywords={allKeywords}
          allSubcategories={allSubcategories}
        />
      </Suspense>
    </NewsShell>
  )
}
