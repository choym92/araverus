export const revalidate = 7200 // ISR: cache for 2 hours

import { notFound } from 'next/navigation'
import Link from 'next/link'
import type { Metadata } from 'next'
import { createServiceClient } from '@/lib/supabase-server'
import { NewsService } from '@/lib/news-service'
import NewsShell from '../_components/NewsShell'
import KeywordPills from '../_components/KeywordPills'
import RelatedSection from './_components/RelatedSection'
import TimelineSection from './_components/TimelineSection'
import SourceList from '../_components/SourceList'
import ShareBar from '@/components/ShareBar'
import ArticleHeroImage from './_components/ArticleHeroImage'

/** Pre-render recent articles at build time for instant first load */
export async function generateStaticParams() {
  const supabase = createServiceClient()
  const service = new NewsService(supabase)
  const items = await service.getNewsItems({ limit: 50 })
  return items.filter(i => i.slug).map(i => ({ slug: i.slug! }))
}

interface ArticlePageProps {
  params: Promise<{ slug: string }>
}

function categoryLabel(feedName: string): string {
  const map: Record<string, string> = {
    BUSINESS_MARKETS: 'Markets',
    TECH: 'Tech',
    ECONOMY: 'Economy',
    WORLD: 'World',
    POLITICS: 'Politics',
  }
  return map[feedName] || feedName
}

export async function generateMetadata({ params }: ArticlePageProps): Promise<Metadata> {
  const { slug } = await params
  const supabase = createServiceClient()
  const service = new NewsService(supabase)
  const item = await service.getNewsItemBySlug(slug)

  if (!item) {
    return { title: 'Article Not Found | Paul Cho' }
  }

  return {
    title: `${item.title} | Paul Cho`,
    description: item.summary || item.description || undefined,
  }
}

export default async function ArticlePage({ params }: ArticlePageProps) {
  const { slug } = await params
  const supabase = createServiceClient()
  const service = new NewsService(supabase)

  const item = await service.getNewsItemBySlug(slug)
  if (!item) notFound()

  // Fetch related data in parallel
  const [related, timeline, thread, sources] = await Promise.all([
    service.getRelatedArticles(item.id, 5),
    item.thread_id ? service.getThreadTimeline(item.thread_id) : Promise.resolve([]),
    item.thread_id ? service.getStoryThread(item.thread_id) : Promise.resolve(null),
    service.getArticleSources(item.id),
  ])

  const date = new Date(item.published_at).toLocaleDateString('en-US', {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  })

  const time = new Date(item.published_at).toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
  })

  return (
    <NewsShell>
      <div className="px-6 md:px-12 lg:px-16 py-6 pb-32 max-w-3xl mx-auto">
        {/* Back nav */}
        <Link
          href="/news"
          className="inline-flex items-center gap-1.5 text-sm text-neutral-500 hover:text-neutral-900 transition-colors mb-6"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
          </svg>
          Back to News
        </Link>

        {/* Category + Must Read */}
        <div className="flex items-center gap-2 mb-3">
          <span className="text-xs font-semibold text-neutral-900 uppercase tracking-wide flex items-center gap-2">
            {categoryLabel(item.feed_name)}
            {item.subcategory && item.subcategory.replace(/-/g, ' ').toUpperCase() !== categoryLabel(item.feed_name).toUpperCase() && (
              <>
                <span className="text-neutral-300">|</span>
                {item.subcategory.replace(/-/g, ' ')}
              </>
            )}
          </span>
          {item.importance === 'must_read' && (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-amber-50 border border-amber-200 rounded-full text-[11px] font-medium text-amber-800">
              <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
              </svg>
              Must Read
            </span>
          )}
        </div>

        {/* Headline */}
        <h1 className="font-serif text-3xl md:text-4xl leading-tight text-neutral-900 mb-2">
          {item.title}
        </h1>

        {/* Timestamp — below title */}
        <p className="text-sm text-neutral-400 mb-4">
          {date} at {time}
        </p>

        {/* Hero image from crawled source */}
        {item.top_image && (
          <ArticleHeroImage src={item.top_image} alt={item.title} />
        )}

        {/* Keywords + Share */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex-1 min-w-0">
            {item.keywords && item.keywords.length > 0 && (
              <KeywordPills keywords={item.keywords} size="sm" variant="hashtag" />
            )}
          </div>
          <div className="flex-shrink-0 ml-4">
            <ShareBar
              url={`https://chopaul.com/news/${slug}`}
              title={item.title}
              palette="neutral"
            />
          </div>
        </div>

        {/* Summary — first sentence bold + larger */}
        {(item.summary || item.description) && (() => {
          const text = (item.summary?.length ?? 0) >= (item.description?.length ?? 0)
            ? item.summary!
            : item.description!
          // Find first real sentence boundary, skipping abbreviations like U.S., U.K.
          const re = /[.!?]/g
          let m: RegExpExecArray | null
          let splitIdx = -1
          while ((m = re.exec(text)) !== null) {
            const idx = m.index
            if (text[idx] === '.') {
              const before = text.slice(Math.max(0, idx - 2), idx)
              if (/(?:^|[.\s])([A-Z])$/.test(before)) continue
              if (idx + 1 < text.length && text[idx + 1] !== ' ') continue
            }
            splitIdx = idx
            break
          }
          const firstSentence = splitIdx >= 0 ? text.slice(0, splitIdx + 1).trim() : text
          const rest = splitIdx >= 0 ? text.slice(splitIdx + 1).trim() : ''
          return (
            <p className="text-base text-neutral-500 leading-relaxed mb-6">
              <span className="font-semibold text-neutral-700">{firstSentence}</span>
              {rest && <> {rest}</>}
            </p>
          )
        })()}

        {/* Story Timeline — same thread across days */}
        {thread && timeline.length > 1 && (
          <div className="mb-8">
            <TimelineSection
              threadTitle={thread.title}
              articles={timeline}
              currentId={item.id}
            />
          </div>
        )}

        {/* Source links */}
        <SourceList sources={sources} wsjUrl={item.link} wsjTitle={item.title} />

        {/* Related Articles — exclude storyline articles */}
        {(() => {
          const timelineIds = new Set(timeline.map(a => a.id))
          const filtered = related.filter(a => !timelineIds.has(a.id))
          return filtered.length > 0 ? (
            <div className="mb-10">
              <RelatedSection title="Related Articles" articles={filtered} />
            </div>
          ) : null
        })()}

        {/* Footer */}
        <div className="border-t border-neutral-200 pt-6 text-center">
          <p className="text-xs text-neutral-400">
            Data sourced from public RSS feeds and News APIs.
          </p>
        </div>
      </div>
    </NewsShell>
  )
}
