export const revalidate = 86400 // 24h ISR safety net; on-demand revalidation is primary

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
  const items = await service.getNewsItems({ limit: 100 })
  return items.filter(i => i.slug).map(i => ({ slug: i.slug! }))
}

interface ArticlePageProps {
  params: Promise<{ slug: string }>
}

const FEED_TO_LABEL: Record<string, string> = {
  BUSINESS_MARKETS: 'Markets',
  TECH: 'Tech',
  ECONOMY: 'Economy',
  WORLD: 'World',
  POLITICS: 'Politics',
}

const FEED_TO_SLUG: Record<string, string> = {
  BUSINESS_MARKETS: 'markets',
  TECH: 'tech',
  ECONOMY: 'economy',
  WORLD: 'world',
  POLITICS: 'politics',
}

function categoryLabel(feedName: string): string {
  return FEED_TO_LABEL[feedName] || feedName
}

/** Smart subcategory formatting — keep short acronyms uppercase, title-case the rest */
function formatSubcategory(sub: string): string {
  return sub.replace(/-/g, ' ').split(' ').map(word => {
    if (word.length <= 3) return word.toUpperCase()
    return word.charAt(0).toUpperCase() + word.slice(1).toLowerCase()
  }).join(' ')
}

export async function generateMetadata({ params }: ArticlePageProps): Promise<Metadata> {
  const { slug } = await params
  const supabase = createServiceClient()
  const service = new NewsService(supabase)
  const item = await service.getNewsItemBySlug(slug)

  if (!item) {
    return { title: 'Article Not Found | Araverus' }
  }

  const displayTitle = item.title
  const description = item.summary || item.description || undefined
  const canonical = `https://araverus.com/news/${item.slug}`
  const image = item.top_image || 'https://araverus.com/og-news-default.png'
  const imageObj = item.top_image
    ? { url: item.top_image }
    : { url: 'https://araverus.com/og-news-default.png', width: 1200, height: 630 }

  return {
    title: displayTitle,
    description,
    alternates: { canonical },
    openGraph: {
      title: displayTitle,
      description,
      url: canonical,
      type: 'article',
      images: [imageObj],
    },
    twitter: {
      card: 'summary_large_image',
      title: displayTitle,
      description,
      images: [image],
    },
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
    service.getRelatedArticles(item.id, 4),
    item.thread_id ? service.getThreadTimeline(item.thread_id) : Promise.resolve([]),
    item.thread_id ? service.getStoryThread(item.thread_id) : Promise.resolve(null),
    service.getArticleSources(item.id),
  ])

  const date = new Date(item.published_at).toLocaleDateString('en-US', {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
    year: 'numeric',
    timeZone: 'UTC',
  })

  const time = new Date(item.published_at).toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
    timeZone: 'UTC',
  })

  const articleUrl = `https://araverus.com/news/${item.slug}`
  const DEFAULT_OG_IMAGE = 'https://araverus.com/og-news-default.png'
  const displayTitle = item.title

  const jsonLd = [
    {
      '@context': 'https://schema.org',
      '@type': 'NewsArticle',
      url: articleUrl,
      headline: displayTitle,
      description: item.description || undefined,
      articleBody: item.summary || item.description || undefined,
      articleSection: categoryLabel(item.feed_name),
      inLanguage: 'en',
      isAccessibleForFree: true,
      datePublished: item.published_at,
      dateModified: item.published_at,
      author: { '@type': 'Organization', name: 'Araverus', url: 'https://araverus.com' },
      publisher: {
        '@type': 'Organization',
        name: 'Araverus',
        url: 'https://araverus.com',
        logo: {
          '@type': 'ImageObject',
          url: 'https://araverus.com/logo-publisher.png',
          width: 600,
          height: 60,
        },
      },
      mainEntityOfPage: { '@type': 'WebPage', '@id': articleUrl },
      image: item.top_image
        ? { '@type': 'ImageObject', url: item.top_image }
        : { '@type': 'ImageObject', url: DEFAULT_OG_IMAGE, width: 1200, height: 630 },
      ...(item.keywords?.length ? { keywords: item.keywords.join(', ') } : {}),
    },
    {
      '@context': 'https://schema.org',
      '@type': 'BreadcrumbList',
      itemListElement: [
        { '@type': 'ListItem', position: 1, name: 'News', item: 'https://araverus.com/news' },
        {
          '@type': 'ListItem',
          position: 2,
          name: categoryLabel(item.feed_name),
          item: `https://araverus.com/news/c/${FEED_TO_SLUG[item.feed_name] || item.feed_name.toLowerCase()}`,
        },
        { '@type': 'ListItem', position: 3, name: displayTitle, item: articleUrl },
      ],
    },
  ]

  return (
    <NewsShell>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify(jsonLd)
            .replace(/</g, '\\u003c')
            .replace(/>/g, '\\u003e')
            .replace(/&/g, '\\u0026'),
        }}
      />
      <div className="px-6 md:px-12 lg:px-16 py-6 pb-32 max-w-3xl mx-auto">
        {/* Breadcrumb nav */}
        <nav className="flex items-center gap-1.5 text-sm text-neutral-400 mb-3" aria-label="Breadcrumb">
          <Link href="/news" className="hover:text-neutral-900 transition-colors">
            News
          </Link>
          <span aria-hidden="true">/</span>
          <Link
            href={`/news/c/${FEED_TO_SLUG[item.feed_name] || item.feed_name.toLowerCase()}`}
            className="hover:text-neutral-900 transition-colors"
          >
            {categoryLabel(item.feed_name)}
          </Link>
          {item.subcategory && item.subcategory.replace(/-/g, ' ').toUpperCase() !== categoryLabel(item.feed_name).toUpperCase() && (
            <>
              <span aria-hidden="true">/</span>
              <span className="text-neutral-500">
                {formatSubcategory(item.subcategory)}
              </span>
            </>
          )}
          {item.importance === 'must_read' && (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-amber-50 border border-amber-200 rounded-full text-[11px] font-medium text-amber-800 ml-2">
              <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
              </svg>
              Must Read
            </span>
          )}
        </nav>

        {/* Headline */}
        <h1 className="font-serif text-3xl md:text-4xl leading-tight text-neutral-900 mb-2">
          {displayTitle}
        </h1>

        {/* Timestamp + Share */}
        <div className="flex items-center justify-between mb-4">
          <p className="text-base text-neutral-400">
            {date} at {time}
          </p>
          <ShareBar
            url={`https://araverus.com/news/${slug}`}
            title={displayTitle}
            palette="neutral"
          />
        </div>

        {/* Hero image from crawled source */}
        {item.top_image && (
          <ArticleHeroImage src={item.top_image} alt={displayTitle} />
        )}

        {/* Keywords — centered */}
        {item.keywords && item.keywords.length > 0 && (
          <div className="mb-4">
            <KeywordPills keywords={item.keywords} variant="hashtag" linkable />
          </div>
        )}

        {/* Key Takeaway */}
        {item.key_takeaway && (
          <aside role="note" aria-label="Key Takeaway" className="bg-amber-50/60 border-l-4 border-amber-400 px-4 py-3 mb-6">
            <p className="font-semibold text-sm text-amber-800 mb-1" aria-hidden="true">Key Takeaway</p>
            <p className="text-base text-neutral-700">{item.key_takeaway}</p>
          </aside>
        )}

        {/* Summary — split into paragraphs for readability */}
        {(item.summary || item.description) && (() => {
          const text = (item.summary?.length ?? 0) >= (item.description?.length ?? 0)
            ? item.summary!
            : item.description!

          // Split text into sentences, respecting abbreviations like U.S., U.K.
          const sentences: string[] = []
          const re = /[.!?]/g
          let m: RegExpExecArray | null
          let lastEnd = 0
          while ((m = re.exec(text)) !== null) {
            const idx = m.index
            if (text[idx] === '.') {
              const before = text.slice(Math.max(0, idx - 2), idx)
              if (/(?:^|[.\s])([A-Z])$/.test(before)) continue
              if (idx + 1 < text.length && text[idx + 1] !== ' ') continue
            }
            sentences.push(text.slice(lastEnd, idx + 1).trim())
            lastEnd = idx + 1
          }
          const remaining = text.slice(lastEnd).trim()
          if (remaining) sentences.push(remaining)

          // Group into paragraphs: first sentence alone (lead), then 2-3 sentences each
          const lead = sentences[0] || text
          const rest = sentences.slice(1)
          const paragraphs: string[] = []
          for (let i = 0; i < rest.length; i += 2) {
            paragraphs.push(rest.slice(i, i + 2).join(' '))
          }

          return (
            <div className="text-lg leading-8 mb-6 space-y-4">
              <p className="text-neutral-600">{lead}</p>
              {paragraphs.length > 0 && (
                <div className="max-w-2xl space-y-4">
                  {paragraphs.map((p, i) => (
                    <p key={i} className="text-neutral-600">{p}</p>
                  ))}
                </div>
              )}
            </div>
          )
        })()}

        {/* Story Timeline — same thread across days */}
        {thread && timeline.length > 1 && (
          <div className="mt-8 pt-8 border-t border-neutral-200">
            <TimelineSection
              threadTitle={thread.title}
              articles={timeline}
              currentId={item.id}
            />
          </div>
        )}

        {/* Source links */}
        <div className="mt-8 pt-8 border-t border-neutral-200" />
        <SourceList
          sources={sources}
          wsjUrl={item.link}
          wsjTitle={item.wsjTitle}
        />

        {/* Related Articles — exclude storyline articles */}
        {(() => {
          const timelineIds = new Set(timeline.map(a => a.id))
          const filtered = related.filter(a => !timelineIds.has(a.id))
          return filtered.length > 0 ? (
            <div className="mt-8 pt-8 border-t border-neutral-200">
              <RelatedSection title="Related Articles" articles={filtered} />
            </div>
          ) : null
        })()}

        {/* Footer */}
        <div className="border-t border-neutral-200 pt-6 text-center" />
      </div>
    </NewsShell>
  )
}
