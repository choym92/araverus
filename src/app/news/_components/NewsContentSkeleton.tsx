/** Skeleton for Suspense fallback while client component hydrates */
export default function NewsContentSkeleton() {
  const Bone = ({ className, style }: { className?: string; style?: React.CSSProperties }) => (
    <div className={`animate-pulse rounded bg-neutral-200 ${className ?? ''}`} style={style} />
  )
  return (
    <>
      <nav className="border-b border-neutral-200 bg-white sticky top-20 z-10">
        <div className="px-6 md:px-16 lg:px-24">
          <div className="flex items-center gap-6 border-b border-neutral-100 py-2.5">
            <Bone className="h-4 w-12" />
            <Bone className="h-4 w-14" />
            <Bone className="h-4 w-14" />
          </div>
          <div className="flex items-center gap-1 py-2">
            {[10, 16, 10, 14, 12, 14].map((w, i) => (
              <Bone key={i} className="h-7 rounded-full" style={{ width: `${w * 4}px` }} />
            ))}
          </div>
        </div>
      </nav>
      <div className="px-6 md:px-16 lg:px-24 py-6">
        <Bone className="h-64 w-full rounded-lg" />
      </div>
    </>
  )
}
