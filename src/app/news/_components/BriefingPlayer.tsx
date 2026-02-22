'use client'

import React, { useRef, useState, useEffect } from 'react'
import { Play, Pause, RotateCcw, RotateCw, ChevronDown, ChevronUp, Captions, Layers, Volume2, VolumeX } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { useBriefing, formatTime, SPEEDS } from './BriefingContext'
import type { BriefingSource, BriefingLangData, BriefingData } from './BriefingContext'

// Re-export types for backward compat
export type { BriefingSource, BriefingLangData }
export type { BriefingChapter, BriefingSentence } from './BriefingContext'

interface BriefingPlayerProps {
  date: string
  duration: number
  sourceCount?: number
  sources?: BriefingSource[]
  en?: BriefingLangData
  ko?: BriefingLangData
  defaultLang?: 'en' | 'ko'
}

function categoryLabel(feedName: string): string {
  const map: Record<string, string> = {
    BUSINESS_MARKETS: 'Markets',
    TECH: 'Tech',
    ECONOMY: 'Economy',
    WORLD: 'World',
    POLITICS: 'Politics',
  }
  return map[feedName] || feedName
}

/** Theme config — swap this object to restyle the entire player */
const T = {
  wrapper: 'bg-neutral-950 text-white shadow-xl',
  text: 'text-white',
  muted: 'text-white/50',
  dim: 'text-white/40',
  dimmer: 'text-white/25',
  dimmest: 'text-white/20',
  surface: 'bg-white/5',
  surfaceHover: 'hover:bg-white/10',
  surfaceActive: 'bg-white/20',
  border: 'border-white/10',
  borderSubtle: 'border-white/5',
  accent: 'bg-gradient-to-br from-gray-300 via-gray-500 to-gray-300 text-white',
  progressBg: 'bg-white/15',
  progressFill: 'bg-gradient-to-r from-gray-300 via-gray-500 to-gray-300',
  progressDivider: 'bg-white/20',
  seekThumb: 'bg-white',
  playBtn: 'bg-white text-neutral-950',
  speedBtn: 'bg-white/10 hover:bg-white/20 text-white/70 hover:text-white',
  toggleBg: 'bg-white/5',
  toggleActive: 'bg-white/15 text-white',
  toggleInactive: 'text-white/40 hover:text-white/70',
  chapterActive: 'bg-white/20 text-white font-medium ring-2 ring-white/40 shadow-[0_0_8px_rgba(255,255,255,0.15)]',
  chapterInactive: 'bg-white/5 text-white/40 hover:bg-white/10 hover:text-white/70',
  chapterTime: 'text-white/25',
  chapterTimeActive: 'text-white/50',
  transcriptActive: 'text-white bg-white/10 rounded px-0.5 -mx-0.5',
  transcriptPast: 'text-white/50',
  transcriptFuture: 'text-white/25',
  headingActive: 'text-gray-300',
  headingInactive: 'text-white/30',
  scrollbar: 'scrollbar-thumb-white/10',
  volumeTrack: 'bg-white/15',
  volumeThumb: '[&::-webkit-slider-thumb]:bg-white',
  sourceHover: 'hover:bg-white/5',
  sourceText: 'text-white/60 group-hover:text-white/90',
} as const

export default function BriefingPlayer({
  date,
  duration,
  sourceCount = 0,
  sources = [],
  en,
  ko,
  defaultLang = 'en',
}: BriefingPlayerProps) {
  const ctx = useBriefing()

  // Hydrate context with server data on mount
  useEffect(() => {
    const briefingData: BriefingData = { date, duration, sourceCount, sources, en, ko, defaultLang }
    ctx.setData(briefingData)
  }, [date, duration, en?.audioUrl, ko?.audioUrl]) // eslint-disable-line react-hooks/exhaustive-deps

  const {
    lang, isPlaying, currentTime, audioDuration, speedIndex, volume, isMuted,
    switchLang, togglePlay, skip, handleSeek, selectSpeed, handleVolumeChange, toggleMute,
    jumpToChapter, seekTo, setFullPlayerVisible,
    chapters, transcript, sentences, hasToggle, progress,
    activeChapterIndex, activeSentenceIndex, chapterGroups,
  } = ctx

  // Local UI state (not shared with mini-player)
  const playerRef = useRef<HTMLDivElement>(null)
  const transcriptRef = useRef<HTMLDivElement>(null)
  const chapterListRef = useRef<HTMLDivElement>(null)
  const lastTapRef = useRef<{ time: number; side: 'left' | 'right' } | null>(null)
  const userScrollTimeout = useRef<NodeJS.Timeout | null>(null)
  const isAutoScrolling = useRef(false)

  const [mainSpeedOpen, setMainSpeedOpen] = useState(false)
  const [chapterDropdownOpen, setChapterDropdownOpen] = useState(false)
  const [volumePopupOpen, setVolumePopupOpen] = useState(false)
  const [mobileSpeedOpen, setMobileSpeedOpen] = useState(false)
  const [mobileVolumeOpen, setMobileVolumeOpen] = useState(false)
  const [seekHover, setSeekHover] = useState<{ ratio: number; x: number } | null>(null)
  const [isExpanded, setIsExpanded] = useState(false)
  const [showTranscript, setShowTranscript] = useState(true)
  const userScrolledRef = useRef(false)
  const lastScrolledSentence = useRef(-1)
  const [transcriptExpanded, setTranscriptExpanded] = useState(false)

  const remaining = audioDuration - currentTime
  const count = sourceCount || sources.length

  // IntersectionObserver: detect when full player scrolls out of view
  useEffect(() => {
    const el = playerRef.current
    if (!el) return
    const observer = new IntersectionObserver(
      ([entry]) => setFullPlayerVisible(entry.isIntersecting),
      { threshold: 0 }
    )
    observer.observe(el)
    return () => {
      observer.disconnect()
      setFullPlayerVisible(false)
    }
  }, [])

  // Auto-scroll chapter pills
  useEffect(() => {
    const container = chapterListRef.current
    if (!container || activeChapterIndex < 0) return
    const activeBtn = container.children[activeChapterIndex] as HTMLElement
    if (!activeBtn) return
    const left = activeBtn.offsetLeft - container.clientWidth / 2 + activeBtn.clientWidth / 2
    container.scrollTo({ left, behavior: 'smooth' })
  }, [activeChapterIndex])

  // Pause auto-scroll when user interacts with transcript (touch/wheel/mousedown)
  useEffect(() => {
    const container = transcriptRef.current
    if (!container) return
    const onUserInteract = () => {
      userScrolledRef.current = true
      if (userScrollTimeout.current) clearTimeout(userScrollTimeout.current)
      userScrollTimeout.current = setTimeout(() => { userScrolledRef.current = false }, 2000)
    }
    container.addEventListener('touchstart', onUserInteract, { passive: true })
    container.addEventListener('wheel', onUserInteract, { passive: true })
    container.addEventListener('mousedown', onUserInteract)
    return () => {
      container.removeEventListener('touchstart', onUserInteract)
      container.removeEventListener('wheel', onUserInteract)
      container.removeEventListener('mousedown', onUserInteract)
      if (userScrollTimeout.current) clearTimeout(userScrollTimeout.current)
    }
  }, [showTranscript])

  return (
    <>
    <div ref={playerRef} className={`rounded-2xl -mx-4 sm:mx-0 ${T.wrapper}`}>

      {/* Header */}
      <div className="px-5 pt-5 pb-0">
        <div className="flex items-start justify-between mb-1">
          <div className="flex items-center gap-3">
            <div className={`w-10 h-10 rounded-xl ${T.accent} flex items-center justify-center shrink-0`}>
              <span className="text-base font-bold tracking-tight">AI</span>
            </div>
            <div>
              <h3 className="font-semibold text-sm leading-tight">
                Daily Briefing
              </h3>
              <p className={`text-xs ${T.muted} mt-0.5`}>
                {date}{count > 0 && ` · ${count} sources`}{audioDuration > 0 && ` · ${Math.ceil(audioDuration / 60)} min`}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-1">
            {/* EN/KO toggle — desktop only (mobile: in controls area) */}
            {hasToggle && (
              <div className={`hidden sm:flex rounded-lg ${T.toggleBg} p-0.5 mr-1`}>
                <button
                  onClick={() => switchLang('en')}
                  className={`text-[11px] font-medium px-2 py-0.5 rounded-md transition-colors ${
                    lang === 'en' ? T.toggleActive : T.toggleInactive
                  }`}
                >
                  EN
                </button>
                <button
                  onClick={() => switchLang('ko')}
                  className={`text-[11px] font-medium px-2 py-0.5 rounded-md transition-colors ${
                    lang === 'ko' ? T.toggleActive : T.toggleInactive
                  }`}
                >
                  KO
                </button>
              </div>
            )}
            {/* Transcript toggle */}
            {(transcript || sentences.length > 0) && (
              <button
                onClick={() => setShowTranscript(!showTranscript)}
                className={`p-1.5 rounded-lg ${T.surfaceHover} transition-colors ${
                  showTranscript ? T.text : `${T.muted} ${T.surfaceHover}`
                }`}
                aria-label={showTranscript ? 'Hide transcript' : 'Show transcript'}
              >
                <Captions size={16} />
              </button>
            )}
            {/* Sources toggle */}
            {sources.length > 0 && (
              <button
                onClick={() => setIsExpanded(!isExpanded)}
                className={`flex items-center gap-1 px-1.5 py-1 rounded-lg ${T.surfaceHover} transition-colors ${isExpanded ? T.text : T.dim} text-[11px]`}
                aria-label={isExpanded ? 'Collapse sources' : 'Expand sources'}
              >
                <Layers size={13} />
                <span>{sources.length}</span>
                {isExpanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Controls */}
      <div
        className="px-5 py-2 relative"
        onTouchEnd={(e) => {
          const rect = e.currentTarget.getBoundingClientRect()
          const x = e.changedTouches[0].clientX
          const side = x < rect.left + rect.width / 2 ? 'left' : 'right'
          const now = Date.now()
          if (lastTapRef.current && lastTapRef.current.side === side && now - lastTapRef.current.time < 300) {
            skip(side === 'left' ? -15 : 15)
            lastTapRef.current = null
          } else {
            lastTapRef.current = { time: now, side }
          }
        }}
      >
        {/* Playback controls — desktop: single row with vol/speed; mobile: centered */}
        <div className="flex items-center justify-center mb-3">
          {/* Left spacer — desktop only, for volume/speed balance */}
          <div className="hidden sm:flex flex-1" />

          <div className="flex items-center gap-5">
            <button
              onClick={() => skip(-15)}
              className={`relative p-2 rounded-full ${T.surfaceHover} transition-colors ${T.muted}`}
              aria-label="Skip back 15 seconds"
            >
              <RotateCcw size={22} />
              <span className="absolute inset-0 flex items-center justify-center text-[8px] font-bold mt-0.5">
                15
              </span>
            </button>

            <button
              onClick={togglePlay}
              className={`w-12 h-12 rounded-full ${T.playBtn} flex items-center justify-center hover:scale-105 active:scale-95 transition-transform`}
              aria-label={isPlaying ? 'Pause' : 'Play'}
            >
              {isPlaying ? <Pause size={20} fill="currentColor" /> : <Play size={20} fill="currentColor" className="ml-0.5" />}
            </button>

            <button
              onClick={() => skip(15)}
              className={`relative p-2 rounded-full ${T.surfaceHover} transition-colors ${T.muted}`}
              aria-label="Skip forward 15 seconds"
            >
              <RotateCw size={22} />
              <span className="absolute inset-0 flex items-center justify-center text-[8px] font-bold mt-0.5">
                15
              </span>
            </button>
          </div>

          {/* Desktop: Volume + Speed inline right of controls */}
          <div className="hidden sm:flex flex-1 items-center justify-end gap-2">
            <div
              className="relative"
              onMouseEnter={() => setVolumePopupOpen(true)}
              onMouseLeave={() => setVolumePopupOpen(false)}
            >
              <button
                onClick={toggleMute}
                className={`h-7 w-7 flex items-center justify-center rounded-full ${T.speedBtn}`}
                aria-label={isMuted ? 'Unmute' : 'Mute'}
              >
                {isMuted || volume === 0 ? <VolumeX size={14} /> : <Volume2 size={14} />}
              </button>
              <AnimatePresence>
                {volumePopupOpen && (
                  <motion.div
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: 8 }}
                    transition={{ duration: 0.15 }}
                    className="absolute bottom-full mb-1 left-1/2 -translate-x-1/2 bg-neutral-950 border border-white/15 rounded-lg shadow-2xl px-3 py-3 z-10 flex flex-col items-center"
                  >
                    <input
                      type="range"
                      min={0}
                      max={1}
                      step={0.05}
                      value={isMuted ? 0 : volume}
                      onChange={handleVolumeChange}
                      className={`h-16 w-1 ${T.volumeTrack} rounded-full appearance-none cursor-pointer [writing-mode:vertical-lr] [direction:rtl] [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:rounded-full ${T.volumeThumb}`}
                      aria-label="Volume"
                    />
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
            <div
              className="relative"
              onMouseEnter={() => setMainSpeedOpen(true)}
              onMouseLeave={() => setMainSpeedOpen(false)}
            >
              <button
                onClick={() => selectSpeed((speedIndex + 1) % SPEEDS.length)}
                className={`h-7 flex items-center justify-center text-[11px] font-medium px-2.5 rounded-full ${T.speedBtn}`}
                aria-label={`Playback speed ${SPEEDS[speedIndex]}x`}
              >
                {SPEEDS[speedIndex]}x
              </button>
              <AnimatePresence>
                {mainSpeedOpen && (
                  <motion.div
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: 8 }}
                    transition={{ duration: 0.15 }}
                    className="absolute bottom-full mb-2 right-0 bg-neutral-950 border border-white/15 rounded-lg shadow-2xl py-1 min-w-[4rem] z-10"
                  >
                    {SPEEDS.map((s, i) => (
                      <button
                        key={s}
                        onClick={() => selectSpeed(i)}
                        className={`block w-full text-[11px] font-medium px-3 py-1.5 text-center transition-colors ${
                          speedIndex === i ? 'text-white bg-white/15' : 'text-white/70 hover:text-white hover:bg-white/10'
                        }`}
                      >
                        {s}x
                      </button>
                    ))}
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </div>
        </div>

        {/* Mobile only: Volume, Speed, EN/KO row (tap to open popup) */}
        <div className="flex sm:hidden items-center justify-center gap-3 mb-2">
          {/* Volume — tap to open popup */}
          <div className="relative">
            <button
              onClick={() => { setMobileVolumeOpen(v => !v); setMobileSpeedOpen(false) }}
              className={`h-7 w-7 flex items-center justify-center rounded-full ${T.speedBtn}`}
              aria-label="Volume"
            >
              {isMuted || volume === 0 ? <VolumeX size={14} /> : <Volume2 size={14} />}
            </button>
            <AnimatePresence>
              {mobileVolumeOpen && (
                <motion.div
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: 8 }}
                  transition={{ duration: 0.15 }}
                  className="absolute bottom-full mb-1 left-1/2 -translate-x-1/2 bg-neutral-950 border border-white/15 rounded-lg shadow-2xl px-3 py-4 z-10 flex flex-col items-center"
                >
                  <input
                    type="range"
                    min={0}
                    max={1}
                    step={0.05}
                    value={isMuted ? 0 : volume}
                    onChange={handleVolumeChange}
                    className={`h-20 w-1 ${T.volumeTrack} rounded-full appearance-none cursor-pointer [writing-mode:vertical-lr] [direction:rtl] [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:rounded-full ${T.volumeThumb}`}
                    aria-label="Volume"
                  />
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* Speed — tap to open popup */}
          <div className="relative">
            <button
              onClick={() => { setMobileSpeedOpen(v => !v); setMobileVolumeOpen(false) }}
              className={`h-7 flex items-center justify-center text-[11px] font-medium px-2.5 rounded-full ${T.speedBtn}`}
              aria-label={`Playback speed ${SPEEDS[speedIndex]}x`}
            >
              {SPEEDS[speedIndex]}x
            </button>
            <AnimatePresence>
              {mobileSpeedOpen && (
                <motion.div
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: 8 }}
                  transition={{ duration: 0.15 }}
                  className="absolute bottom-full mb-2 left-1/2 -translate-x-1/2 bg-neutral-950 border border-white/15 rounded-lg shadow-2xl py-1 min-w-[4rem] z-10"
                >
                  {SPEEDS.map((s, i) => (
                    <button
                      key={s}
                      onClick={() => { selectSpeed(i); setMobileSpeedOpen(false) }}
                      className={`block w-full text-[11px] font-medium px-3 py-1.5 text-center transition-colors ${
                        speedIndex === i ? 'text-white bg-white/15' : 'text-white/70 hover:text-white hover:bg-white/10'
                      }`}
                    >
                      {s}x
                    </button>
                  ))}
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* EN/KO */}
          {hasToggle && (
            <div className={`flex rounded-lg ${T.toggleBg} p-0.5`}>
              <button
                onClick={() => switchLang('en')}
                className={`text-[11px] font-medium px-3 py-1 rounded-md transition-colors ${
                  lang === 'en' ? T.toggleActive : T.toggleInactive
                }`}
              >
                EN
              </button>
              <button
                onClick={() => switchLang('ko')}
                className={`text-[11px] font-medium px-3 py-1 rounded-md transition-colors ${
                  lang === 'ko' ? T.toggleActive : T.toggleInactive
                }`}
              >
                KO
              </button>
            </div>
          )}
        </div>

        {/* Progress bar with chapter dots */}
        <div
          className={`relative h-1.5 ${T.progressBg} rounded-full cursor-pointer group mb-2`}
          onClick={handleSeek}
          onMouseMove={(e) => {
            const rect = e.currentTarget.getBoundingClientRect()
            const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width))
            setSeekHover({ ratio, x: e.clientX - rect.left })
          }}
          onMouseLeave={() => setSeekHover(null)}
          role="slider"
          aria-label="Seek audio"
          aria-valuenow={Math.round(currentTime)}
          aria-valuemin={0}
          aria-valuemax={Math.round(audioDuration)}
          tabIndex={0}
        >
          {/* Hover tooltip — time + chapter name */}
          {seekHover && audioDuration > 0 && (() => {
            const hoverTime = seekHover.ratio * audioDuration
            const hoverChapter = [...chapters].reverse().find(ch => seekHover.ratio >= ch.position)
            return (
              <div
                className="absolute bottom-full mb-2 -translate-x-1/2 pointer-events-none z-20 flex flex-col items-center"
                style={{ left: seekHover.x }}
              >
                <span className="text-[10px] bg-white/10 backdrop-blur-sm text-white/80 px-2 py-1 rounded whitespace-nowrap">
                  {formatTime(hoverTime)}{hoverChapter ? ` · ${hoverChapter.title}` : ''}
                </span>
              </div>
            )
          })()}
          <div
            className={`h-full rounded-full ${T.progressFill} transition-[width] duration-150 relative`}
            style={{ width: `${progress}%` }}
          >
            <div className={`absolute right-0 top-1/2 -translate-y-1/2 w-3 h-3 rounded-full ${T.seekThumb} shadow-md opacity-0 group-hover:opacity-100 transition-opacity`} />
          </div>
          {chapters.map((ch, i) => {
            const start = ch.position * 100
            const end = i < chapters.length - 1 ? chapters[i + 1].position * 100 : 100
            return (
              <div
                key={i}
                className="group/seg absolute top-0 h-full pointer-events-none"
                style={{ left: `${start}%`, width: `${end - start}%` }}
              >
                {ch.position > 0 && (
                  <div className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-3 bg-white/50 rounded-full" />
                )}
              </div>
            )
          })}
        </div>

        {/* Time */}
        <div className="flex items-center justify-between">
          <span className={`text-[11px] ${T.dim} tabular-nums`}>
            {formatTime(currentTime)}
          </span>
          <span className={`text-[11px] ${T.dim} tabular-nums`}>
            -{formatTime(remaining > 0 ? remaining : 0)}
          </span>
        </div>

      </div>

      {/* Chapter list */}
      {chapters.length > 0 && (
        <div className="px-5 pb-3">
          {/* Mobile: inline expandable chapter list */}
          <div className="md:hidden">
            <button
              onClick={() => setChapterDropdownOpen(v => !v)}
              className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs ${T.chapterActive}`}
            >
              <span className="truncate">
                {activeChapterIndex >= 0 ? chapters[activeChapterIndex].title : chapters[0].title}
              </span>
              <span className="flex items-center gap-1.5 shrink-0 ml-2">
                {audioDuration > 0 && activeChapterIndex >= 0 && (
                  <span className={T.chapterTimeActive}>
                    {formatTime(chapters[activeChapterIndex].position * audioDuration)}
                  </span>
                )}
                {chapterDropdownOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              </span>
            </button>
            <AnimatePresence>
              {chapterDropdownOpen && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.2, ease: 'easeInOut' }}
                  className="overflow-hidden"
                >
                  <div className="mt-1 bg-neutral-950 border border-white/15 rounded-lg py-1 max-h-60 overflow-y-auto overscroll-contain [-webkit-overflow-scrolling:touch]">
                    {chapters.map((ch, i) => (
                      <button
                        key={i}
                        onClick={() => { jumpToChapter(ch.position); setChapterDropdownOpen(false) }}
                        className={`w-full flex items-center justify-between px-3 py-2 text-xs transition-colors ${
                          activeChapterIndex === i ? 'text-white bg-white/10' : 'text-white/50 hover:text-white hover:bg-white/5'
                        }`}
                      >
                        <span className="truncate">{ch.title}</span>
                        {audioDuration > 0 && (
                          <span className={`shrink-0 ml-2 text-[10px] ${activeChapterIndex === i ? T.chapterTimeActive : T.chapterTime}`}>
                            {formatTime(ch.position * audioDuration)}
                          </span>
                        )}
                      </button>
                    ))}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* Desktop: pills */}
          <div ref={chapterListRef} className="hidden md:flex gap-1.5 items-stretch">
            {chapters.map((ch, i) => (
              <button
                key={i}
                onClick={() => jumpToChapter(ch.position)}
                className={`text-[11px] leading-snug px-2 py-1.5 rounded-lg transition-all text-center flex-1 basis-0 min-w-0 min-h-[3rem] flex flex-col items-center justify-center overflow-hidden hover:scale-105 hover:-translate-y-0.5 ${
                  activeChapterIndex === i ? T.chapterActive : T.chapterInactive
                }`}
              >
                <span className="block line-clamp-2">{ch.title}</span>
                {audioDuration > 0 && (
                  <span className={`block text-[9px] ${activeChapterIndex === i ? T.chapterTimeActive : T.chapterTime}`}>
                    {formatTime(ch.position * audioDuration)}
                  </span>
                )}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Transcript with sentence-level highlighting */}
      <AnimatePresence>
        {showTranscript && (sentences.length > 0 || transcript) && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: 'easeInOut' }}
            className="overflow-hidden"
          >
            <div className={`border-t ${T.border} px-5 py-3`}>
              <div className="flex items-center justify-between mb-2">
                <p className={`text-[11px] font-semibold ${T.dim} uppercase tracking-wider`}>
                  Transcript
                </p>
                <button
                  onClick={() => setTranscriptExpanded(v => !v)}
                  className={`text-[10px] ${T.dim} ${T.surfaceHover} px-1.5 py-0.5 rounded transition-colors`}
                  aria-label={transcriptExpanded ? 'Collapse transcript' : 'Expand transcript'}
                >
                  {transcriptExpanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                </button>
              </div>
              <div ref={transcriptRef} className={`${transcriptExpanded ? 'max-h-80' : 'max-h-28 sm:max-h-28'} overflow-y-auto overscroll-contain [-webkit-overflow-scrolling:touch] pr-2 [&::-webkit-scrollbar]:w-1.5 [&::-webkit-scrollbar-track]:bg-transparent [&::-webkit-scrollbar-thumb]:bg-white/30 [&::-webkit-scrollbar-thumb]:rounded-full transition-[max-height] duration-300`}>
                {sentences.length > 0 ? (
                  <div className="space-y-4">
                    {chapterGroups.map((group, gi) => (
                      <div key={gi}>
                        {group.title && (
                          <h4 className={`text-[11px] font-semibold uppercase tracking-wider mb-1.5 transition-colors duration-300 ${
                            group.sentences.some(s => s.globalIndex === activeSentenceIndex)
                              ? T.headingActive
                              : T.headingInactive
                          }`}>
                            {group.title}
                          </h4>
                        )}
                        <p className="text-xs sm:text-sm leading-relaxed">
                          {group.sentences.map((sent) => (
                            <React.Fragment key={sent.globalIndex}>
                            <span
                              ref={sent.globalIndex === activeSentenceIndex ? (el) => {
                                if (!el || userScrolledRef.current || !transcriptRef.current) return
                                if (lastScrolledSentence.current === activeSentenceIndex) return
                                lastScrolledSentence.current = activeSentenceIndex
                                const container = transcriptRef.current
                                const elRect = el.getBoundingClientRect()
                                const containerRect = container.getBoundingClientRect()
                                const targetTop = container.scrollTop + (elRect.top - containerRect.top) - 8
                                const start = container.scrollTop
                                const distance = targetTop - start
                                const absDist = Math.abs(distance)
                                if (absDist < 2) return
                                if (absDist > container.clientHeight) {
                                  isAutoScrolling.current = true
                                  container.scrollTop = targetTop
                                  requestAnimationFrame(() => { isAutoScrolling.current = false })
                                } else {
                                  const dur = Math.min(400, absDist * 3)
                                  let startTime: number | null = null
                                  isAutoScrolling.current = true
                                  const step = (timestamp: number) => {
                                    if (!startTime) startTime = timestamp
                                    const elapsed = timestamp - startTime
                                    const t = Math.min(elapsed / dur, 1)
                                    const ease = t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2
                                    container.scrollTop = start + distance * ease
                                    if (t < 1) requestAnimationFrame(step)
                                    else isAutoScrolling.current = false
                                  }
                                  requestAnimationFrame(step)
                                }
                              } : undefined}
                              className={`transition-colors duration-300 ${
                                sent.globalIndex === activeSentenceIndex
                                  ? T.transcriptActive
                                  : sent.globalIndex < activeSentenceIndex
                                    ? T.transcriptPast
                                    : T.transcriptFuture
                              } cursor-pointer hover:opacity-80`}
                              onClick={() => seekTo(sent.start)}
                            >
                              {sent.text}
                            </span>{' '}
                            </React.Fragment>
                          ))}
                        </p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className={`text-sm leading-relaxed ${T.muted} whitespace-pre-line`}>
                    {transcript}
                  </p>
                )}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Expandable sources list */}
      <AnimatePresence>
        {isExpanded && sources.length > 0 && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: 'easeInOut' }}
            className="overflow-hidden"
          >
            <div className={`border-t ${T.border} px-5 py-3`}>
              <p className={`text-[11px] font-semibold ${T.dim} uppercase tracking-wider mb-2`}>
                Sources · {sources.length} articles
              </p>
              <div className="max-h-40 overflow-y-auto pr-1 [&::-webkit-scrollbar]:w-1.5 [&::-webkit-scrollbar-track]:bg-transparent [&::-webkit-scrollbar-thumb]:bg-white/30 [&::-webkit-scrollbar-thumb]:rounded-full">
                {sources.map((src, i) => (
                  <a
                    key={i}
                    href={src.link || undefined}
                    target={src.link ? '_blank' : undefined}
                    rel={src.link ? 'noopener noreferrer' : undefined}
                    className={`flex items-center gap-2 py-1.5 px-1 -mx-1 rounded ${T.sourceHover} transition-colors group`}
                  >
                    <span className={`text-xs ${T.dim} tabular-nums shrink-0 w-4 text-right`}>
                      {i + 1}
                    </span>
                    <p className={`text-sm leading-snug ${T.sourceText} transition-colors truncate flex-1`}>
                      {src.title}
                    </p>
                    <span className={`text-xs ${T.muted} shrink-0`}>
                      {categoryLabel(src.feed_name)}
                    </span>
                  </a>
                ))}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>

    </>
  )
}
