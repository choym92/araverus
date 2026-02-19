'use client'

import { useState } from 'react'
import Link from 'next/link'
import type { NewsItem } from '@/lib/news-service'

const COLLAPSED_COUNT = 5

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
  const [expanded, setExpanded] = useState(false)

  if (articles.length <= 1) return null

  // Show last N articles (most recent) when collapsed, all when expanded
  const showAll = expanded || articles.length <= COLLAPSED_COUNT
  const visible = showAll ? articles : articles.slice(-COLLAPSED_COUNT)
  const hiddenCount = articles.length - COLLAPSED_COUNT

  return (
    <section>
      <h2 className="font-serif text-lg text-neutral-900 border-b-2 border-neutral-900 pb-2 mb-4">
        Story Timeline: {threadTitle}
      </h2>
      <div className="relative pl-6 border-l-2 border-neutral-200">
        {/* Expand button at top when collapsed */}
        {!showAll && (
          <div className="relative mb-3">
            <div className="absolute -left-[1.9rem] top-1 w-3 h-3 rounded-full border-2 border-dashed border-neutral-300 bg-white" />
            <button
              onClick={() => setExpanded(true)}
              className="text-xs text-neutral-500 hover:text-neutral-800 transition-colors"
            >
              Show {hiddenCount} older article{hiddenCount > 1 ? 's' : ''}...
            </button>
          </div>
        )}

        <div className="space-y-4">
          {visible.map((article) => {
            const isCurrent = article.id === currentId
            const date = new Date(article.published_at).toLocaleDateString('en-US', {
              month: 'short',
              day: 'numeric',
              year: 'numeric',
            })

            return (
              <div key={article.id} className="relative">
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

      </div>

      {/* Collapse button outside timeline line */}
      {expanded && articles.length > COLLAPSED_COUNT && (
        <div className="sticky bottom-0 mt-3">
          <button
            onClick={() => setExpanded(false)}
            className="w-full py-2 text-xs font-medium text-neutral-600 bg-white/90 backdrop-blur-sm border-t border-neutral-200 shadow-[0_-4px_6px_-1px_rgba(0,0,0,0.05)] hover:text-neutral-900 transition-colors flex items-center justify-center gap-1.5"
          >
            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 15.75l7.5-7.5 7.5 7.5" />
            </svg>
            Show less
          </button>
        </div>
      )}
    </section>
  )
}
