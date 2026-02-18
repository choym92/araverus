import Image from 'next/image'
import Link from 'next/link'
import KeywordPills from './KeywordPills'

type Variant = 'featured' | 'standard' | 'compact'

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
  activeKeyword?: string | null
  scoreDisplay?: 'visual' | 'numeric'
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

function ImportanceBadge({ importance, variant }: { importance: string; variant: 'visual' | 'numeric' }) {
  if (importance !== 'must_read') return null

  if (variant === 'numeric') {
    return (
      <span className="text-[10px] font-semibold text-amber-700 uppercase tracking-wide">
        Must Read
      </span>
    )
  }

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
  activeKeyword,
  scoreDisplay = 'visual',
}: ArticleCardProps) {
  const isMustRead = importance === 'must_read'
  const isOptional = importance === 'optional'

  if (variant === 'featured') {
    return (
      <article className={`pb-6 mb-6 ${isMustRead ? 'border-l-2 border-amber-400 pl-4' : ''}`}>
        <CardWrapper slug={slug} link={link} className="group block text-center">
          {imageUrl && (
            <div className="relative w-full aspect-[4/3] mb-5 overflow-hidden rounded">
              <Image
                src={imageUrl}
                alt=""
                fill
                className="object-cover group-hover:scale-105 transition-transform duration-300"
                sizes="(max-width: 768px) 100vw, 600px"
              />
            </div>
          )}
          <div className="flex items-center justify-center gap-2 mb-2">
            {isMustRead && <ImportanceBadge importance="must_read" variant={scoreDisplay} />}
            <h2 className="font-serif text-2xl md:text-3xl leading-tight text-neutral-900 group-hover:text-neutral-600 transition-colors">
              {headline}
            </h2>
          </div>
          {summary && (
            <p className="text-base text-neutral-500 leading-relaxed line-clamp-3 max-w-lg mx-auto mb-2">
              {summary}
            </p>
          )}
          {keywords && keywords.length > 0 && (
            <div className="flex justify-center mt-2">
              <KeywordPills keywords={keywords} activeKeyword={activeKeyword} />
            </div>
          )}
          {source && (
            <p className="text-xs text-neutral-400 mt-2">
              via {source}
            </p>
          )}
        </CardWrapper>
      </article>
    )
  }

  if (variant === 'compact') {
    return (
      <article className={`border-b border-neutral-100 py-3 ${isOptional ? 'opacity-70' : ''}`}>
        <CardWrapper slug={slug} link={link} className="group block">
          <div className="flex items-center gap-2 mb-1">
            {isMustRead && <ImportanceBadge importance="must_read" variant={scoreDisplay} />}
            <span className="text-[11px] font-semibold text-neutral-900 uppercase tracking-wide">
              {categoryLabel(category)}
            </span>
            <span className="text-[11px] text-neutral-400">{timeAgo(timestamp)}</span>
          </div>
          <h3 className="font-serif text-sm leading-snug text-neutral-900 group-hover:text-neutral-600 transition-colors">
            {headline}
          </h3>
        </CardWrapper>
      </article>
    )
  }

  // standard variant
  return (
    <article
      className={`border-b border-neutral-200 pb-5 mb-5 ${
        isMustRead ? 'border-l-2 border-amber-400 pl-4' : ''
      } ${isOptional ? 'opacity-70' : ''}`}
    >
      <CardWrapper slug={slug} link={link} className="group block">
        <div className="flex gap-4">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1.5">
              {isMustRead && <ImportanceBadge importance="must_read" variant={scoreDisplay} />}
              <span className="text-[11px] font-semibold text-neutral-900 uppercase tracking-wide">
                {categoryLabel(category)}
              </span>
              <span className="text-[11px] text-neutral-400">{timeAgo(timestamp)}</span>
            </div>
            <h3 className="font-serif text-lg leading-snug text-neutral-900 group-hover:text-neutral-600 transition-colors mb-1.5">
              {headline}
            </h3>
            {summary && (
              <p className="text-sm text-neutral-500 leading-relaxed line-clamp-2">
                {summary}
              </p>
            )}
            {keywords && keywords.length > 0 && (
              <div className="mt-2">
                <KeywordPills keywords={keywords} activeKeyword={activeKeyword} />
              </div>
            )}
            {source && (
              <p className="text-[11px] text-neutral-400 mt-1.5">
                via {source}
              </p>
            )}
          </div>
          {imageUrl && (
            <div className="relative w-24 h-24 shrink-0 overflow-hidden rounded">
              <Image
                src={imageUrl}
                alt=""
                fill
                className="object-cover group-hover:scale-105 transition-transform duration-300"
                sizes="96px"
              />
            </div>
          )}
        </div>
      </CardWrapper>
    </article>
  )
}
