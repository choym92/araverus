'use client'

import { useState } from 'react'
import Image from 'next/image'
import Link from 'next/link'
import { AnimatePresence, motion } from 'framer-motion'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import KeywordPills from './KeywordPills'
import type { NewsItem } from '@/lib/news-service'

type Variant = 'featured' | 'standard'

interface ArticleCardProps {
  headline: string
  summary: string | null
  source: string | null
  category: string
  timestamp: string
  imageUrl: string | null
  link: string
  variant?: Variant
  slug?: string | null
  importance?: string | null
  keywords?: string[] | null
  activeKeywords?: string[]
  id?: string
  threadTimeline?: NewsItem[] | null
  threadTitle?: string | null
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

function ImportanceBadge({ importance }: { importance: string }) {
  if (importance !== 'must_read') return null
  return (
    <svg className="w-3.5 h-3.5 text-amber-500 shrink-0" fill="currentColor" viewBox="0 0 20 20">
      <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
    </svg>
  )
}

function CardWrapper({
  slug,
  link,
  children,
  className,
}: {
  slug?: string | null
  link: string
  children: React.ReactNode
  className?: string
}) {
  if (slug) {
    return (
      <Link href={`/news/${slug}`} className={className}>
        {children}
      </Link>
    )
  }
  return (
    <a href={link} target="_blank" rel="noopener noreferrer" className={className}>
      {children}
    </a>
  )
}

const slideVariants = {
  enter: (dir: number) => ({ x: dir > 0 ? 60 : -60, opacity: 0 }),
  center: { x: 0, opacity: 1 },
  exit: (dir: number) => ({ x: dir > 0 ? -60 : 60, opacity: 0 }),
}

export default function ArticleCard({
  headline,
  summary,
  source,
  category,
  timestamp,
  imageUrl,
  link,
  variant = 'standard',
  slug,
  importance,
  keywords,
  activeKeywords = [],
  id,
  threadTimeline,
  threadTitle,
}: ArticleCardProps) {
  const hasThread = threadTimeline && threadTimeline.length > 1
  // Start at the latest article (end of timeline, sorted ascending by published_at)
  const initialIndex = hasThread ? threadTimeline.length - 1 : 0
  const [carouselIndex, setCarouselIndex] = useState(initialIndex)
  const [direction, setDirection] = useState<1 | -1>(1)

  // Display data: use carousel item if navigated away from initial, else original props
  const current = hasThread ? threadTimeline[carouselIndex] : null
  const isNavigated = carouselIndex !== initialIndex && hasThread && current != null
  const activeHeadline = isNavigated ? current.title : headline
  const activeSummary = isNavigated ? (current.summary ?? current.description) : summary
  const activeSource = isNavigated ? current.source : source
  const activeCategory = isNavigated ? current.feed_name : category
  const activeTimestamp = isNavigated ? current.published_at : timestamp
  const activeImage = isNavigated ? current.top_image : imageUrl
  const activeLink = isNavigated ? current.link : link
  const activeSlug = isNavigated ? current.slug : slug
  const activeImportance = isNavigated ? current.importance : importance
  const displayKeywords = isNavigated ? current.keywords : keywords

  const isMustRead = activeImportance === 'must_read'
  const isOptional = activeImportance === 'optional'

  const handlePrev = (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (carouselIndex > 0) {
      setDirection(-1)
      setCarouselIndex(carouselIndex - 1)
    }
  }

  const handleNext = (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (hasThread && carouselIndex < threadTimeline.length - 1) {
      setDirection(1)
      setCarouselIndex(carouselIndex + 1)
    }
  }

  if (variant === 'featured') {
    return (
      <article className={`pb-6 mb-6 ${
        isMustRead
          ? 'bg-white rounded-xl shadow-[0_2px_20px_rgba(245,158,11,0.2)] hover:shadow-[0_4px_25px_rgba(245,158,11,0.3)] transition-shadow p-4'
          : ''
      }`}>
        <CardWrapper slug={activeSlug} link={activeLink} className="group block text-center">
          <AnimatePresence custom={direction} mode="wait">
            <motion.div
              key={carouselIndex}
              custom={direction}
              variants={slideVariants}
              initial="enter"
              animate="center"
              exit="exit"
              transition={{ duration: 0.25 }}
            >
              {activeImage && (
                <div className="relative w-full aspect-[4/3] mb-5 overflow-hidden rounded">
                  <Image
                    src={activeImage}
                    alt=""
                    fill
                    className="object-cover group-hover:scale-105 transition-transform duration-300"
                    sizes="(max-width: 768px) 100vw, 600px"
                  />
                </div>
              )}
              <div className="flex items-center justify-center gap-2 mb-2">
                {isMustRead && <ImportanceBadge importance="must_read" />}
                <h2 className="font-serif text-2xl md:text-3xl leading-tight text-neutral-900 group-hover:text-neutral-600 transition-colors">
                  {activeHeadline}
                </h2>
              </div>
              {activeSummary && (
                <p className="text-base text-neutral-500 leading-relaxed line-clamp-3 max-w-lg mx-auto mb-2">
                  {activeSummary}
                </p>
              )}
              {displayKeywords && displayKeywords.length > 0 && (
                <div className="flex justify-center mt-2">
                  <KeywordPills keywords={displayKeywords} activeKeywords={activeKeywords} />
                </div>
              )}
              {activeSource && (
                <p className="text-xs text-neutral-400 mt-2">
                  via {activeSource}
                </p>
              )}
            </motion.div>
          </AnimatePresence>
        </CardWrapper>
        {hasThread && (
          <div className="bg-neutral-50 rounded-lg mt-1 px-2 py-2 flex items-center justify-center gap-1 text-xs text-neutral-500">
            <button
              onClick={handlePrev}
              disabled={carouselIndex === 0}
              className="p-0.5 rounded hover:bg-neutral-200 disabled:opacity-30 disabled:cursor-default transition-colors"
              aria-label="Previous article in thread"
            >
              <ChevronLeft className="w-3.5 h-3.5" />
            </button>
            <span className="font-medium tabular-nums">
              {carouselIndex + 1}/{threadTimeline.length}
            </span>
            <button
              onClick={handleNext}
              disabled={carouselIndex === threadTimeline.length - 1}
              className="p-0.5 rounded hover:bg-neutral-200 disabled:opacity-30 disabled:cursor-default transition-colors"
              aria-label="Next article in thread"
            >
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
            {threadTitle && (
              <span className="text-neutral-600 font-medium truncate ml-1" title={threadTitle}>
                {threadTitle}
              </span>
            )}
          </div>
        )}
      </article>
    )
  }

  // standard variant
  return (
    <article
      className={`pb-5 mb-5 ${
        isMustRead
          ? 'bg-white rounded-xl shadow-[0_2px_20px_rgba(245,158,11,0.2)] hover:shadow-[0_4px_25px_rgba(245,158,11,0.3)] transition-shadow p-4'
          : 'border-b border-neutral-200'
      } ${isOptional ? 'opacity-70' : ''}`}
    >
      <CardWrapper slug={activeSlug} link={activeLink} className="group block">
        <div className={`${hasThread ? 'h-36 overflow-hidden' : ''}`}>
          <AnimatePresence custom={direction} mode="wait">
            <motion.div
              key={carouselIndex}
              custom={direction}
              variants={slideVariants}
              initial="enter"
              animate="center"
              exit="exit"
              transition={{ duration: 0.25 }}
            >
              <div className="flex gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1.5">
                    {isMustRead && <ImportanceBadge importance="must_read" />}
                    <span className="text-[11px] font-semibold text-neutral-900 uppercase tracking-wide">
                      {categoryLabel(activeCategory)}
                    </span>
                    <span className="text-[11px] text-neutral-400">{timeAgo(activeTimestamp)}</span>
                    {activeSource && (
                      <span className="text-[11px] text-neutral-400 ml-auto">
                        via {activeSource}
                      </span>
                    )}
                  </div>
                  <h3 className="font-serif text-lg leading-snug text-neutral-900 group-hover:text-neutral-600 transition-colors mb-1.5 line-clamp-2">
                    {activeHeadline}
                  </h3>
                  {activeSummary && (
                    <p className={`text-sm text-neutral-500 leading-relaxed ${hasThread ? 'line-clamp-3' : 'line-clamp-2'}`}>
                      {activeSummary}
                    </p>
                  )}
                  {displayKeywords && displayKeywords.length > 0 && (
                    <div className="mt-2">
                      <KeywordPills keywords={displayKeywords} activeKeywords={activeKeywords} />
                    </div>
                  )}
                </div>
                {activeImage && (
                  <div className="relative w-24 h-24 shrink-0 overflow-hidden rounded">
                    <Image
                      src={activeImage}
                      alt=""
                      fill
                      className="object-cover group-hover:scale-105 transition-transform duration-300"
                      sizes="96px"
                    />
                  </div>
                )}
              </div>
          </motion.div>
        </AnimatePresence>
        </div>
      </CardWrapper>
      {hasThread && (
        <div className="bg-neutral-50 rounded-lg mt-1 px-2 py-2 flex items-center gap-1 text-xs text-neutral-500">
          <button
            onClick={handlePrev}
            disabled={carouselIndex === 0}
            className="p-0.5 rounded hover:bg-neutral-200 disabled:opacity-30 disabled:cursor-default transition-colors"
            aria-label="Previous article in thread"
          >
            <ChevronLeft className="w-3.5 h-3.5" />
          </button>
          <span className="font-medium tabular-nums">
            {carouselIndex + 1}/{threadTimeline.length}
          </span>
          <button
            onClick={handleNext}
            disabled={carouselIndex === threadTimeline.length - 1}
            className="p-0.5 rounded hover:bg-neutral-200 disabled:opacity-30 disabled:cursor-default transition-colors"
            aria-label="Next article in thread"
          >
            <ChevronRight className="w-3.5 h-3.5" />
          </button>
          {threadTitle && (
            <span className="text-neutral-600 font-medium truncate ml-1" title={threadTitle}>
              {threadTitle}
            </span>
          )}
        </div>
      )}
    </article>
  )
}
