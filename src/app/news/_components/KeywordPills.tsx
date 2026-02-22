import Link from 'next/link'

interface KeywordPillsProps {
  keywords: string[]
  activeKeywords?: string[]
  linkable?: boolean
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
}: KeywordPillsProps) {
  if (!keywords.length) return null

  const activeSet = new Set(activeKeywords.map((k) => k.toLowerCase()))
  const capitalize = (s: string) =>
    s.replace(/\b\w/g, (c) => c.toUpperCase())

  const sorted = [...keywords].sort((a, b) => a.localeCompare(b, 'en', { sensitivity: 'base' }))

  return (
    <div className="text-xs text-neutral-400 truncate">
      {sorted.map((kw, i) => {
        const label = capitalize(kw)
        const isActive = activeSet.has(kw.toLowerCase())

        if (linkable) {
          return (
            <span key={kw}>
              {i > 0 && <span className="mx-1">&middot;</span>}
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
            {i > 0 && <span className="mx-1">&middot;</span>}
            <span className={isActive ? 'text-neutral-900 font-medium' : ''}>
              {label}
            </span>
          </span>
        )
      })}
    </div>
  )
}
