'use client'

import { useState } from 'react'
import Image from 'next/image'
import Link from 'next/link'
import type { RelatedArticle } from '@/lib/news-service'

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

function timeAgo(timestamp: string): string {
  const diff = Date.now() - new Date(timestamp).getTime()
  const hours = Math.floor(diff / (1000 * 60 * 60))
  if (hours < 1) return 'Just now'
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  if (days === 1) return '1d ago'
  return `${days}d ago`
}


function importanceStars(importance: string | null): string {
  if (importance === 'must_read') return '★★★'
  if (importance === 'worth_reading') return '★★'
  return '★'
}

function RelatedCard({ article }: { article: RelatedArticle }) {
  const [imgError, setImgError] = useState(false)
  const showImage = article.top_image && !imgError

  const content = (
    <div className="group flex gap-4 h-full">
      {showImage && (
        <div className="relative w-28 h-20 flex-shrink-0 overflow-hidden rounded bg-neutral-100">
          <Image
            src={article.top_image!}
            alt=""
            fill
            className="object-cover"
            sizes="112px"
            unoptimized
            onError={() => setImgError(true)}
          />
        </div>
      )}
      <div className="flex flex-col flex-1 min-w-0">
      <div className="flex items-center gap-1.5 text-[11px] mb-1.5">
        <span className="font-semibold text-neutral-900 uppercase tracking-wide">
          {categoryLabel(article.feed_name)}
        </span>
        <span className="text-amber-500">{importanceStars(article.importance)}</span>
        <span className="text-neutral-400 ml-auto">Similarity: {Math.round(article.similarity * 100)}% · {timeAgo(article.published_at)}</span>
      </div>
      <h3 className="font-serif text-base leading-snug text-neutral-900 group-hover:text-neutral-600 transition-colors mb-1.5">
        {article.title}
      </h3>
      {article.summary && (
        <p className="text-sm text-neutral-500 leading-relaxed line-clamp-2">
          {article.summary}
        </p>
      )}
      </div>
    </div>
  )

  if (article.slug) {
    return (
      <Link href={`/news/${article.slug}`} className="block">
        {content}
      </Link>
    )
  }

  return <div>{content}</div>
}

interface RelatedSectionProps {
  title: string
  articles: RelatedArticle[]
}

export default function RelatedSection({ title, articles }: RelatedSectionProps) {
  if (!articles.length) return null

  return (
    <section>
      <h2 className="font-serif text-lg text-neutral-900 border-b-2 border-neutral-900 pb-2 mb-5">
        {title}
      </h2>
      <div className="flex flex-col divide-y divide-neutral-200">
        {articles.map((article) => (
          <div key={article.id} className="py-5 first:pt-0 last:pb-0">
            <RelatedCard article={article} />
          </div>
        ))}
      </div>
    </section>
  )
}
