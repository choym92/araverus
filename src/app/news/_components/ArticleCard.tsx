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
  category: string
  timestamp: string
  imageUrl: string | null
  link: string
  variant?: Variant
  slug?: string | null
  importance?: string | null
  keywords?: string[] | null
  activeKeywords?: string[]
  threadTimeline?: NewsItem[] | null
  threadTitle?: string | null
  sourceCount?: number
  subcategory?: string | null
  /** ID of the article this card represents, used to find self in thread timeline */
  itemId?: string
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

/** Extract the first sentence, truncating at maxLen if too long. */
function firstSentence(text: string, maxLen = 250): string {
  // Walk through each . ! ? and check if it's a real sentence boundary
  const re = /[.!?]/g
  let m: RegExpExecArray | null
  while ((m = re.exec(text)) !== null) {
    const idx = m.index
    const ch = text[idx]
    // Skip periods that look like abbreviations: single letter before dot (U.S., U.K.)
    // or no space / end-of-string after the dot (e.g. mid-abbreviation)
    if (ch === '.') {
      const before = text.slice(Math.max(0, idx - 2), idx)
      // Single uppercase letter before dot: likely abbreviation like U.S.
      if (/(?:^|[.\s])([A-Z])$/.test(before)) continue
      // Not followed by space or end — not a sentence break
      if (idx + 1 < text.length && text[idx + 1] !== ' ') continue
    }
    const sentence = text.slice(0, idx + 1).trim()
    if (sentence.length <= maxLen) return sentence
    break
  }
  // No valid sentence boundary found or too long — truncate
  if (text.length <= maxLen) return text
  return text.slice(0, maxLen).replace(/\s+\S*$/, '') + '…'
}


function ImportanceBadge({ importance }: { importance: string }) {
  if (importance !== 'must_read') return null
  return (
    <span className="inline-flex items-center gap-0.5 shrink-0">
      <svg className="w-3.5 h-3.5 text-amber-500" fill="currentColor" viewBox="0 0 20 20">
        <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
      </svg>
      <span className="text-[10px] font-semibold uppercase tracking-wide text-amber-600">Top Story</span>
    </span>
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
      <Link href={`/news/${slug}`} prefetch={false} className={className}>
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
  category,
  timestamp,
  imageUrl,
  link,
  variant = 'standard',
  slug,
  importance,
  keywords,
  activeKeywords = [],
  threadTimeline,
  threadTitle,
  sourceCount = 0,
  itemId,
}: ArticleCardProps) {
  const [imageError, setImageError] = useState(false)
  const hasThread = threadTimeline && threadTimeline.length > 1
  // Start at this card's own article in the timeline, fallback to latest
  const selfIndex = hasThread ? threadTimeline.findIndex(a => a.id === itemId) : -1
  const initialIndex = selfIndex >= 0 ? selfIndex : (hasThread ? threadTimeline.length - 1 : 0)
  const [carouselIndex, setCarouselIndex] = useState(initialIndex)
  const [direction, setDirection] = useState<1 | -1>(1)

  // Display data: always use carousel data when thread exists, else original props
  const current = hasThread ? threadTimeline[carouselIndex] : null
  const activeHeadline = current ? current.title : headline
  const activeSummary = current ? (current.summary ?? current.description) : summary
  const activeSourceCount = current ? current.source_count : sourceCount
  const activeCategory = current ? current.feed_name : category
  const activeTimestamp = current ? current.published_at : timestamp
  const activeImage = current ? current.top_image : imageUrl
  const activeLink = current ? current.link : link
  const activeSlug = current ? current.slug : slug
  const activeImportance = current ? current.importance : importance
  const displayKeywords = current ? current.keywords : keywords


  const isMustRead = activeImportance === 'must_read'

  const handlePrev = (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (carouselIndex > 0) {
      setDirection(-1)
      setCarouselIndex(carouselIndex - 1)
      setImageError(false)
    }
  }

  const handleNext = (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (hasThread && carouselIndex < threadTimeline.length - 1) {
      setDirection(1)
      setCarouselIndex(carouselIndex + 1)
      setImageError(false)
    }
  }

  if (variant === 'featured') {
    return (
      <article className="pb-6 mb-6">
        <CardWrapper slug={activeSlug} link={activeLink} className="group block">
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
              <p className="text-xs text-neutral-400 mb-2 flex items-center gap-1.5">
                {isMustRead && <ImportanceBadge importance="must_read" />}
                <span className="font-semibold text-neutral-900 uppercase tracking-wide">{categoryLabel(activeCategory)}</span>
                <span className="ml-auto">{timeAgo(activeTimestamp)}</span>
                {activeSourceCount > 1 && (
                  <>
                    <span className="text-neutral-300">·</span>
                    <span>{activeSourceCount} sources</span>
                  </>
                )}
              </p>
              {activeImage && !imageError && (
                <div className="relative w-full aspect-[2.5/1] mb-5 overflow-hidden rounded">
                  <Image
                    src={activeImage}
                    alt=""
                    fill
                    className="object-cover group-hover:scale-105 transition-transform duration-300"
                    sizes="(max-width: 768px) 100vw, 600px"
                    onError={() => setImageError(true)}
                  />
                </div>
              )}
              <h2 className="font-serif text-2xl md:text-3xl font-semibold leading-tight text-neutral-900 group-hover:text-neutral-600 transition-colors mb-2">
                {activeHeadline}
              </h2>
              {activeSummary && (
                <p className="text-sm text-neutral-500 leading-relaxed line-clamp-3 mb-2">
                  {activeSummary}
                </p>
              )}
              {displayKeywords && displayKeywords.length > 0 && (
                <div className="flex justify-center mt-2">
                  <KeywordPills keywords={displayKeywords} activeKeywords={activeKeywords} />
                </div>
              )}
            </motion.div>
          </AnimatePresence>
        </CardWrapper>
        {hasThread && (
          <div className="mt-2 px-1 py-1.5 flex items-center justify-center gap-1 text-xs text-neutral-500">
            <button
              onClick={handlePrev}
              disabled={carouselIndex === 0}
              className="p-0.5 rounded hover:bg-neutral-200 disabled:opacity-30 disabled:cursor-default transition-colors"
              aria-label="Previous article in thread"
            >
              <ChevronLeft className="w-3 h-3" />
            </button>
            <div className="w-12 h-1 bg-neutral-200 rounded-full overflow-hidden shrink-0">
              <div
                className="h-full bg-neutral-500 rounded-full transition-all duration-300"
                style={{ width: `${((carouselIndex + 1) / threadTimeline.length) * 100}%` }}
              />
            </div>
            <span className="font-medium tabular-nums text-[11px]">
              {carouselIndex + 1}/{threadTimeline.length}
            </span>
            <button
              onClick={handleNext}
              disabled={carouselIndex === threadTimeline.length - 1}
              className="p-0.5 rounded hover:bg-neutral-200 disabled:opacity-30 disabled:cursor-default transition-colors"
              aria-label="Next article in thread"
            >
              <ChevronRight className="w-3 h-3" />
            </button>
            {threadTitle && (
              <span className="min-w-0 text-neutral-500 font-medium truncate max-w-[60%]" title={threadTitle}>
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
      className="pb-5 mb-5 border-b border-neutral-200"
    >
      <CardWrapper slug={activeSlug} link={activeLink} className="group block">
        <div>
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
              <div>
                <div className="flex items-center gap-1.5 mb-1.5 text-[11px]">
                  {isMustRead && <ImportanceBadge importance="must_read" />}
                  <span className="font-semibold text-neutral-900 uppercase tracking-wide">
                    {categoryLabel(activeCategory)}
                  </span>
                  <span className="text-neutral-400 ml-auto">{timeAgo(activeTimestamp)}</span>
                  {activeSourceCount > 1 && (
                    <>
                      <span className="text-neutral-300">·</span>
                      <span className="text-neutral-400">{activeSourceCount} sources</span>
                    </>
                  )}
                </div>
                <div>
                  {activeImage && !imageError && (
                    <div className="relative w-24 h-24 float-left overflow-hidden rounded mt-0.5 mr-4 mb-1">
                      <Image
                        src={activeImage}
                        alt=""
                        fill
                        className="object-cover group-hover:scale-105 transition-transform duration-300"
                        sizes="96px"
                        onError={() => setImageError(true)}
                      />
                    </div>
                  )}
                  <h3 className="font-serif text-lg font-semibold leading-snug text-neutral-900 group-hover:text-neutral-600 transition-colors mb-1.5" style={{ textWrap: 'balance' }}>
                    {activeHeadline}
                  </h3>
                  {activeSummary && (
                    <p className="text-sm text-neutral-500 leading-relaxed" style={{ textWrap: 'pretty' }}>
                      {firstSentence(activeSummary)}
                    </p>
                  )}
                </div>
                {displayKeywords && displayKeywords.length > 0 && (
                  <div className="mt-1.5 clear-left">
                    <KeywordPills keywords={displayKeywords} activeKeywords={activeKeywords} />
                  </div>
                )}
              </div>
          </motion.div>
        </AnimatePresence>
        </div>
      </CardWrapper>
      {hasThread && (
        <div className="mt-2 px-1 py-2 flex items-center gap-1 text-xs text-neutral-500">
          <button
            onClick={handlePrev}
            disabled={carouselIndex === 0}
            className="p-0.5 rounded hover:bg-neutral-200 disabled:opacity-30 disabled:cursor-default transition-colors"
            aria-label="Previous article in thread"
          >
            <ChevronLeft className="w-3 h-3" />
          </button>
          <div className="w-9 h-1 bg-neutral-200 rounded-full overflow-hidden shrink-0">
            <div
              className="h-full bg-neutral-500 rounded-full transition-all duration-300"
              style={{ width: `${((carouselIndex + 1) / threadTimeline.length) * 100}%` }}
            />
          </div>
          <span className="font-medium tabular-nums text-[11px]">
            {carouselIndex + 1}/{threadTimeline.length}
          </span>
          <button
            onClick={handleNext}
            disabled={carouselIndex === threadTimeline.length - 1}
            className="p-0.5 rounded hover:bg-neutral-200 disabled:opacity-30 disabled:cursor-default transition-colors"
            aria-label="Next article in thread"
          >
            <ChevronRight className="w-3 h-3" />
          </button>
          {threadTitle && (
            <span className="flex-1 min-w-0 text-neutral-500 font-medium truncate" title={threadTitle}>
              {threadTitle}
            </span>
          )}
        </div>
      )}
    </article>
  )
}
