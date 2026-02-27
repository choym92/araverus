'use client'

import { useState } from 'react'
import type { CrawlSource } from '@/lib/news-service'

const COLLAPSED_COUNT = 3

function SourceRow({ href, icon, label, domain }: {
  href: string
  icon: React.ReactNode
  label: string
  domain: string
}) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      aria-label={`Read on ${domain}`}
      className="group flex items-center gap-2.5 py-2 -mx-2 px-2 rounded-md hover:bg-neutral-50 transition-colors"
    >
      {icon}
      <span className="text-sm text-neutral-600 group-hover:text-neutral-900 truncate flex-1 min-w-0 transition-colors">
        {label}
      </span>
      <span className="inline-flex items-center gap-1 text-[11px] text-neutral-300 group-hover:text-neutral-500 shrink-0 transition-colors">
        {domain}
        <svg className="w-3 h-3 text-neutral-300 group-hover:text-neutral-500 transition-colors" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 19.5l15-15m0 0H8.25m11.25 0v11.25" />
        </svg>
      </span>
    </a>
  )
}

function Favicon({ domain }: { domain: string }) {
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={`https://www.google.com/s2/favicons?domain=${domain}&sz=16`}
      alt=""
      width={16}
      height={16}
      className="w-4 h-4 rounded-sm shrink-0 opacity-60 group-hover:opacity-100 transition-opacity"
    />
  )
}

export default function SourceList({ sources, wsjUrl, wsjTitle }: { sources: CrawlSource[]; wsjUrl: string; wsjTitle: string }) {
  const [expanded, setExpanded] = useState(false)

  const visible = expanded ? sources : sources.slice(0, COLLAPSED_COUNT)
  const hasMore = sources.length > COLLAPSED_COUNT

  return (
    <div className="mb-12">
      <div className="flex items-center gap-2 mb-2">
        <span className="text-[11px] font-medium text-neutral-400 uppercase tracking-wider">
          Read more on
        </span>
        <span className="flex-1 h-px bg-neutral-100" />
      </div>
      <div className="space-y-0">
        <SourceRow
          href={wsjUrl}
          icon={<Favicon domain="wsj.com" />}
          label={wsjTitle}
          domain="wsj.com"
        />
        {visible.map((src, i) => (
          <SourceRow
            key={i}
            href={src.resolved_url}
            icon={<Favicon domain={src.domain} />}
            label={src.title || src.source}
            domain={src.domain}
          />
        ))}
      </div>
      {hasMore && (
        <button
          onClick={() => setExpanded(!expanded)}
          aria-expanded={expanded}
          className="mt-1 text-[11px] text-neutral-400 hover:text-neutral-600 transition-colors"
        >
          {expanded ? 'Show less' : `+${sources.length - COLLAPSED_COUNT} more`}
        </button>
      )}
    </div>
  )
}
