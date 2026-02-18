'use client'

import { useRef, useState, useCallback, useEffect, useMemo } from 'react'
import { Play, Pause, RotateCcw, RotateCw, ChevronDown, ChevronUp, Headphones, ExternalLink, FileText, Volume2, VolumeX, Download } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'

export interface BriefingSource {
  title: string
  feed_name: string
  link: string
  source: string | null
}

export interface BriefingChapter {
  title: string
  position: number // 0.0–1.0 ratio
}

export interface BriefingSentence {
  text: string
  start: number // seconds
  end: number   // seconds
}

export interface BriefingLangData {
  audioUrl: string
  chapters?: BriefingChapter[]
  transcript?: string
  sentences?: BriefingSentence[]
}

interface BriefingPlayerProps {
  date: string
  duration: number
  sourceCount?: number
  sources?: BriefingSource[]
  en?: BriefingLangData
  ko?: BriefingLangData
  defaultLang?: 'en' | 'ko'
}

const SPEEDS = [0.75, 1, 1.25, 1.5, 2] as const

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
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

export default function BriefingPlayer({
  date,
  duration,
  sourceCount = 0,
  sources = [],
  en,
  ko,
  defaultLang = 'en',
}: BriefingPlayerProps) {
  const audioRef = useRef<HTMLAudioElement>(null)
  const [lang, setLang] = useState<'en' | 'ko'>(defaultLang)
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [audioDuration, setAudioDuration] = useState(duration)
  const [speedIndex, setSpeedIndex] = useState(1)
  const [isExpanded, setIsExpanded] = useState(false)
  const [showTranscript, setShowTranscript] = useState(false)
  const [volume, setVolume] = useState(1)
  const [isMuted, setIsMuted] = useState(false)

  // Active language data
  const activeLang = lang === 'ko' && ko ? ko : en
  const audioUrl = activeLang?.audioUrl ?? ''
  const chapters = activeLang?.chapters ?? []
  const transcript = activeLang?.transcript ?? ''
  const sentences = activeLang?.sentences ?? []
  const hasToggle = !!en && !!ko

  // Switch language
  const switchLang = useCallback((newLang: 'en' | 'ko') => {
    if (newLang === lang) return
    const audio = audioRef.current
    const wasPlaying = isPlaying
    if (audio) {
      audio.pause()
      setIsPlaying(false)
    }
    setLang(newLang)
    setCurrentTime(0)
    setAudioDuration(duration)
    // After src change, optionally resume
    setTimeout(() => {
      const a = audioRef.current
      if (a && wasPlaying) {
        a.play()
        setIsPlaying(true)
      }
    }, 100)
  }, [lang, isPlaying, duration])

  const togglePlay = useCallback(() => {
    const audio = audioRef.current
    if (!audio) return
    if (isPlaying) {
      audio.pause()
    } else {
      audio.play()
    }
    setIsPlaying(!isPlaying)
  }, [isPlaying])

  const skip = useCallback((seconds: number) => {
    const audio = audioRef.current
    if (!audio) return
    const dur = audio.duration && isFinite(audio.duration) ? audio.duration : audioDuration
    if (dur <= 0) return
    audio.currentTime = Math.max(0, Math.min(audio.currentTime + seconds, dur))
  }, [audioDuration])

  const handleSeek = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    const audio = audioRef.current
    if (!audio) return
    const dur = audio.duration && isFinite(audio.duration) ? audio.duration : audioDuration
    if (dur <= 0) return
    const rect = e.currentTarget.getBoundingClientRect()
    const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width))
    audio.currentTime = ratio * dur
  }, [audioDuration])

  const cycleSpeed = useCallback(() => {
    const next = (speedIndex + 1) % SPEEDS.length
    setSpeedIndex(next)
    if (audioRef.current) {
      audioRef.current.playbackRate = SPEEDS[next]
    }
  }, [speedIndex])

  const jumpToChapter = useCallback((position: number) => {
    const audio = audioRef.current
    if (!audio) return
    const dur = audio.duration && isFinite(audio.duration) ? audio.duration : audioDuration
    if (dur <= 0) return
    audio.currentTime = position * dur
    if (!isPlaying) {
      audio.play()
      setIsPlaying(true)
    }
  }, [audioDuration, isPlaying])

  useEffect(() => {
    const audio = audioRef.current
    if (!audio) return

    const onTimeUpdate = () => {
      setCurrentTime(audio.currentTime)
      // Also sync duration in case it wasn't set yet
      if (audio.duration && isFinite(audio.duration) && audio.duration !== audioDuration) {
        setAudioDuration(audio.duration)
      }
    }
    const onDurationChange = () => {
      if (audio.duration && isFinite(audio.duration)) {
        setAudioDuration(audio.duration)
      }
    }
    const onEnded = () => setIsPlaying(false)

    audio.addEventListener('timeupdate', onTimeUpdate)
    audio.addEventListener('loadedmetadata', onDurationChange)
    audio.addEventListener('durationchange', onDurationChange)
    audio.addEventListener('ended', onEnded)

    // Check if duration is already available (cached audio)
    if (audio.duration && isFinite(audio.duration)) {
      setAudioDuration(audio.duration)
    }

    return () => {
      audio.removeEventListener('timeupdate', onTimeUpdate)
      audio.removeEventListener('loadedmetadata', onDurationChange)
      audio.removeEventListener('durationchange', onDurationChange)
      audio.removeEventListener('ended', onEnded)
    }
  }, [audioUrl])

  // Keyboard shortcuts
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      // Don't intercept when typing in inputs
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return

      const audio = audioRef.current
      if (!audio) return

      switch (e.code) {
        case 'Space':
          e.preventDefault()
          togglePlay()
          break
        case 'ArrowLeft':
          e.preventDefault()
          skip(-30)
          break
        case 'ArrowRight':
          e.preventDefault()
          skip(30)
          break
        case 'ArrowUp':
          e.preventDefault()
          audio.volume = Math.min(1, audio.volume + 0.1)
          break
        case 'ArrowDown':
          e.preventDefault()
          audio.volume = Math.max(0, audio.volume - 0.1)
          break
        case 'KeyM':
          e.preventDefault()
          audio.muted = !audio.muted
          break
      }
    }

    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [togglePlay, skip])

  const handleVolumeChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const val = parseFloat(e.target.value)
    setVolume(val)
    setIsMuted(val === 0)
    if (audioRef.current) {
      audioRef.current.volume = val
      audioRef.current.muted = val === 0
    }
  }, [])

  const toggleMute = useCallback(() => {
    const audio = audioRef.current
    if (!audio) return
    const next = !isMuted
    setIsMuted(next)
    audio.muted = next
    if (!next && volume === 0) {
      setVolume(0.5)
      audio.volume = 0.5
    }
  }, [isMuted, volume])

  const handleDownload = useCallback(() => {
    if (!audioUrl) return
    const a = document.createElement('a')
    a.href = audioUrl
    a.download = `briefing-${lang}-${date.replace(/[^a-zA-Z0-9]/g, '-')}.mp3`
    a.click()
  }, [audioUrl, lang, date])

  // Resume position: save to localStorage
  useEffect(() => {
    if (!audioUrl || currentTime === 0) return
    const key = `briefing-resume:${audioUrl}`
    localStorage.setItem(key, String(currentTime))
  }, [currentTime, audioUrl])

  // Resume position: restore on mount
  useEffect(() => {
    const audio = audioRef.current
    if (!audio || !audioUrl) return
    const key = `briefing-resume:${audioUrl}`
    const saved = localStorage.getItem(key)
    if (saved) {
      const t = parseFloat(saved)
      if (isFinite(t) && t > 0) {
        audio.currentTime = t
        setCurrentTime(t)
      }
    }
  }, [audioUrl])

  const progress = audioDuration > 0 ? (currentTime / audioDuration) * 100 : 0
  const remaining = audioDuration - currentTime
  const count = sourceCount || sources.length

  const activeChapterIndex = useMemo(() => {
    if (chapters.length === 0) return -1
    return chapters.reduce((active, ch, i) => {
      const chTime = ch.position * audioDuration
      return currentTime >= chTime ? i : active
    }, 0)
  }, [chapters, currentTime, audioDuration])

  // Active sentence index based on real Whisper timestamps
  const activeSentenceIndex = useMemo(() => {
    if (sentences.length === 0 || currentTime <= 0) return 0
    let active = 0
    for (let i = 0; i < sentences.length; i++) {
      if (currentTime >= sentences[i].start) {
        active = i
      } else {
        break
      }
    }
    return active
  }, [sentences, currentTime])

  return (
    <div className="rounded-2xl bg-neutral-950 text-white overflow-hidden shadow-xl">
      {audioUrl && <audio ref={audioRef} src={audioUrl} preload="metadata" />}

      {/* Header */}
      <div className="px-5 pt-5 pb-0">
        <div className="flex items-start justify-between mb-1">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center shrink-0">
              <Headphones size={18} />
            </div>
            <div>
              <h3 className="font-semibold text-sm leading-tight">
                Daily Briefing
              </h3>
              <p className="text-xs text-white/50 mt-0.5">
                {date}{count > 0 && ` · ${count} sources`}{audioDuration > 0 && ` · ${Math.ceil(audioDuration / 60)} min`}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-1">
            {/* EN/KO toggle */}
            {hasToggle && (
              <div className="flex rounded-lg bg-white/5 p-0.5 mr-1">
                <button
                  onClick={() => switchLang('en')}
                  className={`text-[11px] font-medium px-2 py-0.5 rounded-md transition-colors ${
                    lang === 'en' ? 'bg-white/15 text-white' : 'text-white/40 hover:text-white/70'
                  }`}
                >
                  EN
                </button>
                <button
                  onClick={() => switchLang('ko')}
                  className={`text-[11px] font-medium px-2 py-0.5 rounded-md transition-colors ${
                    lang === 'ko' ? 'bg-white/15 text-white' : 'text-white/40 hover:text-white/70'
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
                className={`p-1.5 rounded-lg hover:bg-white/10 transition-colors ${
                  showTranscript ? 'text-white' : 'text-white/50 hover:text-white'
                }`}
                aria-label={showTranscript ? 'Hide transcript' : 'Show transcript'}
              >
                <FileText size={16} />
              </button>
            )}
            {/* Sources toggle */}
            {sources.length > 0 && (
              <button
                onClick={() => setIsExpanded(!isExpanded)}
                className="flex items-center gap-0.5 px-1.5 py-1 rounded-lg hover:bg-white/10 transition-colors text-white/40 hover:text-white/70 text-[11px]"
                aria-label={isExpanded ? 'Collapse sources' : 'Expand sources'}
              >
                <span>{sources.length}</span>
                {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Controls */}
      <div className="px-5 py-4">
        <div className="flex items-center justify-center gap-5 mb-4">
          <button
            onClick={() => skip(-30)}
            className="relative p-2 rounded-full hover:bg-white/10 transition-colors text-white/70 hover:text-white"
            aria-label="Skip back 30 seconds"
          >
            <RotateCcw size={22} />
            <span className="absolute inset-0 flex items-center justify-center text-[8px] font-bold mt-0.5">
              30
            </span>
          </button>

          <button
            onClick={togglePlay}
            className="w-12 h-12 rounded-full bg-white text-neutral-950 flex items-center justify-center hover:scale-105 active:scale-95 transition-transform"
            aria-label={isPlaying ? 'Pause' : 'Play'}
          >
            {isPlaying ? <Pause size={20} fill="currentColor" /> : <Play size={20} fill="currentColor" className="ml-0.5" />}
          </button>

          <button
            onClick={() => skip(30)}
            className="relative p-2 rounded-full hover:bg-white/10 transition-colors text-white/70 hover:text-white"
            aria-label="Skip forward 30 seconds"
          >
            <RotateCw size={22} />
            <span className="absolute inset-0 flex items-center justify-center text-[8px] font-bold mt-0.5">
              30
            </span>
          </button>
        </div>

        {/* Progress bar with chapter dots */}
        <div
          className="relative h-1.5 bg-white/15 rounded-full cursor-pointer group mb-2"
          onClick={handleSeek}
          role="slider"
          aria-label="Seek audio"
          aria-valuenow={Math.round(currentTime)}
          aria-valuemin={0}
          aria-valuemax={Math.round(audioDuration)}
          tabIndex={0}
        >
          <div
            className="h-full rounded-full bg-gradient-to-r from-blue-500 to-purple-500 transition-[width] duration-150 relative"
            style={{ width: `${progress}%` }}
          >
            <div className="absolute right-0 top-1/2 -translate-y-1/2 w-3 h-3 rounded-full bg-white shadow-md opacity-0 group-hover:opacity-100 transition-opacity" />
          </div>
          {chapters.map((ch, i) => (
            ch.position > 0 && (
              <button
                key={i}
                className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 w-2.5 h-2.5 rounded-full bg-white/40 hover:bg-white hover:scale-150 transition-all z-10"
                style={{ left: `${ch.position * 100}%` }}
                onClick={(e) => { e.stopPropagation(); jumpToChapter(ch.position) }}
                aria-label={`Jump to ${ch.title}`}
                title={ch.title}
              />
            )
          ))}
        </div>

        {/* Time + Speed */}
        <div className="flex items-center justify-between">
          <span className="text-[11px] text-white/40 tabular-nums">
            {formatTime(currentTime)}
          </span>
          <button
            onClick={cycleSpeed}
            className="text-[11px] font-medium px-2 py-0.5 rounded-full bg-white/10 hover:bg-white/20 transition-colors text-white/70 hover:text-white"
            aria-label={`Playback speed ${SPEEDS[speedIndex]}x`}
          >
            {SPEEDS[speedIndex]}x
          </button>
          <span className="text-[11px] text-white/40 tabular-nums">
            -{formatTime(remaining > 0 ? remaining : 0)}
          </span>
        </div>

        {/* Volume + Download */}
        <div className="flex items-center justify-between mt-3 pt-2 border-t border-white/5">
          <div className="flex items-center gap-2">
            <button
              onClick={toggleMute}
              className="p-1 rounded hover:bg-white/10 transition-colors text-white/50 hover:text-white"
              aria-label={isMuted ? 'Unmute' : 'Mute'}
            >
              {isMuted || volume === 0 ? <VolumeX size={14} /> : <Volume2 size={14} />}
            </button>
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={isMuted ? 0 : volume}
              onChange={handleVolumeChange}
              className="w-16 h-1 bg-white/15 rounded-full appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-2.5 [&::-webkit-slider-thumb]:h-2.5 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-white"
              aria-label="Volume"
            />
          </div>
          <button
            onClick={handleDownload}
            className="flex items-center gap-1.5 text-[11px] text-white/40 hover:text-white/70 transition-colors"
            aria-label="Download audio"
          >
            <Download size={12} />
            <span>Download</span>
          </button>
        </div>
      </div>

      {/* Chapter list */}
      {chapters.length > 0 && (
        <div className="px-5 pb-3">
          <div className="flex flex-wrap gap-1.5">
            {chapters.map((ch, i) => (
              <button
                key={i}
                onClick={() => jumpToChapter(ch.position)}
                className={`text-[11px] px-2.5 py-1 rounded-full transition-colors ${
                  activeChapterIndex === i
                    ? 'bg-white/20 text-white font-medium'
                    : 'bg-white/5 text-white/40 hover:bg-white/10 hover:text-white/70'
                }`}
              >
                {ch.title}
                {audioDuration > 0 && (
                  <span className="ml-1.5 text-white/30">
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
            <div className="border-t border-white/10 px-5 py-3">
              <p className="text-[11px] font-semibold text-white/40 uppercase tracking-wider mb-2">
                Transcript
              </p>
              <div className="max-h-64 overflow-y-auto pr-2 scrollbar-thin scrollbar-thumb-white/10">
                {sentences.length > 0 ? (
                  <p className="text-sm leading-relaxed">
                    {sentences.map((sent, i) => (
                      <span
                        key={i}
                        ref={i === activeSentenceIndex ? (el) => {
                          if (el && isPlaying) {
                            el.scrollIntoView({ behavior: 'smooth', block: 'center' })
                          }
                        } : undefined}
                        className={`transition-colors duration-300 ${
                          i === activeSentenceIndex
                            ? 'text-white bg-white/10 rounded px-0.5 -mx-0.5'
                            : i < activeSentenceIndex
                              ? 'text-white/50'
                              : 'text-white/25'
                        }`}
                      >
                        {sent.text}{' '}
                      </span>
                    ))}
                  </p>
                ) : (
                  <p className="text-sm leading-relaxed text-white/70 whitespace-pre-line">
                    {transcript}
                  </p>
                )}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Expandable sources list — compact scrollable */}
      <AnimatePresence>
        {isExpanded && sources.length > 0 && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: 'easeInOut' }}
            className="overflow-hidden"
          >
            <div className="border-t border-white/10 px-5 py-3">
              <p className="text-[11px] font-semibold text-white/40 uppercase tracking-wider mb-2">
                Sources · {sources.length} articles
              </p>
              <div className="max-h-40 overflow-y-auto pr-1 scrollbar-thin scrollbar-thumb-white/10">
                {sources.map((src, i) => (
                  <a
                    key={i}
                    href={src.link || undefined}
                    target={src.link ? '_blank' : undefined}
                    rel={src.link ? 'noopener noreferrer' : undefined}
                    className="flex items-center gap-2 py-1.5 px-1 -mx-1 rounded hover:bg-white/5 transition-colors group"
                  >
                    <span className="text-[10px] text-white/20 tabular-nums shrink-0 w-3 text-right">
                      {i + 1}
                    </span>
                    <p className="text-xs leading-snug text-white/60 group-hover:text-white/90 transition-colors truncate flex-1">
                      {src.title}
                    </p>
                    <span className="text-[10px] text-white/20 shrink-0">
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
  )
}
