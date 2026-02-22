'use client'

import { useState, useEffect, useRef } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { SlidersHorizontal } from 'lucide-react'
import { AnimatePresence, motion } from 'framer-motion'

interface FilterButtonProps {
  allSubcategories: { keyword: string; count: number }[]
  allKeywords: { keyword: string; count: number }[]
  activeKeywords: string[]
}

export default function FilterButton({ allSubcategories, allKeywords, activeKeywords }: FilterButtonProps) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const router = useRouter()
  const searchParams = useSearchParams()

  // Close on outside click
  useEffect(() => {
    if (!open) return
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  // Close on ESC
  useEffect(() => {
    if (!open) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [open])

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
    setOpen(false)
  }

  const renderPills = (items: { keyword: string; count: number }[]) =>
    items.map(({ keyword, count }) => {
      const isActive = activeSet.has(keyword.toLowerCase())
      return (
        <button
          key={keyword}
          onClick={() => toggleKeyword(keyword)}
          className={`inline-flex items-center gap-1 px-2.5 py-1 text-xs rounded-full transition-colors ${
            isActive
              ? 'bg-neutral-900 text-white'
              : 'bg-neutral-100 text-neutral-600 hover:bg-neutral-200'
          }`}
        >
          {keyword}
          <span className={`text-[10px] ${isActive ? 'text-neutral-400' : 'text-neutral-400'}`}>
            {count}
          </span>
          {isActive && <span className="ml-0.5">×</span>}
        </button>
      )
    })

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-full bg-neutral-100 text-neutral-600 hover:bg-neutral-200 transition-colors"
        aria-label="Toggle topic filter"
        aria-expanded={open}
      >
        <SlidersHorizontal className="w-3.5 h-3.5" />
        Filter
        {activeKeywords.length > 0 && (
          <span className="ml-0.5 px-1.5 py-0.5 text-[10px] font-semibold bg-neutral-900 text-white rounded-full leading-none">
            {activeKeywords.length}
          </span>
        )}
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.15 }}
            className="absolute right-0 top-full mt-2 w-96 bg-white border border-neutral-200 rounded-xl shadow-lg z-50 overflow-hidden"
          >
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-neutral-100">
              <span className="text-xs font-semibold text-neutral-900 uppercase tracking-wide">
                Today&apos;s Topics
              </span>
              {activeKeywords.length > 0 && (
                <button
                  onClick={clearAll}
                  className="text-[11px] text-neutral-400 hover:text-neutral-600 transition-colors"
                >
                  Clear all
                </button>
              )}
            </div>

            <div className="max-h-80 overflow-y-auto">
              {/* Subcategories */}
              {allSubcategories.length > 0 && (
                <div className="px-4 py-3">
                  <span className="text-[11px] font-medium text-neutral-400 uppercase tracking-wide">
                    Subcategory
                  </span>
                  <div className="flex flex-wrap gap-1.5 mt-2">
                    {renderPills(allSubcategories)}
                  </div>
                </div>
              )}

              {/* Divider */}
              {allSubcategories.length > 0 && allKeywords.length > 0 && (
                <div className="border-t border-neutral-100" />
              )}

              {/* Keywords */}
              {allKeywords.length > 0 && (
                <div className="px-4 py-3">
                  <span className="text-[11px] font-medium text-neutral-400 uppercase tracking-wide">
                    Keywords
                  </span>
                  <div className="flex flex-wrap gap-1.5 mt-2">
                    {renderPills(allKeywords)}
                  </div>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
