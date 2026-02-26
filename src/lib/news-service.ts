import { SupabaseClient } from '@supabase/supabase-js'

const UNSAFE_SOURCE_DOMAINS = new Set([
  'marketscreener.com',
  'uk.marketscreener.com',
  'politico.com',
  'tradingeconomics.com',
  'bitget.com',
])

function getDomainFromUrl(url: string): string {
  try {
    const hostname = new URL(url).hostname
    return hostname.startsWith('www.') ? hostname.slice(4) : hostname
  } catch {
    return ''
  }
}

function isUnsafeSourceUrl(resolvedUrl: string | null): boolean {
  if (!resolvedUrl) return false
  const domain = getDomainFromUrl(resolvedUrl)
  return UNSAFE_SOURCE_DOMAINS.has(domain)
}

export interface NewsItem {
  id: string
  feed_name: string
  title: string
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
}

export interface StoryThread {
  id: string
  title: string
  member_count: number
  first_seen: string
  last_seen: string
}

export interface RelatedArticle {
  id: string
  title: string
  slug: string | null
  feed_name: string
  published_at: string
  similarity: number
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
          source,
          resolved_url,
          wsj_llm_analysis (
            summary,
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

    return data.map((item: Record<string, unknown>) => {
      const crawlResults = item.wsj_crawl_results as Record<string, unknown>[]
      const crawlArray = Array.isArray(crawlResults) ? crawlResults : crawlResults ? [crawlResults] : []
      // Use 'ok' crawl for article data, count all candidates
      const crawl = crawlArray.find((c) => c.relevance_flag === 'ok') ?? crawlArray[0] ?? null
      const analysis = crawl?.wsj_llm_analysis as Record<string, unknown>[] | Record<string, unknown> | undefined
      const llm = Array.isArray(analysis) ? analysis[0] : analysis

      const resolvedUrl = (crawl?.resolved_url as string) || null
      const isSafe = !isUnsafeSourceUrl(resolvedUrl)

      return {
        id: item.id as string,
        feed_name: item.feed_name as string,
        title: item.title as string,
        description: item.description as string | null,
        link: item.link as string,
        creator: item.creator as string | null,
        subcategory: item.subcategory as string | null,
        published_at: item.published_at as string,
        top_image: (crawl?.top_image as string) || null,
        summary: (llm?.summary as string) || null,
        source: isSafe ? (crawl?.source as string) || null : null,
        slug: (item.slug as string) || null,
        importance: (llm?.importance_reranked as string) || (llm?.importance as string) || null,
        keywords: (llm?.keywords as string[]) || null,
        thread_id: (item.thread_id as string) || null,
        resolved_url: isSafe ? resolvedUrl : null,
        source_count: crawlArray.length,
      }
    })
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
          source,
          resolved_url,
          wsj_llm_analysis (
            summary,
            importance,
            importance_reranked,
            keywords
          )
        )
      `)
      .eq('wsj_crawl_results.relevance_flag', 'ok')
      .eq('slug', slug)
      .limit(1)
      .single()

    if (error || !data) return null

    const item = data as Record<string, unknown>
    const crawlResults = item.wsj_crawl_results as Record<string, unknown>[]
    const crawlArray = Array.isArray(crawlResults) ? crawlResults : crawlResults ? [crawlResults] : []
    const crawl = crawlArray[0] ?? null
    const analysis = crawl?.wsj_llm_analysis as Record<string, unknown>[] | Record<string, unknown> | undefined
    const llm = Array.isArray(analysis) ? analysis[0] : analysis

    const resolvedUrl = (crawl?.resolved_url as string) || null
    const isSafe = !isUnsafeSourceUrl(resolvedUrl)

    return {
      id: item.id as string,
      feed_name: item.feed_name as string,
      title: item.title as string,
      description: item.description as string | null,
      link: item.link as string,
      creator: item.creator as string | null,
      subcategory: item.subcategory as string | null,
      published_at: item.published_at as string,
      top_image: (crawl?.top_image as string) || null,
      summary: (llm?.summary as string) || null,
      source: isSafe ? (crawl?.source as string) || null : null,
      slug: (item.slug as string) || null,
      importance: (llm?.importance_reranked as string) || (llm?.importance as string) || null,
      keywords: (llm?.keywords as string[]) || null,
      thread_id: (item.thread_id as string) || null,
      resolved_url: isSafe ? resolvedUrl : null,
      source_count: 0, // detail page uses getArticleSources() for full list
      source_domains: [],
    }
  }

  async getRelatedArticles(itemId: string, limit = 5): Promise<RelatedArticle[]> {
    const { data, error } = await this.supabase
      .rpc('match_articles', {
        query_item_id: itemId,
        match_count: limit,
        days_window: 7,
      })

    if (error || !data) return []
    return data as RelatedArticle[]
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
          source,
          resolved_url,
          wsj_llm_analysis (
            summary,
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
      const crawl = crawlArray.find((c) => c.relevance_flag === 'ok') ?? crawlArray[0] ?? null
      const analysis = crawl?.wsj_llm_analysis as Record<string, unknown>[] | Record<string, unknown> | undefined
      const llm = Array.isArray(analysis) ? analysis[0] : analysis

      const resolvedUrl = (crawl?.resolved_url as string) || null
      const isSafe = !isUnsafeSourceUrl(resolvedUrl)

      return {
        id: item.id as string,
        feed_name: item.feed_name as string,
        title: item.title as string,
        description: item.description as string | null,
        link: item.link as string,
        creator: item.creator as string | null,
        subcategory: item.subcategory as string | null,
        published_at: item.published_at as string,
        top_image: (crawl?.top_image as string) || null,
        summary: (llm?.summary as string) || null,
        source: isSafe ? (crawl?.source as string) || null : null,
        slug: (item.slug as string) || null,
        importance: (llm?.importance_reranked as string) || (llm?.importance as string) || null,
        keywords: (llm?.keywords as string[]) || null,
        thread_id: (item.thread_id as string) || null,
        resolved_url: isSafe ? resolvedUrl : null,
        source_count: crawlArray.length,
      }
    })
  }


  async getStoryThread(threadId: string): Promise<StoryThread | null> {
    const { data, error } = await this.supabase
      .from('wsj_story_threads')
      .select('id, title, member_count, first_seen, last_seen')
      .eq('id', threadId)
      .single()

    if (error || !data) return null
    return data as StoryThread
  }

  async getThreadsByIds(threadIds: string[]): Promise<Map<string, StoryThread>> {
    if (threadIds.length === 0) return new Map()
    const { data, error } = await this.supabase
      .from('wsj_story_threads')
      .select('id, title, member_count, first_seen, last_seen')
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
            relevance_flag
          )
        )
      `)
      .eq('briefing_id', briefingId)

    if (error || !data) return []

    return data.map((row: Record<string, unknown>) => {
      const item = row.wsj_items as Record<string, unknown>
      const crawls = item?.wsj_crawl_results as Record<string, unknown>[] | undefined
      const crawl = crawls?.[0]
      return {
        title: (item?.title as string) || '',
        feed_name: (item?.feed_name as string) || '',
        link: (item?.link as string) || '',
        source: (crawl?.source as string) || null,
      }
    })
  }

  async getArticleSources(itemId: string): Promise<CrawlSource[]> {
    const { data } = await this.supabase
      .from('wsj_crawl_results')
      .select('title, source, resolved_url')
      .eq('wsj_item_id', itemId)
      .not('resolved_url', 'is', null)
      .order('embedding_score', { ascending: false })

    if (!data) return []

    return (data as { title: string | null; source: string; resolved_url: string }[])
      .filter((r) => !isUnsafeSourceUrl(r.resolved_url))
      .map((r) => ({
        title: r.title,
        source: r.source,
        resolved_url: r.resolved_url,
        domain: getDomainFromUrl(r.resolved_url),
      }))
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
