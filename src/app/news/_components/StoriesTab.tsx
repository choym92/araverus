'use client'

import { useState } from 'react'
import Link from 'next/link'
import type { ParentThreadGroup } from '@/lib/news-service'

interface StoriesTabProps {
  groups: ParentThreadGroup[]
}

/** Heat level to dot indicator */
function heatBadge(heat: number): string {
  if (heat >= 8) return '●●●'
  if (heat >= 4) return '●●'
  if (heat >= 1) return '●'
  return ''
}

/** Format date range like "Feb 23 – Mar 1" */
function dateRange(firstSeen: string, lastSeen: string): string {
  const fmt = (d: string) =>
    new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  const first = fmt(firstSeen)
  const last = fmt(lastSeen)
  return first === last ? first : `${first} – ${last}`
}

/** Importance pill */
function ImportancePill({ importance }: { importance: string | null }) {
  if (!importance || importance === 'optional') return null
  return (
    <span
      className={`inline-block px-1.5 py-0.5 text-[10px] font-medium rounded ${
        importance === 'must_read'
          ? 'bg-neutral-900 text-white'
          : 'bg-neutral-200 text-neutral-600'
      }`}
    >
      {importance === 'must_read' ? 'Must Read' : 'Worth Reading'}
    </span>
  )
}

export default function StoriesTab({ groups }: StoriesTabProps) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set())

  const toggle = (threadId: string) => {
    setExpanded(prev => {
      const next = new Set(prev)
      if (next.has(threadId)) next.delete(threadId)
      else next.add(threadId)
      return next
    })
  }

  if (groups.length === 0) {
    return (
      <div className="text-center py-16">
        <p className="text-neutral-500 text-lg">No active threads.</p>
        <p className="text-neutral-400 text-sm mt-2">
          Threads will appear here as the pipeline groups related articles.
        </p>
      </div>
    )
  }

  // Flatten: for now all threads are orphans (parent=null), show as flat list
  // When parent threads exist, they'll render as grouped sections
  const hasParents = groups.some(g => g.parent !== null)

  return (
    <div className="py-4 space-y-6">
      {groups.map((group, gi) => (
        <div key={group.parent?.id ?? `orphan-${gi}`}>
          {/* Parent thread header (only if parents exist) */}
          {hasParents && group.parent && (
            <h2 className="text-lg font-semibold text-neutral-900 mb-3 px-1">
              {group.parent.title}
            </h2>
          )}

          {/* Sub-threads */}
          <div className="border border-neutral-200 rounded-lg divide-y divide-neutral-100 overflow-hidden">
            {group.subThreads.map(thread => {
              const isOpen = expanded.has(thread.id)
              return (
                <div key={thread.id}>
                  {/* Sub-thread row */}
                  <button
                    onClick={() => toggle(thread.id)}
                    className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-neutral-50 transition-colors"
                  >
                    {/* Expand chevron */}
                    <svg
                      className={`w-4 h-4 text-neutral-400 shrink-0 transition-transform ${isOpen ? 'rotate-90' : ''}`}
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                      strokeWidth={2}
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                    </svg>

                    {/* Thread info */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-neutral-900 truncate">
                          {thread.title}
                        </span>
                        {heatBadge(thread.heat) && (
                          <span className="text-[10px] text-neutral-400 shrink-0 tracking-tight">{heatBadge(thread.heat)}</span>
                        )}
                      </div>
                      <div className="text-xs text-neutral-400 mt-0.5">
                        {thread.member_count} article{thread.member_count !== 1 ? 's' : ''}
                        {' · '}
                        {dateRange(thread.first_seen, thread.last_seen)}
                      </div>
                    </div>
                  </button>

                  {/* Expanded article list */}
                  {isOpen && thread.recentArticles.length > 0 && (
                    <div className="bg-neutral-50 border-t border-neutral-100 px-4 py-2">
                      <ul className="space-y-2">
                        {thread.recentArticles.map(article => (
                          <li key={article.id} className="flex items-start gap-2">
                            <span className="text-neutral-300 mt-1 text-xs">•</span>
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2">
                                {article.slug ? (
                                  <Link
                                    href={`/news/${article.slug}`}
                                    className="text-sm text-neutral-700 hover:text-neutral-900 hover:underline truncate"
                                  >
                                    {article.title}
                                  </Link>
                                ) : (
                                  <span className="text-sm text-neutral-700 truncate">
                                    {article.title}
                                  </span>
                                )}
                                <ImportancePill importance={article.importance} />
                              </div>
                              <span className="text-[11px] text-neutral-400">
                                {new Date(article.published_at).toLocaleDateString('en-US', {
                                  month: 'short',
                                  day: 'numeric',
                                })}
                              </span>
                            </div>
                          </li>
                        ))}
                      </ul>
                      {thread.member_count > thread.recentArticles.length && (
                        <p className="text-xs text-neutral-400 mt-2 pl-4">
                          +{thread.member_count - thread.recentArticles.length} more article{thread.member_count - thread.recentArticles.length !== 1 ? 's' : ''}
                        </p>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      ))}
    </div>
  )
}
