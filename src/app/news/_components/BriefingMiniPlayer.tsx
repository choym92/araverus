'use client'

import { useState, useEffect, useRef } from 'react'
import { usePathname } from 'next/navigation'
import { createPortal } from 'react-dom'
import { Play, Pause, ChevronDown, ChevronUp, Captions, Volume2, VolumeX } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { useBriefingOptional, formatTime, SPEEDS } from './BriefingContext'

/** Theme — keep in sync with BriefingPlayer T object */
const T = {
  text: 'text-white',
  muted: 'text-white/50',
  dim: 'text-white/40',
  dimmer: 'text-white/25',
  accent: 'bg-gradient-to-br from-gray-300 via-gray-500 to-gray-300 text-white',
  progressBg: 'bg-white/15',
  progressFill: 'bg-gradient-to-r from-gray-300 via-gray-500 to-gray-300',
  seekThumb: 'bg-white',
  speedBtn: 'bg-white/10 hover:bg-white/20 text-white/70 hover:text-white',
  toggleBg: 'bg-white/5',
  toggleActive: 'bg-white/15 text-white',
  toggleInactive: 'text-white/40 hover:text-white/70',
  surfaceHover: 'hover:bg-white/10',
  volumeTrack: 'bg-white/15',
  volumeThumb: '[&::-webkit-slider-thumb]:bg-white',
  miniWrapper: 'bg-neutral-950/95 backdrop-blur-md border-t border-white/10 text-white shadow-2xl pb-[env(safe-area-inset-bottom)]',
  miniPlayBtn: 'bg-white text-neutral-950',
} as const

export default function BriefingMiniPlayer() {
  const ctx = useBriefingOptional()
  const [miniSpeedOpen, setMiniSpeedOpen] = useState(false)
  const [miniVolumeOpen, setMiniVolumeOpen] = useState(false)
  const [miniTranscriptOpen, setMiniTranscriptOpen] = useState(true)
  const [isMiniMinimized, setIsMiniMinimized] = useState(false)
  const pathname = usePathname()
  const prevPathname = useRef(pathname)

  // Auto-minimize on mobile only when navigating to an article page
  useEffect(() => {
    const isMobile = window.innerWidth < 640
    const navigatedToArticle = prevPathname.current === '/news' && pathname !== '/news'
    if (isMobile && navigatedToArticle) {
      setIsMiniMinimized(true)
    }
    // Reset minimize when going back to landing page
    if (pathname === '/news') {
      setIsMiniMinimized(false)
    }
    prevPathname.current = pathname
  }, [pathname])

  if (!ctx || !ctx.audioUrl) return null

  const {
    data, lang, isPlaying, currentTime, audioDuration, speedIndex, volume, isMuted,
    switchLang, togglePlay, handleSeek, selectSpeed, handleVolumeChange, toggleMute,
    audioUrl, sentences, hasToggle, progress, activeSentenceIndex,
    isFullPlayerVisible,
  } = ctx

  // Show when: audio loaded AND full player is not visible (scrolled away or on article page)
  const shouldShow = !!audioUrl && !isFullPlayerVisible

  if (typeof document === 'undefined') return null

  return createPortal(
    <AnimatePresence>
      {shouldShow && (
        <motion.div
          initial={{ y: '100%' }}
          animate={{ y: 0 }}
          exit={{ y: '100%' }}
          transition={{ type: 'spring', damping: 25, stiffness: 300 }}
          className={`fixed bottom-0 left-0 right-0 z-50 ${T.miniWrapper}`}
        >
          <div className="max-w-5xl mx-auto px-4 py-2.5 flex items-center gap-2 sm:gap-3">
            {/* Icon */}
            <div className={`w-8 h-8 rounded-lg ${T.accent} flex items-center justify-center shrink-0`}>
              <span className="text-xs font-bold tracking-tight">AI</span>
            </div>

            {/* Title — desktop only */}
            {!isMiniMinimized && (
              <div className="shrink-0 hidden sm:block">
                <p className="text-xs font-medium leading-tight">Daily Briefing</p>
                <p className={`text-[10px] ${T.dim}`}>{data?.date}</p>
              </div>
            )}

            {/* Progress bar */}
            <div
              className={`flex-1 h-1 ${T.progressBg} rounded-full cursor-pointer group min-w-[40px]`}
              onClick={handleSeek}
            >
              <div
                className={`h-full rounded-full ${T.progressFill} relative`}
                style={{ width: `${progress}%` }}
              >
                <div className={`absolute right-0 top-1/2 -translate-y-1/2 w-2.5 h-2.5 rounded-full ${T.seekThumb} shadow-md opacity-0 group-hover:opacity-100 transition-opacity`} />
              </div>
            </div>

            {/* Time */}
            <span className={`text-[10px] ${T.dim} tabular-nums shrink-0`}>
              {formatTime(currentTime)}/{formatTime(audioDuration)}
            </span>

            {/* Play/Pause + Volume + Speed — grouped tight */}
            <div className="flex items-center gap-1.5 shrink-0">
              {/* Volume */}
              {!isMiniMinimized && (
                <div
                  className="relative flex items-center"
                  onMouseEnter={() => setMiniVolumeOpen(true)}
                  onMouseLeave={() => setMiniVolumeOpen(false)}
                >
                  <button
                    onClick={toggleMute}
                    className={`w-7 h-7 flex items-center justify-center rounded ${T.surfaceHover} transition-colors ${T.muted}`}
                    aria-label={isMuted ? 'Unmute' : 'Mute'}
                  >
                    {isMuted || volume === 0 ? <VolumeX size={14} /> : <Volume2 size={14} />}
                  </button>
                  <AnimatePresence>
                    {miniVolumeOpen && (
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
                          className={`h-16 w-1 ${T.volumeTrack} rounded-full appearance-none cursor-pointer [writing-mode:vertical-lr] [direction:rtl] [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:rounded-full ${T.volumeThumb}`}
                          aria-label="Volume"
                        />
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              )}

              {/* Speed */}
              {!isMiniMinimized && (
                <div
                  className="relative flex items-center"
                  onMouseEnter={() => setMiniSpeedOpen(true)}
                  onMouseLeave={() => setMiniSpeedOpen(false)}
                >
                  <button
                    onClick={() => selectSpeed((speedIndex + 1) % SPEEDS.length)}
                    className={`h-7 flex items-center justify-center text-[10px] font-medium px-2 rounded-full ${T.speedBtn}`}
                  >
                    {SPEEDS[speedIndex]}x
                  </button>
                  <AnimatePresence>
                    {miniSpeedOpen && (
                      <motion.div
                        initial={{ opacity: 0, y: 8 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: 8 }}
                        transition={{ duration: 0.15 }}
                        className="absolute bottom-full mb-2 left-1/2 -translate-x-1/2 bg-neutral-950 border border-white/15 rounded-lg shadow-2xl py-1 min-w-[4rem]"
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
              )}

              {/* Play/Pause */}
              <button
                onClick={togglePlay}
                className={`w-8 h-8 rounded-full ${T.miniPlayBtn} flex items-center justify-center hover:scale-105 active:scale-95 transition-transform`}
                aria-label={isPlaying ? 'Pause' : 'Play'}
              >
                {isPlaying ? <Pause size={14} fill="currentColor" /> : <Play size={14} fill="currentColor" className="ml-0.5" />}
              </button>
            </div>

            {/* EN/KO toggle (hidden when minimized) */}
            {!isMiniMinimized && hasToggle && (
              <div className={`flex rounded-md ${T.toggleBg} p-0.5 shrink-0`}>
                <button
                  onClick={() => switchLang('en')}
                  className={`text-[10px] font-medium px-1.5 py-0.5 rounded transition-colors ${
                    lang === 'en' ? T.toggleActive : T.toggleInactive
                  }`}
                >
                  EN
                </button>
                <button
                  onClick={() => switchLang('ko')}
                  className={`text-[10px] font-medium px-1.5 py-0.5 rounded transition-colors ${
                    lang === 'ko' ? T.toggleActive : T.toggleInactive
                  }`}
                >
                  KO
                </button>
              </div>
            )}

            {/* Transcript toggle (hidden when minimized) */}
            {!isMiniMinimized && (
              <button
                onClick={() => setMiniTranscriptOpen(v => !v)}
                className={`p-1 rounded ${T.surfaceHover} transition-colors shrink-0 ${miniTranscriptOpen ? T.text : T.dim}`}
                aria-label={miniTranscriptOpen ? 'Hide transcript' : 'Show transcript'}
              >
                <Captions size={14} />
              </button>
            )}

            {/* Minimize / Expand — always visible */}
            <button
              onClick={() => setIsMiniMinimized(v => !v)}
              className={`p-1 rounded ${T.surfaceHover} transition-colors ${T.dim} shrink-0`}
              aria-label={isMiniMinimized ? 'Expand mini player' : 'Minimize mini player'}
            >
              {isMiniMinimized ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            </button>
          </div>

          {/* Mini transcript — current + next sentence (hidden when minimized) */}
          {!isMiniMinimized && miniTranscriptOpen && sentences.length > 0 && activeSentenceIndex >= 0 && (
            <div className="max-w-5xl mx-auto px-4 pb-2.5">
              <div className="text-xs sm:text-sm leading-relaxed h-10 overflow-hidden">
                <span className={T.text}>
                  {sentences[activeSentenceIndex]?.text}
                </span>
                {sentences[activeSentenceIndex + 1] && (
                  <span className={T.dimmer}>
                    {' '}{sentences[activeSentenceIndex + 1].text}
                  </span>
                )}
              </div>
            </div>
          )}
        </motion.div>
      )}
    </AnimatePresence>,
    document.body
  )
}
