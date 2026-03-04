import Link from 'next/link'

interface KeywordPillsProps {
  keywords: string[]
  activeKeywords?: string[]
  linkable?: boolean
  size?: 'xs' | 'sm'
  /** 'dot' = middot separator (default), 'hashtag' = # prefix with spacing */
  variant?: 'dot' | 'hashtag'
}

/** Build a keywords param string toggling `kw` in/out of the current set */
function toggleKeywordsParam(kw: string, activeKeywords: string[]): string {
  const set = new Set(activeKeywords.map((k) => k.toLowerCase()))
  const kwLower = kw.toLowerCase()
  if (set.has(kwLower)) {
    set.delete(kwLower)
  } else {
    set.add(kwLower)
  }
  // Build using original-cased values where possible
  const remaining = activeKeywords.filter((k) => set.has(k.toLowerCase()))
  if (!set.has(kwLower) || remaining.some((k) => k.toLowerCase() === kwLower)) {
    // kw was removed or already in remaining
  } else {
    remaining.push(kw)
  }
  if (remaining.length === 0) return '/news'
  return `/news?keywords=${encodeURIComponent(remaining.join(','))}`
}

export default function KeywordPills({
  keywords,
  activeKeywords = [],
  linkable = false,
  size = 'xs',
  variant = 'dot',
}: KeywordPillsProps) {
  if (!keywords.length) return null

  const activeSet = new Set(activeKeywords.map((k) => k.toLowerCase()))
  const capitalize = (s: string) =>
    s.replace(/\b\w/g, (c) => c.toUpperCase())

  const sorted = [...keywords].sort((a, b) => a.localeCompare(b, 'en', { sensitivity: 'base' }))

  if (variant === 'hashtag') {
    return (
      <div className="flex flex-wrap items-center gap-2">
        {sorted.map((kw) => {
          const label = capitalize(kw)
          const isActive = activeSet.has(kw.toLowerCase())
          const cls = isActive
            ? 'border-neutral-900 text-neutral-900 bg-neutral-50'
            : 'border-neutral-300 text-neutral-700 bg-transparent hover:border-neutral-500 hover:text-neutral-900'

          if (linkable) {
            return (
              <Link
                key={kw}
                href={toggleKeywordsParam(kw, activeKeywords)}
                className={`inline-flex items-center px-3 py-1 text-[11px] font-medium uppercase tracking-wide rounded-sm border transition-all duration-200 ${cls}`}
              >
                {label}
                {isActive && <span className="ml-1.5 text-neutral-400">&times;</span>}
              </Link>
            )
          }

          return (
            <span
              key={kw}
              className={`inline-flex items-center px-3 py-1 text-[11px] font-medium uppercase tracking-wide rounded-sm border transition-all duration-200 ${cls}`}
            >
              {label}
            </span>
          )
        })}
      </div>
    )
  }

  return (
    <div className={`${size === 'sm' ? 'text-sm' : 'text-xs'} text-neutral-400 truncate`}>
      {sorted.map((kw, i) => {
        const label = capitalize(kw)
        const isActive = activeSet.has(kw.toLowerCase())
        const sep = i > 0 && <span key={`sep-${kw}`} className="mx-1">&middot;</span>

        if (linkable) {
          return (
            <span key={kw}>
              {sep}
              <Link
                href={toggleKeywordsParam(kw, activeKeywords)}
                className={`hover:text-neutral-600 transition-colors ${isActive ? 'text-neutral-900 font-medium' : ''}`}
              >
                {label}
                {isActive && ' ×'}
              </Link>
            </span>
          )
        }

        return (
          <span key={kw}>
            {sep}
            <span className={isActive ? 'text-neutral-900 font-medium' : ''}>
              {label}
            </span>
          </span>
        )
      })}
    </div>
  )
}
