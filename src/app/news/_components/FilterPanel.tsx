'use client'

import { useRouter, useSearchParams } from 'next/navigation'
import { SlidersHorizontal } from 'lucide-react'

interface FilterPanelProps {
  allSubcategories: { keyword: string; count: number }[]
  allKeywords: { keyword: string; count: number }[]
  activeKeywords: string[]
  isOpen: boolean
  onClose: () => void
  onOpen: () => void
}

export default function FilterPanel({
  allSubcategories,
  allKeywords,
  activeKeywords,
  isOpen,
  onClose,
  onOpen,
}: FilterPanelProps) {
  const router = useRouter()
  const searchParams = useSearchParams()

  const activeSet = new Set(activeKeywords.map((k) => k.toLowerCase()))

  const toggleKeyword = (kw: string) => {
    const next = new Set(activeKeywords)
    if (next.has(kw)) {
      next.delete(kw)
    } else {
      next.add(kw)
    }
    const params = new URLSearchParams(searchParams.toString())
    if (next.size > 0) {
      params.set('keywords', Array.from(next).join(','))
    } else {
      params.delete('keywords')
    }
    params.delete('keyword')
    router.push(`/news${params.size > 0 ? `?${params.toString()}` : ''}`)
  }

  const clearAll = () => {
    const params = new URLSearchParams(searchParams.toString())
    params.delete('keywords')
    params.delete('keyword')
    router.push(`/news${params.size > 0 ? `?${params.toString()}` : ''}`)
  }

  const renderPill = ({ keyword, count }: { keyword: string; count: number }) => {
    const isActive = activeSet.has(keyword.toLowerCase())
    return (
      <button
        key={keyword}
        onClick={() => toggleKeyword(keyword)}
        className={`inline-flex items-center gap-1.5 px-3 py-2.5 text-sm transition-colors ${
          isActive
            ? 'bg-neutral-900 text-white rounded-full'
            : 'text-neutral-700 hover:text-neutral-900'
        }`}
      >
        {keyword}
        <span className="text-[10px] tabular-nums text-neutral-400">{count}</span>
        {isActive && <span className="ml-0.5 text-neutral-400">&times;</span>}
      </button>
    )
  }

  return (
    <>
      {/* Mobile backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/20 z-10 lg:hidden"
          onClick={onClose}
          aria-hidden
        />
      )}

      {/* Toggle tab — sits on the left edge of the panel, visible when panel is closed or open */}
      <button
        onClick={isOpen ? onClose : onOpen}
        className={`fixed right-0 top-1/2 -translate-y-1/2 z-20 flex items-center gap-1.5 px-2 py-3 bg-white rounded-l-lg shadow-md transition-all duration-200 ease-out ${
          isOpen ? 'right-72' : 'right-0'
        }`}
        aria-label="Toggle filter panel"
        aria-expanded={isOpen}
      >
        <SlidersHorizontal className="w-3.5 h-3.5 text-neutral-400" />
        {activeKeywords.length > 0 && (
          <span className="px-1.5 py-0.5 text-[10px] font-semibold bg-neutral-900 text-white rounded-full leading-none">
            {activeKeywords.length}
          </span>
        )}
      </button>

      {/* Panel */}
      <aside
        className={`fixed right-0 top-14 md:top-20 h-[calc(100vh-3.5rem)] md:h-[calc(100vh-5rem)] w-72 bg-white z-20 flex flex-col transition-transform duration-200 ease-out ${
          isOpen ? 'translate-x-0' : 'translate-x-full'
        }`}
        aria-label="Filter panel"
        aria-hidden={!isOpen}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 shrink-0">
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-bold text-neutral-900 uppercase tracking-widest">
              Filter
            </span>
          </div>
          {activeKeywords.length > 0 && (
            <button
              onClick={clearAll}
              className="text-[11px] text-neutral-400 hover:text-neutral-900 underline underline-offset-2 transition-colors"
            >
              Clear all
            </button>
          )}
        </div>

        {/* Scrollable body */}
        <div className="flex-1 overflow-y-auto">
          {/* Region / Subcategories */}
          {allSubcategories.length > 0 && (
            <div className="px-5 pt-4 pb-3">
              <span className="text-[10px] font-bold text-neutral-400 uppercase tracking-widest">
                Region
              </span>
              <div className="flex flex-wrap gap-0 mt-2">
                {allSubcategories.map((item) => renderPill(item))}
              </div>
            </div>
          )}

          {allSubcategories.length > 0 && allKeywords.length > 0 && (
            <div className="mx-5 border-t border-neutral-100" />
          )}

          {/* Topics / Keywords */}
          {allKeywords.length > 0 && (
            <div className="px-5 pt-3 pb-5">
              <span className="text-[10px] font-bold text-neutral-400 uppercase tracking-widest">
                Topics
              </span>
              <div className="flex flex-wrap gap-0 mt-2">
                {allKeywords.map((item) => renderPill(item))}
              </div>
            </div>
          )}
        </div>
      </aside>
    </>
  )
}
