'use client'

import React, { useState } from 'react'

interface ThreadSectionProps {
  title: string
  articleCount: number
  defaultExpanded?: boolean
  children: React.ReactNode
}

export default function ThreadSection({
  title,
  articleCount,
  defaultExpanded = false,
  children,
}: ThreadSectionProps) {
  const [expanded, setExpanded] = useState(defaultExpanded)
  const allChildren = React.Children.toArray(children)
  const canCollapse = articleCount > 2
  const visibleChildren = canCollapse && !expanded ? allChildren.slice(0, 2) : allChildren
  const hiddenCount = allChildren.length - 2

  return (
    <section>
      <h2 className="font-serif text-lg text-neutral-900 border-b-2 border-neutral-900 pb-2 mb-4">
        {title}
        <span className="text-neutral-400 text-sm font-sans ml-2">({articleCount})</span>
      </h2>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-x-6">
        {visibleChildren}
      </div>
      {canCollapse && (
        <button
          onClick={() => setExpanded(!expanded)}
          className="mt-3 text-sm text-neutral-500 hover:text-neutral-700 transition-colors"
        >
          {expanded ? 'Show less' : `Show ${hiddenCount} more article${hiddenCount !== 1 ? 's' : ''}`}
        </button>
      )}
    </section>
  )
}
