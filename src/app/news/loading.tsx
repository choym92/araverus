import NewsShell from './_components/NewsShell'

/** Skeleton placeholder block */
function Bone({ className, style }: { className?: string; style?: React.CSSProperties }) {
  return <div className={`animate-pulse rounded bg-neutral-200 ${className ?? ''}`} style={style} />
}

/** Skeleton for a text-only article card (left/right columns) */
function CardSkeleton() {
  return (
    <div className="py-4 border-b border-neutral-100">
      <Bone className="h-4 w-3/4 mb-2" />
      <Bone className="h-3 w-full mb-1" />
      <Bone className="h-3 w-5/6 mb-3" />
      <Bone className="h-3 w-24" />
    </div>
  )
}

export default function NewsLoading() {
  return (
    <NewsShell>
      {/* Nav bar skeleton — tabs + category pills */}
      <nav className="border-b border-neutral-200 bg-white sticky top-20 z-10">
        <div className="px-6 md:px-12 lg:px-16">
          {/* Tabs */}
          <div className="flex items-center gap-6 border-b border-neutral-100 py-2.5">
            <Bone className="h-4 w-12" />
            <Bone className="h-4 w-14" />
            <Bone className="h-4 w-14" />
          </div>
          {/* Category pills */}
          <div className="flex items-center gap-1 py-2">
            {[10, 16, 10, 14, 12, 14].map((w, i) => (
              <Bone key={i} className={`h-7 rounded-full`} style={{ width: `${w * 4}px` }} />
            ))}
          </div>
        </div>
      </nav>

      <div className="px-6 md:px-12 lg:px-16 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-0 border-b border-neutral-200 pb-8 mb-8">
          {/* Briefing player skeleton — center top */}
          <div className="order-first lg:order-none lg:col-start-4 lg:col-span-6 lg:row-start-1 lg:px-6 mb-6">
            <div className="rounded-lg border border-neutral-200 p-5">
              <Bone className="h-5 w-48 mb-3" />
              <Bone className="h-3 w-32 mb-4" />
              <Bone className="h-10 w-full rounded-lg mb-3" />
              <div className="flex items-center gap-3">
                <Bone className="h-8 w-8 rounded-full" />
                <Bone className="h-2 w-full rounded-full" />
                <Bone className="h-3 w-10" />
              </div>
            </div>
          </div>

          {/* Left column — 5 text story skeletons */}
          <div className="order-2 lg:order-none lg:col-span-3 lg:row-start-1 lg:row-span-2 lg:border-r lg:border-neutral-200 lg:pr-6">
            {Array.from({ length: 5 }).map((_, i) => (
              <CardSkeleton key={i} />
            ))}
          </div>

          {/* Center — featured card skeleton */}
          <div className="order-1 lg:order-none lg:col-start-4 lg:col-span-6 lg:row-start-2 lg:px-6">
            <div className="py-4">
              <Bone className="h-48 w-full rounded-lg mb-4" />
              <Bone className="h-5 w-5/6 mb-2" />
              <Bone className="h-4 w-full mb-1" />
              <Bone className="h-4 w-4/5 mb-3" />
              <Bone className="h-3 w-28" />
            </div>
          </div>

          {/* Right column — 5 text story skeletons */}
          <div className="order-3 lg:order-none lg:col-span-3 lg:row-start-1 lg:row-span-2 lg:border-l lg:border-neutral-200 lg:pl-6">
            {Array.from({ length: 5 }).map((_, i) => (
              <CardSkeleton key={i} />
            ))}
          </div>
        </div>
      </div>
    </NewsShell>
  )
}
