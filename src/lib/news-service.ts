import { SupabaseClient } from '@supabase/supabase-js'

/** Trusted source domains — displayed first in "Read More On", ordered by embedding score within tier. */
const TRUSTED_SOURCE_DOMAINS = new Set([
  // Wire services & newspapers of record
  'reuters.com', 'apnews.com', 'wsj.com', 'nytimes.com', 'washingtonpost.com',
  'ft.com', 'financialtimes.com', 'bloomberg.com', 'economist.com',
  // Public broadcasters
  'npr.org', 'bbc.com', 'bbc.co.uk', 'theguardian.com', 'cbc.ca', 'aljazeera.com',
  // Business & markets
  'cnbc.com', 'marketwatch.com', 'barrons.com', 'investing.com', 'fortune.com',
  'forbes.com', 'businessinsider.com', 'hbr.org', 'fastcompany.com', 'inc.com', 'qz.com',
  // Tech
  'techcrunch.com', 'theverge.com', 'wired.com', 'arstechnica.com', 'venturebeat.com',
  'technologyreview.com', 'geekwire.com', 'theinformation.com', 'engadget.com',
  'zdnet.com', 'cnet.com', 'pcmag.com', 'tomshardware.com',
  // Policy & analysis
  'axios.com', 'semafor.com', 'politico.com', 'thehill.com', 'propublica.org',
  'vox.com', 'time.com', 'usatoday.com', 'vice.com',
  // Long-form & magazines
  'theatlantic.com', 'newyorker.com', 'foreignaffairs.com', 'foreignpolicy.com',
  // Science & health
  'statnews.com', 'nature.com', 'science.org', 'nejm.org', 'thelancet.com',
  // Regional US papers
  'seattletimes.com', 'latimes.com', 'sfchronicle.com', 'bostonglobe.com',
  'chicagotribune.com', 'dallasnews.com', 'miamiherald.com', 'ajc.com',
  'startribune.com', 'inquirer.com',
  // Government & intl orgs
  'sec.gov', 'federalreserve.gov', 'treasury.gov', 'justice.gov', 'ftc.gov',
  'fcc.gov', 'nist.gov', 'congress.gov', 'oecd.org', 'imf.org', 'worldbank.org',
])

/** Minimum embedding similarity to include in source list (filters off-topic results). */
const SOURCE_SIMILARITY_THRESHOLD = 0.73

const UNSAFE_SOURCE_DOMAINS = new Set([
  'marketscreener.com',
  'uk.marketscreener.com',
  'politico.com',
  'tradingeconomics.com',
  'bitget.com',
])

function isUnsafeSourceUrl(resolvedUrl: string | null): boolean {
  if (!resolvedUrl) return false
  const domain = getDomainFromUrl(resolvedUrl)
  return UNSAFE_SOURCE_DOMAINS.has(domain)
}

function getDomainFromUrl(url: string): string {
  try {
    const hostname = new URL(url).hostname
    return hostname.startsWith('www.') ? hostname.slice(4) : hostname
  } catch {
    return ''
  }
}

export interface NewsItem {
  id: string
  feed_name: string
  title: string // AI headline only — articles without headline are hidden
  wsjTitle: string // Original WSJ title — only for SourceList attribution
  description: string | null
  link: string
  creator: string | null
  subcategory: string | null
  published_at: string
  top_image: string | null
  summary: string | null
  source: string | null
  slug: string | null
  importance: string | null // 'must_read' | 'worth_reading' | 'optional' (prefers importance_reranked over importance)
  key_takeaway: string | null
  keywords: string[] | null
  thread_id: string | null
  resolved_url: string | null
  source_count: number
}

export interface CrawlSource {
  title: string | null
  source: string
  resolved_url: string
  domain: string
  embeddingScore?: number
}

export interface StoryThread {
  id: string
  title: string
  member_count: number
  first_seen: string
  last_seen: string
  status: 'active' | 'cooling' | 'archived'
}

export interface ParentThread {
  id: string
  title: string
}

export interface StoryThreadWithDetails extends StoryThread {
  parent_id: string | null
  heat: number
  recentArticles: Pick<NewsItem, 'id' | 'title' | 'slug' | 'published_at' | 'importance'>[]
}

export interface ParentThreadGroup {
  parent: ParentThread | null // null = orphan group (no parent assigned)
  subThreads: StoryThreadWithDetails[]
  totalHeat: number
}

export interface RelatedArticle {
  id: string
  title: string
  slug: string | null
  feed_name: string
  published_at: string
  similarity: number
  summary: string | null
  top_image: string | null
  importance: string | null
}

export interface Briefing {
  id: string
  date: string
  category: string
  briefing_text: string
  audio_url: string | null
  audio_duration: number | null
  chapters: { title: string; position: number }[] | null
  sentences: { text: string; start: number; end: number }[] | null
  item_count: number
  created_at: string
}

export class NewsService {
  private supabase: SupabaseClient

  constructor(supabaseClient: SupabaseClient) {
    if (!supabaseClient) {
      throw new Error('NewsService requires a Supabase client instance')
    }
    this.supabase = supabaseClient
  }

  async getLatestBriefings(): Promise<{ en: Briefing | null; ko: Briefing | null }> {
    const { data, error } = await this.supabase
      .from('wsj_briefings')
      .select('*')
      .in('category', ['EN', 'KO'])
      .order('date', { ascending: false })
      .limit(2)

    if (error || !data) return { en: null, ko: null }
    return {
      en: (data as Briefing[]).find(b => b.category === 'EN') ?? null,
      ko: (data as Briefing[]).find(b => b.category === 'KO') ?? null,
    }
  }

  async getNewsItems({
    category,
    limit = 20,
    offset = 0,
    since,
  }: {
    category?: string
    limit?: number
    offset?: number
    since?: string
  } = {}): Promise<NewsItem[]> {
    let query = this.supabase
      .from('wsj_items')
      .select(`
        id,
        feed_name,
        title,
        description,
        link,
        creator,
        subcategory,
        published_at,
        slug,
        thread_id,
        wsj_crawl_results (
          top_image,
          relevance_flag,
          embedding_score,
          source,
          resolved_url,
          wsj_llm_analysis (
            summary,
            headline,
            key_takeaway,
            importance,
            importance_reranked,
            keywords
          )
        )
      `)
      .order('published_at', { ascending: false })
      .range(offset, offset + limit - 1)

    if (since) {
      query = query.gte('published_at', since)
    }

    if (category) {
      query = query.eq('feed_name', category)
    }

    const { data, error } = await query

    if (error || !data) return []

    // Visibility gate: only show articles with an AI headline (implies ok crawl)
    return data
      .map((item: Record<string, unknown>) => {
      const crawlResults = item.wsj_crawl_results as Record<string, unknown>[]
      const crawlArray = Array.isArray(crawlResults) ? crawlResults : crawlResults ? [crawlResults] : []
      // Pick crawl with headline for LLM data; use 'ok' crawl for image/source
      const crawlWithHeadline = crawlArray.find((c) => {
        const a = c.wsj_llm_analysis as Record<string, unknown>[] | Record<string, unknown> | undefined
        const l = Array.isArray(a) ? a[0] : a
        return l?.headline
      })
      const crawl = crawlArray.find((c) => c.relevance_flag === 'ok') ?? crawlWithHeadline ?? crawlArray[0] ?? null
      const llmSource = crawlWithHeadline ?? crawl
      const analysis = llmSource?.wsj_llm_analysis as Record<string, unknown>[] | Record<string, unknown> | undefined
      const llm = Array.isArray(analysis) ? analysis[0] : analysis

      const resolvedUrl = (crawl?.resolved_url as string) || null
      const aiHeadline = (llm?.headline as string) || null
      if (!aiHeadline) return null
      return {
        id: item.id as string,
        feed_name: item.feed_name as string,
        title: aiHeadline,
        wsjTitle: item.title as string,
        description: item.description as string | null,
        link: item.link as string,
        creator: item.creator as string | null,
        subcategory: item.subcategory as string | null,
        published_at: item.published_at as string,
        top_image: (crawl?.top_image as string) || null,
        summary: (llm?.summary as string) || null,
        key_takeaway: (llm?.key_takeaway as string) || null,
        source: (crawl?.source as string) || null,
        slug: (item.slug as string) || null,
        importance: (llm?.importance_reranked as string) || (llm?.importance as string) || null,
        keywords: (llm?.keywords as string[]) || null,
        thread_id: (item.thread_id as string) || null,
        resolved_url: resolvedUrl,
        source_count: 1 + crawlArray.filter((c) => c.resolved_url && ((c.embedding_score as number) >= SOURCE_SIMILARITY_THRESHOLD || c.relevance_flag === 'ok')).length,
      }
    })
    .filter((item): item is NewsItem => item !== null)
  }

  async getNewsItemBySlug(slug: string): Promise<NewsItem | null> {
    const { data, error } = await this.supabase
      .from('wsj_items')
      .select(`
        id,
        feed_name,
        title,
        description,
        link,
        creator,
        subcategory,
        published_at,
        slug,
        thread_id,
        wsj_crawl_results (
          top_image,
          relevance_flag,
          source,
          resolved_url,
          wsj_llm_analysis (
            summary,
            headline,
            key_takeaway,
            importance,
            importance_reranked,
            keywords
          )
        )
      `)
      .eq('slug', slug)
      .limit(1)
      .single()

    if (error || !data) return null

    const item = data as Record<string, unknown>
    const crawlResults = item.wsj_crawl_results as Record<string, unknown>[]
    const crawlArray = Array.isArray(crawlResults) ? crawlResults : crawlResults ? [crawlResults] : []
    // Pick crawl with headline for LLM data; use 'ok' crawl for image/source
    const crawlWithHeadline = crawlArray.find((c) => {
      const a = c.wsj_llm_analysis as Record<string, unknown>[] | Record<string, unknown> | undefined
      const l = Array.isArray(a) ? a[0] : a
      return l?.headline
    })
    const crawl = crawlArray.find((c) => c.relevance_flag === 'ok') ?? crawlWithHeadline ?? crawlArray[0] ?? null
    // Visibility gate: no crawl result = not yet processed
    if (!crawl) return null
    const llmSource = crawlWithHeadline ?? crawl
    const analysis = llmSource?.wsj_llm_analysis as Record<string, unknown>[] | Record<string, unknown> | undefined
    const llm = Array.isArray(analysis) ? analysis[0] : analysis

    const resolvedUrl = (crawl?.resolved_url as string) || null
    const isSafe = !isUnsafeSourceUrl(resolvedUrl)

    const aiHeadline = (llm?.headline as string) || null
    if (!aiHeadline) return null
    return {
      id: item.id as string,
      feed_name: item.feed_name as string,
      title: aiHeadline,
      wsjTitle: item.title as string,
      description: item.description as string | null,
      link: item.link as string,
      creator: item.creator as string | null,
      subcategory: item.subcategory as string | null,
      published_at: item.published_at as string,
      top_image: (crawl?.top_image as string) || null,
      summary: (llm?.summary as string) || null,
      key_takeaway: (llm?.key_takeaway as string) || null,
      source: isSafe ? (crawl?.source as string) || null : null,
      slug: (item.slug as string) || null,
      importance: (llm?.importance_reranked as string) || (llm?.importance as string) || null,
      keywords: (llm?.keywords as string[]) || null,
      thread_id: (item.thread_id as string) || null,
      resolved_url: isSafe ? resolvedUrl : null,
      source_count: 0, // detail page uses getArticleSources() for full list
    }
  }

  async getRelatedArticles(itemId: string, limit = 5): Promise<RelatedArticle[]> {
    const { data, error } = await this.supabase
      .rpc('match_articles', {
        query_item_id: itemId,
        match_count: limit,
        days_window: 7,
      })

    if (error || !data || data.length === 0) return []

    // Enrich with description and image
    const ids = data.map((r: { id: string }) => r.id)
    const { data: items } = await this.supabase
      .from('wsj_items')
      .select('id, description, wsj_crawl_results ( top_image, relevance_flag, wsj_llm_analysis ( headline, importance ) )')
      .in('id', ids)

    type CrawlRow = { top_image: string | null; wsj_llm_analysis?: { importance?: string } | { importance?: string }[] | null }
    const enrichMap = new Map<string, { summary: string | null; top_image: string | null; importance: string | null }>()
    for (const item of (items ?? []) as { id: string; description: string | null; wsj_crawl_results: CrawlRow[] | CrawlRow | null }[]) {
      const crawls = Array.isArray(item.wsj_crawl_results) ? item.wsj_crawl_results : [item.wsj_crawl_results].filter(Boolean) as CrawlRow[]
      const withLlm = crawls.find(c => {
        const llm = Array.isArray(c.wsj_llm_analysis) ? c.wsj_llm_analysis[0] : c.wsj_llm_analysis
        return llm?.importance
      })
      const llm = withLlm ? (Array.isArray(withLlm.wsj_llm_analysis) ? withLlm.wsj_llm_analysis[0] : withLlm.wsj_llm_analysis) : null
      enrichMap.set(item.id, {
        summary: item.description ?? null,
        top_image: crawls.find(c => c?.top_image)?.top_image ?? null,
        importance: llm?.importance ?? null,
      })
    }

    return data.map((r: RelatedArticle) => ({
      ...r,
      ...(enrichMap.get(r.id) ?? { summary: null, top_image: null, importance: null }),
    }))
  }

  async getThreadTimeline(threadId: string): Promise<NewsItem[]> {
    const { data, error } = await this.supabase
      .from('wsj_items')
      .select(`
        id,
        feed_name,
        title,
        description,
        link,
        creator,
        subcategory,
        published_at,
        slug,
        thread_id,
        wsj_crawl_results (
          top_image,
          relevance_flag,
          embedding_score,
          source,
          resolved_url,
          wsj_llm_analysis (
            summary,
            headline,
            key_takeaway,
            importance,
            importance_reranked,
            keywords
          )
        )
      `)
      .eq('thread_id', threadId)
      .order('published_at', { ascending: true })
      .limit(20)

    if (error || !data) return []

    return data.map((item: Record<string, unknown>) => {
      const crawlResults = item.wsj_crawl_results as Record<string, unknown>[]
      const crawlArray = Array.isArray(crawlResults) ? crawlResults : crawlResults ? [crawlResults] : []
      const crawlWithHeadline = crawlArray.find((c) => {
        const a = c.wsj_llm_analysis as Record<string, unknown>[] | Record<string, unknown> | undefined
        const l = Array.isArray(a) ? a[0] : a
        return l?.headline
      })
      const crawl = crawlArray.find((c) => c.relevance_flag === 'ok') ?? crawlWithHeadline ?? crawlArray[0] ?? null
      const llmSource = crawlWithHeadline ?? crawl
      const analysis = llmSource?.wsj_llm_analysis as Record<string, unknown>[] | Record<string, unknown> | undefined
      const llm = Array.isArray(analysis) ? analysis[0] : analysis

      const resolvedUrl = (crawl?.resolved_url as string) || null
      const aiHeadline = (llm?.headline as string) || null
      if (!aiHeadline) return null
      return {
        id: item.id as string,
        feed_name: item.feed_name as string,
        title: aiHeadline,
        wsjTitle: item.title as string,
        description: item.description as string | null,
        link: item.link as string,
        creator: item.creator as string | null,
        subcategory: item.subcategory as string | null,
        published_at: item.published_at as string,
        top_image: (crawl?.top_image as string) || null,
        summary: (llm?.summary as string) || null,
        key_takeaway: (llm?.key_takeaway as string) || null,
        source: (crawl?.source as string) || null,
        slug: (item.slug as string) || null,
        importance: (llm?.importance_reranked as string) || (llm?.importance as string) || null,
        keywords: (llm?.keywords as string[]) || null,
        thread_id: (item.thread_id as string) || null,
        resolved_url: resolvedUrl,
        source_count: 1 + crawlArray.filter((c) => c.resolved_url && ((c.embedding_score as number) >= SOURCE_SIMILARITY_THRESHOLD || c.relevance_flag === 'ok')).length,
      }
    })
    .filter((item): item is NewsItem => item !== null)
  }


  async getStoryThread(threadId: string): Promise<StoryThread | null> {
    const { data, error } = await this.supabase
      .from('wsj_story_threads')
      .select('id, title, member_count, first_seen, last_seen, status')
      .eq('id', threadId)
      .single()

    if (error || !data) return null
    return data as StoryThread
  }

  async getThreadsByIds(threadIds: string[]): Promise<Map<string, StoryThread>> {
    if (threadIds.length === 0) return new Map()
    const { data, error } = await this.supabase
      .from('wsj_story_threads')
      .select('id, title, member_count, first_seen, last_seen, status')
      .in('id', threadIds)
    if (error || !data) return new Map()
    return new Map((data as StoryThread[]).map(t => [t.id, t]))
  }

  async getBriefingSources(briefingId: string): Promise<{
    title: string
    feed_name: string
    link: string
    source: string | null
  }[]> {
    const { data, error } = await this.supabase
      .from('wsj_briefing_items')
      .select(`
        wsj_items (
          title,
          feed_name,
          link,
          wsj_crawl_results (
            source,
            relevance_flag,
            wsj_llm_analysis ( headline )
          )
        )
      `)
      .eq('briefing_id', briefingId)

    if (error || !data) return []

    return data.map((row: Record<string, unknown>) => {
      const item = row.wsj_items as Record<string, unknown>
      const crawls = item?.wsj_crawl_results as Record<string, unknown>[] | undefined
      const crawl = crawls?.[0]
      const llmData = crawl?.wsj_llm_analysis as Record<string, unknown>[] | Record<string, unknown> | undefined
      const llmRow = Array.isArray(llmData) ? llmData[0] : llmData
      const aiHeadline = (llmRow?.headline as string) || null
      return {
        title: aiHeadline || '',
        feed_name: (item?.feed_name as string) || '',
        link: (item?.link as string) || '',
        source: (crawl?.source as string) || null,
      }
    })
  }

  async getArticleSources(itemId: string): Promise<CrawlSource[]> {
    // Fetch sources that either pass embedding threshold OR were adopted by the pipeline (relevance_flag='ok')
    const { data } = await this.supabase
      .from('wsj_crawl_results')
      .select('title, source, resolved_url, embedding_score, relevance_flag')
      .eq('wsj_item_id', itemId)
      .not('resolved_url', 'is', null)
      .or(`embedding_score.gte.${SOURCE_SIMILARITY_THRESHOLD},relevance_flag.eq.ok`)
      .order('embedding_score', { ascending: false })

    if (!data) return []

    const sources = (data as { title: string | null; source: string; resolved_url: string; embedding_score: number }[])
      .map((r) => ({
        title: r.title,
        source: r.source,
        resolved_url: r.resolved_url,
        domain: getDomainFromUrl(r.resolved_url),
        embeddingScore: r.embedding_score,
      }))

    // Sort: trusted domains first (by embedding score), then rest (by embedding score)
    const trusted: typeof sources = []
    const rest: typeof sources = []
    for (const s of sources) {
      if (TRUSTED_SOURCE_DOMAINS.has(s.domain)) {
        trusted.push(s)
      } else {
        rest.push(s)
      }
    }

    return [...trusted, ...rest]
  }

  async getActiveThreadsGrouped(category?: string): Promise<ParentThreadGroup[]> {
    // Fetch active threads (with parent_id if available)
    const threadQuery = this.supabase
      .from('wsj_story_threads')
      .select('id, title, member_count, first_seen, last_seen, status')
      .in('status', ['active', 'cooling'])
      .order('last_seen', { ascending: false })
      .limit(50)

    const { data: threads, error: threadError } = await threadQuery
    if (threadError || !threads || threads.length === 0) return []

    const threadList = threads as (StoryThread & { parent_id?: string | null })[]

    // Fetch recent articles per thread (batch: get all articles for all threads at once)
    const threadIds = threadList.map(t => t.id)
    const { data: articleData } = await this.supabase
      .from('wsj_items')
      .select(`
        id, title, slug, published_at, feed_name, thread_id,
        wsj_crawl_results (
          relevance_flag,
          wsj_llm_analysis ( headline, importance, importance_reranked )
        )
      `)
      .in('thread_id', threadIds)
      .order('published_at', { ascending: false })

    // Group articles by thread_id
    const articlesByThread = new Map<string, { id: string; title: string; slug: string | null; published_at: string; importance: string | null; feed_name: string }[]>()
    if (articleData) {
      for (const raw of articleData as Record<string, unknown>[]) {
        const tid = raw.thread_id as string
        if (!tid) continue
        const crawls = raw.wsj_crawl_results as Record<string, unknown>[]
        const crawlArr = Array.isArray(crawls) ? crawls : crawls ? [crawls] : []
        const crawlWithHeadline = crawlArr.find((c) => {
          const a = c.wsj_llm_analysis as Record<string, unknown>[] | Record<string, unknown> | undefined
          const l = Array.isArray(a) ? a[0] : a
          return l?.headline
        })
        const crawl = crawlArr.find((c) => c.relevance_flag === 'ok') ?? crawlWithHeadline ?? crawlArr[0]
        const llmSource = crawlWithHeadline ?? crawl
        const analysis = llmSource?.wsj_llm_analysis as Record<string, unknown>[] | Record<string, unknown> | undefined
        const llm = Array.isArray(analysis) ? analysis[0] : analysis

        const aiHeadline = (llm?.headline as string) || null
        if (!aiHeadline) continue
        const article = {
          id: raw.id as string,
          title: aiHeadline,
          slug: (raw.slug as string) || null,
          published_at: raw.published_at as string,
          importance: (llm?.importance_reranked as string) || (llm?.importance as string) || null,
          feed_name: raw.feed_name as string,
        }
        const list = articlesByThread.get(tid) || []
        list.push(article)
        articlesByThread.set(tid, list)
      }
    }

    // Calculate heat and build StoryThreadWithDetails
    const now = Date.now()
    const importanceWeight: Record<string, number> = { must_read: 3, worth_reading: 2, optional: 1 }

    const detailedThreads: StoryThreadWithDetails[] = threadList
      .map(t => {
        const articles = articlesByThread.get(t.id) || []

        // Filter by category if specified
        const relevantArticles = category
          ? articles.filter(a => a.feed_name === category)
          : articles

        // Skip thread if no articles match the category filter
        if (category && relevantArticles.length === 0) return null

        // Heat = Σ (importance_weight × e^(-0.3 × days_old))
        const heat = articles.reduce((sum, a) => {
          const daysOld = (now - new Date(a.published_at).getTime()) / (1000 * 60 * 60 * 24)
          const weight = importanceWeight[a.importance ?? 'optional'] ?? 1
          return sum + weight * Math.exp(-0.3 * daysOld)
        }, 0)

        return {
          ...t,
          parent_id: t.parent_id ?? null,
          heat,
          recentArticles: relevantArticles.slice(0, 5).map(a => ({
            id: a.id,
            title: a.title,
            slug: a.slug,
            published_at: a.published_at,
            importance: a.importance,
          })),
        }
      })
      .filter((t): t is StoryThreadWithDetails => t !== null && t.heat > 0)
      .sort((a, b) => b.heat - a.heat)

    // Group by parent_id
    const parentMap = new Map<string | null, StoryThreadWithDetails[]>()
    for (const thread of detailedThreads) {
      const key = thread.parent_id
      const list = parentMap.get(key) || []
      list.push(thread)
      parentMap.set(key, list)
    }

    // Build ParentThreadGroup array
    // For now, all threads have parent_id = null (backend not yet ready)
    // When parent_id is populated, we'd fetch wsj_parent_threads here
    const groups: ParentThreadGroup[] = []
    for (const [parentId, subThreads] of parentMap) {
      const totalHeat = subThreads.reduce((sum, t) => sum + t.heat, 0)
      groups.push({
        parent: parentId ? { id: parentId, title: '' } : null, // TODO: fetch parent titles when table exists
        subThreads: subThreads.sort((a, b) => b.heat - a.heat),
        totalHeat,
      })
    }

    return groups.sort((a, b) => b.totalHeat - a.totalHeat)
  }

  async getCategories(): Promise<string[]> {
    const { data, error } = await this.supabase
      .from('wsj_items')
      .select('feed_name')
      .eq('processed', true)

    if (error || !data) return []

    const unique = [...new Set(data.map((d: { feed_name: string }) => d.feed_name))]
    return unique.sort()
  }
}
