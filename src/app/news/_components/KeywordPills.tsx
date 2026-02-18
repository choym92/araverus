import Link from 'next/link'

interface KeywordPillsProps {
  keywords: string[]
  activeKeyword?: string | null
  linkable?: boolean
}

export default function KeywordPills({
  keywords,
  activeKeyword,
  linkable = false,
}: KeywordPillsProps) {
  if (!keywords.length) return null

  return (
    <div className="flex flex-wrap gap-1.5">
      {keywords.map((kw) => {
        const isActive = activeKeyword === kw
        const baseClasses =
          'inline-block px-2.5 py-0.5 text-xs rounded-full transition-colors'
        const activeClasses = isActive
          ? 'bg-neutral-900 text-white'
          : 'bg-neutral-100 text-neutral-600 hover:bg-neutral-200'

        if (linkable) {
          return (
            <Link
              key={kw}
              href={isActive ? '/news' : `/news?keyword=${encodeURIComponent(kw)}`}
              className={`${baseClasses} ${activeClasses}`}
            >
              {kw}
              {isActive && ' ×'}
            </Link>
          )
        }

        return (
          <span key={kw} className={`${baseClasses} ${activeClasses}`}>
            {kw}
          </span>
        )
      })}
    </div>
  )
}
