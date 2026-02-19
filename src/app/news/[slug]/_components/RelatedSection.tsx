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

interface RelatedSectionProps {
  title: string
  articles: RelatedArticle[]
}

function SimilarityBar({ similarity }: { similarity: number }) {
  const pct = Math.round(similarity * 100)
  const filled = Math.round(pct / 10)
  return (
    <div className="flex items-center gap-2">
      <div className="flex gap-[2px]">
        {Array.from({ length: 10 }).map((_, i) => (
          <div
            key={i}
            className={`w-1.5 h-3 rounded-sm ${
              i < filled ? 'bg-neutral-700' : 'bg-neutral-200'
            }`}
          />
        ))}
      </div>
      <span className="text-[11px] text-neutral-400 tabular-nums w-8">{pct}%</span>
    </div>
  )
}

export default function RelatedSection({ title, articles }: RelatedSectionProps) {
  if (!articles.length) return null

  return (
    <section>
      <h2 className="font-serif text-lg text-neutral-900 border-b-2 border-neutral-900 pb-2 mb-4">
        {title}
      </h2>
      <div className="space-y-3">
        {articles.map((article, index) => {
          const date = new Date(article.published_at).toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
          })

          const content = (
            <div className="flex items-start gap-3 py-3 border-b border-neutral-100 last:border-b-0 hover:bg-neutral-50 transition-colors -mx-2 px-2 rounded">
              <span className="text-sm font-medium text-neutral-400 tabular-nums pt-0.5 w-5 shrink-0">
                {index + 1}
              </span>
              <div className="flex-1 min-w-0">
                <h3 className="font-serif text-sm leading-snug text-neutral-900 mb-1">
                  {article.title}
                </h3>
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[11px] text-neutral-400">
                    <span className="font-semibold text-neutral-600 uppercase tracking-wide">
                      {categoryLabel(article.feed_name)}
                    </span>
                    {' · '}{date}
                  </span>
                  <SimilarityBar similarity={article.similarity} />
                </div>
              </div>
            </div>
          )

          return article.slug ? (
            <Link key={article.id} href={`/news/${article.slug}`} className="block">
              {content}
            </Link>
          ) : (
            <div key={article.id}>{content}</div>
          )
        })}
      </div>
    </section>
  )
}
