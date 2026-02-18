import Link from 'next/link'
import type { NewsItem } from '@/lib/news-service'

interface TimelineSectionProps {
  threadTitle: string
  articles: NewsItem[]
  currentId: string
}

export default function TimelineSection({
  threadTitle,
  articles,
  currentId,
}: TimelineSectionProps) {
  if (articles.length <= 1) return null

  return (
    <section>
      <h2 className="font-serif text-lg text-neutral-900 border-b-2 border-neutral-900 pb-2 mb-4">
        Story Timeline: {threadTitle}
      </h2>
      <div className="relative pl-6 border-l-2 border-neutral-200 space-y-4">
        {articles.map((article) => {
          const isCurrent = article.id === currentId
          const date = new Date(article.published_at).toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
            year: 'numeric',
          })

          return (
            <div key={article.id} className="relative">
              {/* Timeline dot */}
              <div
                className={`absolute -left-[1.9rem] top-1.5 w-3 h-3 rounded-full border-2 ${
                  isCurrent
                    ? 'bg-neutral-900 border-neutral-900'
                    : 'bg-white border-neutral-400'
                }`}
              />

              <div className={isCurrent ? 'opacity-100' : 'opacity-70'}>
                <span className="text-[11px] text-neutral-400">{date}</span>
                {article.slug && !isCurrent ? (
                  <Link
                    href={`/news/${article.slug}`}
                    className="block font-serif text-sm leading-snug text-neutral-900 hover:text-neutral-600 transition-colors mt-0.5"
                  >
                    {article.title}
                  </Link>
                ) : (
                  <p
                    className={`font-serif text-sm leading-snug mt-0.5 ${
                      isCurrent ? 'text-neutral-900 font-semibold' : 'text-neutral-900'
                    }`}
                  >
                    {article.title}
                    {isCurrent && (
                      <span className="text-[10px] font-normal text-neutral-400 ml-2">
                        (current)
                      </span>
                    )}
                  </p>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </section>
  )
}
