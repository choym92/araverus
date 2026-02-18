import { SupabaseClient } from '@supabase/supabase-js'

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
  importance: string | null // 'must_read' | 'worth_reading' | 'optional'
  keywords: string[] | null
  thread_id: string | null
  resolved_url: string | null
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
  }: {
    category?: string
    limit?: number
    offset?: number
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
        wsj_crawl_results!inner (
          top_image,
          relevance_flag,
          source,
          resolved_url,
          wsj_llm_analysis (
            summary,
            importance,
            keywords
          )
        )
      `)
      .eq('processed', true)
      .eq('wsj_crawl_results.relevance_flag', 'ok')
      .order('published_at', { ascending: false })
      .range(offset, offset + limit - 1)

    if (category) {
      query = query.eq('feed_name', category)
    }

    const { data, error } = await query

    if (error || !data) return []

    return data.map((item: Record<string, unknown>) => {
      const crawlResults = item.wsj_crawl_results as Record<string, unknown>[]
      const crawl = Array.isArray(crawlResults) ? crawlResults[0] : crawlResults
      const analysis = crawl?.wsj_llm_analysis as Record<string, unknown>[] | Record<string, unknown> | undefined
      const llm = Array.isArray(analysis) ? analysis[0] : analysis

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
        source: (crawl?.source as string) || null,
        slug: (item.slug as string) || null,
        importance: (llm?.importance as string) || null,
        keywords: (llm?.keywords as string[]) || null,
        thread_id: (item.thread_id as string) || null,
        resolved_url: (crawl?.resolved_url as string) || null,
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
    const crawl = Array.isArray(crawlResults) ? crawlResults[0] : crawlResults
    const analysis = crawl?.wsj_llm_analysis as Record<string, unknown>[] | Record<string, unknown> | undefined
    const llm = Array.isArray(analysis) ? analysis[0] : analysis

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
      source: (crawl?.source as string) || null,
      slug: (item.slug as string) || null,
      importance: (llm?.importance as string) || null,
      keywords: (llm?.keywords as string[]) || null,
      thread_id: (item.thread_id as string) || null,
      resolved_url: (crawl?.resolved_url as string) || null,
    }
  }

  async getRelatedArticles(itemId: string, limit = 5): Promise<RelatedArticle[]> {
    const { data, error } = await this.supabase
      .rpc('match_articles', {
        query_item_id: itemId,
        match_count: limit,
        days_window: 1,
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
        wsj_crawl_results!inner (
          top_image,
          relevance_flag,
          source,
          resolved_url,
          wsj_llm_analysis (
            summary,
            importance,
            keywords
          )
        )
      `)
      .eq('thread_id', threadId)
      .eq('wsj_crawl_results.relevance_flag', 'ok')
      .order('published_at', { ascending: true })
      .limit(20)

    if (error || !data) return []

    return data.map((item: Record<string, unknown>) => {
      const crawlResults = item.wsj_crawl_results as Record<string, unknown>[]
      const crawl = Array.isArray(crawlResults) ? crawlResults[0] : crawlResults
      const analysis = crawl?.wsj_llm_analysis as Record<string, unknown>[] | Record<string, unknown> | undefined
      const llm = Array.isArray(analysis) ? analysis[0] : analysis

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
        source: (crawl?.source as string) || null,
        slug: (item.slug as string) || null,
        importance: (llm?.importance as string) || null,
        keywords: (llm?.keywords as string[]) || null,
        thread_id: (item.thread_id as string) || null,
        resolved_url: (crawl?.resolved_url as string) || null,
      }
    })
  }

  async getMoreLikeThis(itemId: string, limit = 5): Promise<RelatedArticle[]> {
    const { data, error } = await this.supabase
      .rpc('match_articles_wide', {
        query_item_id: itemId,
        match_count: limit,
        days_window: 90,
      })

    if (error || !data) return []
    return data as RelatedArticle[]
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
