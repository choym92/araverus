import { unstable_cache } from 'next/cache'
import { createServiceClient } from '@/lib/supabase-server'
import { NewsService } from '@/lib/news-service'
import type { NewsItem, ParentThreadGroup } from '@/lib/news-service'
import { readFile, readdir } from 'fs/promises'
import path from 'path'

/** Aggregate keywords from articles with counts, sorted by frequency.
 *  Merges case variants (e.g. "Geopolitics" + "geopolitics") under the most frequent form. */
function aggregateKeywords(items: NewsItem[]): { keyword: string; count: number }[] {
  const counts = new Map<string, number>()
  const forms = new Map<string, Map<string, number>>() // lowercase → (original → count)
  for (const item of items) {
    if (item.keywords) {
      for (const kw of item.keywords) {
        const key = kw.toLowerCase()
        counts.set(key, (counts.get(key) || 0) + 1)
        const fm = forms.get(key) ?? new Map<string, number>()
        fm.set(kw, (fm.get(kw) || 0) + 1)
        forms.set(key, fm)
      }
    }
  }
  return Array.from(counts.entries())
    .map(([key, count]) => {
      // Pick the most frequent casing as the display name
      const fm = forms.get(key)!
      let best = key
      let bestN = 0
      for (const [form, n] of fm) {
        if (n > bestN) { best = form; bestN = n }
      }
      return { keyword: best, count }
    })
    .sort((a, b) => b.count - a.count)
    .slice(0, 20)
}

/** Aggregate subcategories from articles with counts, sorted by frequency */
function aggregateSubcategories(items: NewsItem[]): { keyword: string; count: number }[] {
  const counts = new Map<string, number>()
  for (const item of items) {
    if (item.subcategory) {
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

/** Sort articles: date (newest day first) → importance within same day → crawled → threaded → recency */
export function sortByDateThenImportance(items: NewsItem[]): NewsItem[] {
  const importanceRank: Record<string, number> = { must_read: 0, worth_reading: 1, optional: 2 }
  return [...items].sort((a, b) => {
    const dateA = new Date(a.published_at)
    const dateB = new Date(b.published_at)
    const dayA = new Date(dateA.getFullYear(), dateA.getMonth(), dateA.getDate()).getTime()
    const dayB = new Date(dateB.getFullYear(), dateB.getMonth(), dateB.getDate()).getTime()
    if (dayA !== dayB) return dayB - dayA
    const ia = importanceRank[a.importance ?? 'optional'] ?? 2
    const ib = importanceRank[b.importance ?? 'optional'] ?? 2
    if (ia !== ib) return ia - ib
    const ca = a.summary ? 0 : 1
    const cb = b.summary ? 0 : 1
    if (ca !== cb) return ca - cb
    const ta = a.thread_id ? 0 : 1
    const tb = b.thread_id ? 0 : 1
    if (ta !== tb) return ta - tb
    return dateB.getTime() - dateA.getTime()
  })
}

const _getStoriesDataCached = unstable_cache(
  async (category: string): Promise<ParentThreadGroup[]> => {
    const supabase = createServiceClient()
    const service = new NewsService(supabase)
    return service.getActiveThreadsGrouped(category === '__all__' ? undefined : category)
  },
  ['news-stories'],
  { revalidate: 86400, tags: ['news'] }
)

export const getStoriesData = (category?: string) =>
  _getStoriesDataCached(category ?? '__all__')

const _getNewsDataCached = unstable_cache(
  async (category: string) => {
    const cat = category === '__all__' ? undefined : category
    const supabase = createServiceClient()
    const service = new NewsService(supabase)

    // Today's articles first, backfill with older (deduped)
    const initialLimit = cat ? 60 : 100
    const todayCutoff = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString()
    const [todayItems, allItems] = await Promise.all([
      service.getNewsItems({ category: cat, limit: initialLimit, since: todayCutoff }),
      service.getNewsItems({ category: cat, limit: initialLimit }),
    ])
    const todayIds = new Set(todayItems.map(i => i.id))
    const olderBackfill = allItems.filter(i => !todayIds.has(i.id))
    const merged = [...todayItems, ...olderBackfill]

    // Dedup by thread: articles >24h old keep only the best per thread
    const oneDayAgo = Date.now() - 24 * 60 * 60 * 1000
    const seenThreads = new Set<string>()
    const items = merged.filter(item => {
      if (!item.thread_id) return true
      const isRecent = new Date(item.published_at).getTime() > oneDayAgo
      if (isRecent) return true
      if (seenThreads.has(item.thread_id)) return false
      seenThreads.add(item.thread_id)
      return true
    }).slice(0, initialLimit)

    const [{ en: enBriefing, ko: koBriefing }] = await Promise.all([
      service.getLatestBriefings(),
    ])

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

    // Collect thread IDs
    const visibleThreadIds = [...new Set(
      items.filter(i => i.thread_id).map(i => i.thread_id!)
    )]

    // Parallel fetch: briefingSources + threadMeta + threadTimelines + local files
    const ttsDir = path.join(process.cwd(), 'notebooks/tts_outputs/text')

    // Find latest TTS date by scanning directory for chapter files
    const latestTtsDate = await readdir(ttsDir).then(files => {
      const dates = files
        .filter(f => f.startsWith('chapters-en-') && f.endsWith('.json'))
        .map(f => f.replace('chapters-en-', '').replace('.json', ''))
        .sort()
        .reverse()
      return dates[0] || '2026-02-16'
    }).catch(() => '2026-02-16')

    const [briefingSources, threadMetaMap, ...rest] = await Promise.all([
      briefing ? service.getBriefingSources(briefing.id) : Promise.resolve([] as { title: string; feed_name: string; link: string; source: string | null }[]),
      service.getThreadsByIds(visibleThreadIds),
      ...visibleThreadIds.map(id => service.getThreadTimeline(id).catch(() => [] as NewsItem[])),
      readFile(path.join(ttsDir, `chapters-en-${latestTtsDate}.json`), 'utf-8').then(JSON.parse).catch(() => undefined),
      readFile(path.join(ttsDir, `chapters-ko-${latestTtsDate}.json`), 'utf-8').then(JSON.parse).catch(() => undefined),
      readFile(path.join(ttsDir, `sentences-en-${latestTtsDate}.json`), 'utf-8').then(JSON.parse).catch(() => undefined),
      readFile(path.join(ttsDir, `sentences-ko-${latestTtsDate}.json`), 'utf-8').then(JSON.parse).catch(() => undefined),
      readFile(path.join(ttsDir, `briefing-pro-friendly-${latestTtsDate}.txt`), 'utf-8').catch(() => undefined),
      readFile(path.join(ttsDir, `briefing-ko-pro-${latestTtsDate}.txt`), 'utf-8').catch(() => undefined),
    ])

    const timelines = rest.slice(0, visibleThreadIds.length) as NewsItem[][]
    const [localChaptersEn, localChaptersKo, localSentencesEn, localSentencesKo, localTranscriptEn, localTranscriptKo] = rest.slice(visibleThreadIds.length)

    const threadTimelines: Record<string, NewsItem[]> = {}
    visibleThreadIds.forEach((id, i) => { threadTimelines[id] = timelines[i] })
    const threadMeta: Record<string, { id: string; title: string; member_count: number; first_seen: string; last_seen: string; status: 'active' | 'cooling' | 'archived' }> = Object.fromEntries(threadMetaMap)

    // Fetch 7-day articles for richer keyword/subcategory aggregation
    const weekCutoff = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString()
    const weekItems = await service.getNewsItems({ category: cat, limit: 200, since: weekCutoff })
    const allKeywords = aggregateKeywords(weekItems)
    const allSubcategories = aggregateSubcategories(weekItems)
    const sortedItems = sortByDateThenImportance(items)

    // Parse briefing date
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

    const briefingPlayerData = {
      date: briefingDate ?? new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }),
      duration: briefing?.audio_duration ?? 0,
      sourceCount: briefing?.item_count ?? briefingSources.length,
      sources: briefingSources,
      en: {
        audioUrl: enBriefing?.audio_url || `/audio/chirp3-en-pro-friendly-${latestTtsDate}.wav`,
        chapters: enBriefing?.chapters ?? localChaptersEn ?? null,
        transcript: enBriefing?.briefing_text || localTranscriptEn || undefined,
        sentences: enBriefing?.sentences ?? localSentencesEn ?? null,
      },
      ko: {
        audioUrl: koBriefing?.audio_url || `/audio/gemini-tts-ko-kore-${latestTtsDate}.wav`,
        chapters: koBriefing?.chapters ?? localChaptersKo ?? null,
        transcript: koBriefing?.briefing_text || localTranscriptKo || undefined,
        sentences: koBriefing?.sentences ?? localSentencesKo ?? null,
      },
      defaultLang: 'en' as const,
    }

    return {
      sortedItems,
      briefingPlayerData,
      threadTimelines,
      threadMeta,
      allKeywords,
      allSubcategories,
    }
  },
  ['news-page'],
  { revalidate: 86400, tags: ['news'] }
)

export const getNewsData = (category?: string) =>
  _getNewsDataCached(category ?? '__all__')

/** Category slug ↔ feed_name mapping */
export const CATEGORY_SLUG_MAP: Record<string, string> = {
  markets: 'BUSINESS_MARKETS',
  tech: 'TECH',
  economy: 'ECONOMY',
  world: 'WORLD',
  politics: 'POLITICS',
}

export const CATEGORY_SLUGS = Object.keys(CATEGORY_SLUG_MAP)
