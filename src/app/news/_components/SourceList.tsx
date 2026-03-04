'use client'

import { useState } from 'react'
import type { CrawlSource } from '@/lib/news-service'

const COLLAPSED_COUNT = 4

function isSafeUrl(url: string): boolean {
  try {
    const { protocol } = new URL(url)
    return protocol === 'https:' || protocol === 'http:'
  } catch {
    return false
  }
}

function SourceRow({ href, domain, label }: {
  href: string
  domain: string
  label: string
}) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      aria-label={`Read on ${domain}`}
      className="group flex items-center gap-3 py-2.5 -mx-2 px-2 rounded-md hover:bg-neutral-50 transition-colors"
    >
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={`https://www.google.com/s2/favicons?domain=${domain}&sz=32`}
        alt=""
        width={20}
        height={20}
        className="w-5 h-5 rounded shrink-0 opacity-70 group-hover:opacity-100 transition-opacity"
      />
      <span className="text-sm text-neutral-600 group-hover:text-neutral-900 truncate flex-1 min-w-0 transition-colors">
        {label}
      </span>
      <span className="inline-flex items-center gap-1.5 text-[11px] text-neutral-300 group-hover:text-neutral-500 shrink-0 transition-colors">
        {domain}
        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 19.5l15-15m0 0H8.25m11.25 0v11.25" />
        </svg>
      </span>
    </a>
  )
}

export default function SourceList({ sources, wsjUrl, wsjTitle, originalTitle }: { sources: CrawlSource[]; wsjUrl: string; wsjTitle: string; originalTitle?: string }) {
  const [expanded, setExpanded] = useState(false)

  const visible = expanded ? sources : sources.slice(0, COLLAPSED_COUNT)
  const hasMore = sources.length > COLLAPSED_COUNT

  if (sources.length === 0 && !wsjUrl) return null

  return (
    <div className="mb-12">
      <h2 className="font-serif text-lg text-neutral-900 border-b-2 border-neutral-900 pb-2 mb-4">
        Read More On
      </h2>
      <div className="divide-y divide-neutral-100">
        <SourceRow
          href={wsjUrl}
          domain="wsj.com"
          label={wsjTitle}
        />
        {visible.filter((src) => isSafeUrl(src.resolved_url)).map((src) => (
          <SourceRow
            key={src.resolved_url}
            href={src.resolved_url}
            domain={src.domain}
            label={src.title || src.source}
          />
        ))}
      </div>
      {originalTitle && (
        <p className="text-xs text-neutral-400 mt-3 italic">
          Originally reported as: &ldquo;{originalTitle}&rdquo;
        </p>
      )}
      {hasMore && (
        <button
          onClick={() => setExpanded(!expanded)}
          aria-expanded={expanded}
          className="mt-2 text-[11px] text-neutral-400 hover:text-neutral-600 transition-colors"
        >
          {expanded ? 'Show less' : `+${sources.length - COLLAPSED_COUNT} more`}
        </button>
      )}
    </div>
  )
}
