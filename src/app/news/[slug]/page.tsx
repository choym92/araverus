import { notFound } from 'next/navigation'
import Link from 'next/link'
import type { Metadata } from 'next'
import { createClient } from '@/lib/supabase-server'
import { NewsService } from '@/lib/news-service'
import NewsShell from '../_components/NewsShell'
import KeywordPills from '../_components/KeywordPills'
import RelatedSection from './_components/RelatedSection'
import TimelineSection from './_components/TimelineSection'
import MoreLikeThisSection from './_components/MoreLikeThisSection'

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
  const supabase = await createClient()
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
  const supabase = await createClient()
  const service = new NewsService(supabase)

  const item = await service.getNewsItemBySlug(slug)
  if (!item) notFound()

  // Fetch related data in parallel
  const [related, timeline, moreLikeThis, thread] = await Promise.all([
    service.getRelatedArticles(item.id, 5),
    item.thread_id ? service.getThreadTimeline(item.thread_id) : Promise.resolve([]),
    service.getMoreLikeThis(item.id, 5),
    item.thread_id ? service.getStoryThread(item.thread_id) : Promise.resolve(null),
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
      <div className="px-6 md:px-12 lg:px-16 py-6 max-w-3xl mx-auto">
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

        {/* Category + timestamp */}
        <div className="flex items-center gap-2 mb-3">
          <span className="text-xs font-semibold text-neutral-900 uppercase tracking-wide">
            {categoryLabel(item.feed_name)}
          </span>
          <span className="text-xs text-neutral-400">
            {date} at {time}
          </span>
        </div>

        {/* Headline */}
        <h1 className="font-serif text-3xl md:text-4xl leading-tight text-neutral-900 mb-4">
          {item.title}
        </h1>

        {/* Summary — prefer the longer of summary vs description */}
        {(item.summary || item.description) && (
          <div className="border-l-4 border-neutral-200 pl-4 mb-6">
            <p className="text-base text-neutral-600 leading-relaxed">
              {(item.summary?.length ?? 0) >= (item.description?.length ?? 0)
                ? item.summary
                : item.description}
            </p>
          </div>
        )}

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

        {/* Importance badge */}
        {item.importance === 'must_read' && (
          <div className="inline-flex items-center gap-1.5 px-3 py-1 bg-amber-50 border border-amber-200 rounded-full text-xs font-medium text-amber-800 mb-4">
            <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
              <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
            </svg>
            Must Read
          </div>
        )}

        {/* Keywords */}
        {item.keywords && item.keywords.length > 0 && (
          <div className="mb-6">
            <KeywordPills keywords={item.keywords} linkable />
          </div>
        )}

        {/* Source links */}
        <div className="flex flex-col sm:flex-row gap-3 mb-12">
          {item.resolved_url && item.source && (
            <a
              href={item.resolved_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 px-4 py-2.5 bg-neutral-900 text-white text-sm font-medium rounded-lg hover:bg-neutral-700 transition-colors"
            >
              Read on {item.source}
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25" />
              </svg>
            </a>
          )}
          <a
            href={item.link}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 px-4 py-2.5 border border-neutral-300 text-neutral-700 text-sm font-medium rounded-lg hover:bg-neutral-50 transition-colors"
          >
            Original on WSJ
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25" />
            </svg>
          </a>
        </div>

        {/* Related Articles — same-day pgvector */}
        {related.length > 0 && (
          <div className="mb-10">
            <RelatedSection title="Related Articles" articles={related} />
          </div>
        )}

        {/* More Like This — 90-day pgvector */}
        {moreLikeThis.length > 0 && (
          <div className="mb-10">
            <MoreLikeThisSection articles={moreLikeThis} />
          </div>
        )}

        {/* Footer */}
        <div className="border-t border-neutral-200 pt-6 text-center">
          <p className="text-xs text-neutral-400">
            Data sourced from public RSS feeds and crawled articles. Not affiliated with The Wall Street Journal.
          </p>
        </div>
      </div>
    </NewsShell>
  )
}
