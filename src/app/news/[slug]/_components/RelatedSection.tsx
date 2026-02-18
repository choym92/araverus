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

export default function RelatedSection({ title, articles }: RelatedSectionProps) {
  if (!articles.length) return null

  return (
    <section>
      <h2 className="font-serif text-lg text-neutral-900 border-b-2 border-neutral-900 pb-2 mb-4">
        {title}
      </h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {articles.map((article) => {
          const date = new Date(article.published_at).toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
          })

          const content = (
            <div className="border border-neutral-200 rounded-lg p-4 hover:border-neutral-400 transition-colors">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-[11px] font-semibold text-neutral-900 uppercase tracking-wide">
                  {categoryLabel(article.feed_name)}
                </span>
                <span className="text-[11px] text-neutral-400">{date}</span>
              </div>
              <h3 className="font-serif text-sm leading-snug text-neutral-900">
                {article.title}
              </h3>
            </div>
          )

          return article.slug ? (
            <Link key={article.id} href={`/news/${article.slug}`}>
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
