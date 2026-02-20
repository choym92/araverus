'use client'

import { useRef, useState, useCallback, useEffect, useMemo } from 'react'
import { createPortal } from 'react-dom'
import { Play, Pause, RotateCcw, RotateCw, ChevronDown, ChevronUp, Captions, Layers, Volume2, VolumeX } from 'lucide-react'
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

const SPEEDS = [1, 1.25, 1.5, 2] as const

/** Theme config — swap this object to restyle the entire player */
const T = {
  // Wrapper
  wrapper: 'bg-neutral-950 text-white shadow-xl',
  // Text
  text: 'text-white',
  muted: 'text-white/50',
  dim: 'text-white/40',
  dimmer: 'text-white/25',
  dimmest: 'text-white/20',
  // Surfaces
  surface: 'bg-white/5',
  surfaceHover: 'hover:bg-white/10',
  surfaceActive: 'bg-white/20',
  // Borders
  border: 'border-white/10',
  borderSubtle: 'border-white/5',
  // Accent badge (AI icon)
  accent: 'bg-gradient-to-br from-gray-300 via-gray-500 to-gray-300 text-white',
  // Progress bar
  progressBg: 'bg-white/15',
  progressFill: 'bg-gradient-to-r from-gray-300 via-gray-500 to-gray-300',
  progressDivider: 'bg-white/20',
  seekThumb: 'bg-white',
  // Play button
  playBtn: 'bg-white text-neutral-950',
  // Speed button
  speedBtn: 'bg-white/10 hover:bg-white/20 text-white/70 hover:text-white',
  // Toggle (EN/KO)
  toggleBg: 'bg-white/5',
  toggleActive: 'bg-white/15 text-white',
  toggleInactive: 'text-white/40 hover:text-white/70',
  // Chapters
  chapterActive: 'bg-white/20 text-white font-medium ring-2 ring-white/40 shadow-[0_0_8px_rgba(255,255,255,0.15)]',
  chapterInactive: 'bg-white/5 text-white/40 hover:bg-white/10 hover:text-white/70',
  chapterTime: 'text-white/25',
  chapterTimeActive: 'text-white/50',
  // Transcript
  transcriptActive: 'text-white bg-white/10 rounded px-0.5 -mx-0.5',
  transcriptPast: 'text-white/50',
  transcriptFuture: 'text-white/25',
  headingActive: 'text-gray-300',
  headingInactive: 'text-white/30',
  // Scrollbar
  scrollbar: 'scrollbar-thumb-white/10',
  // Volume
  volumeTrack: 'bg-white/15',
  volumeThumb: '[&::-webkit-slider-thumb]:bg-white',
  // Source list
  sourceHover: 'hover:bg-white/5',
  sourceText: 'text-white/60 group-hover:text-white/90',
  // Mini player
  miniWrapper: 'bg-neutral-950/95 backdrop-blur-md border-t border-white/10 text-white shadow-2xl',
  miniPlayBtn: 'bg-white text-neutral-950',
} as const

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
  const playerRef = useRef<HTMLDivElement>(null)
  const [lang, setLang] = useState<'en' | 'ko'>(defaultLang)
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [audioDuration, setAudioDuration] = useState(duration)
  const [speedIndex, setSpeedIndex] = useState(0)
  const [mainSpeedOpen, setMainSpeedOpen] = useState(false)
  const [miniSpeedOpen, setMiniSpeedOpen] = useState(false)
  const [miniTranscriptOpen, setMiniTranscriptOpen] = useState(true)
  const [chapterDropdownOpen, setChapterDropdownOpen] = useState(false)
  const [volumePopupOpen, setVolumePopupOpen] = useState(false)
  const [miniVolumeOpen, setMiniVolumeOpen] = useState(false)
  const [seekHover, setSeekHover] = useState<{ ratio: number; x: number } | null>(null)
  const [isExpanded, setIsExpanded] = useState(false)
  const [showTranscript, setShowTranscript] = useState(true)
  const [volume, setVolume] = useState(1)
  const [isMuted, setIsMuted] = useState(false)
  const [userScrolled, setUserScrolled] = useState(false)
  const [isPlayerVisible, setIsPlayerVisible] = useState(true)
  const [isMiniMinimized, setIsMiniMinimized] = useState(false)
  const userScrollTimeout = useRef<NodeJS.Timeout | null>(null)
  const lastTapRef = useRef<{ time: number; side: 'left' | 'right' } | null>(null)
  const transcriptRef = useRef<HTMLDivElement>(null)
  const chapterListRef = useRef<HTMLDivElement>(null)

  // Active language data
  const activeLang = lang === 'ko' && ko ? ko : en
  const audioUrl = activeLang?.audioUrl ?? ''
  const chapters = Array.isArray(activeLang?.chapters) ? activeLang.chapters : []
  const transcript = activeLang?.transcript ?? ''
  const sentences = Array.isArray(activeLang?.sentences) ? activeLang.sentences : []
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

  const selectSpeed = useCallback((idx: number) => {
    setSpeedIndex(idx)
    if (audioRef.current) {
      audioRef.current.playbackRate = SPEEDS[idx]
    }
  }, [])

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
          skip(-15)
          break
        case 'ArrowRight':
          e.preventDefault()
          skip(15)
          break
        case 'ArrowUp':
          e.preventDefault()
          { const v = Math.min(1, audio.volume + 0.1); audio.volume = v; setVolume(v); setIsMuted(false) }
          break
        case 'ArrowDown':
          e.preventDefault()
          { const v = Math.max(0, audio.volume - 0.1); audio.volume = v; setVolume(v) }
          break
        case 'KeyM':
          e.preventDefault()
          { const m = !audio.muted; audio.muted = m; setIsMuted(m) }
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

  // Pause auto-scroll when user scrolls the transcript manually
  useEffect(() => {
    const container = transcriptRef.current
    if (!container) return
    const onScroll = () => {
      setUserScrolled(true)
      if (userScrollTimeout.current) clearTimeout(userScrollTimeout.current)
      userScrollTimeout.current = setTimeout(() => setUserScrolled(false), 2000)
    }
    container.addEventListener('scroll', onScroll, { passive: true })
    return () => {
      container.removeEventListener('scroll', onScroll)
      if (userScrollTimeout.current) clearTimeout(userScrollTimeout.current)
    }
  }, [showTranscript])

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

  // IntersectionObserver: detect when full player scrolls out of view
  useEffect(() => {
    const el = playerRef.current
    if (!el) return
    const observer = new IntersectionObserver(
      ([entry]) => {
        setIsPlayerVisible(entry.isIntersecting)
        // Reset dismiss when player comes back into view
        if (entry.isIntersecting) setIsMiniMinimized(false)
      },
      { threshold: 0 }
    )
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  // Auto-scroll chapter pills to active chapter (mobile horizontal scroll)
  useEffect(() => {
    const container = chapterListRef.current
    if (!container || activeChapterIndex < 0) return
    const activeBtn = container.children[activeChapterIndex] as HTMLElement
    if (!activeBtn) return
    const left = activeBtn.offsetLeft - container.clientWidth / 2 + activeBtn.clientWidth / 2
    container.scrollTo({ left, behavior: 'smooth' })
  }, [activeChapterIndex])

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

  // Group sentences by chapter
  const chapterGroups = useMemo(() => {
    if (sentences.length === 0) return []
    if (chapters.length === 0) return [{ title: null, sentences: sentences.map((s, i) => ({ ...s, globalIndex: i })) }]

    const chapterTimes = chapters.map(ch => ch.position * audioDuration)
    const groups: { title: string | null; sentences: (BriefingSentence & { globalIndex: number })[] }[] =
      chapters.map(ch => ({ title: ch.title, sentences: [] }))

    sentences.forEach((sent, i) => {
      let chIdx = 0
      for (let c = chapterTimes.length - 1; c >= 0; c--) {
        if (sent.start >= chapterTimes[c]) { chIdx = c; break }
      }
      groups[chIdx].sentences.push({ ...sent, globalIndex: i })
    })

    const filtered = groups.filter(g => g.sentences.length > 0)

    // Split closing sentences from the last chapter
    const closingPatterns = /여기까지입니다|that'?s all for today|that wraps up|오늘 준비한 소식은|see you|다시 돌아올게|until next time|have a great/i
    const lastGroup = filtered[filtered.length - 1]
    if (lastGroup && lastGroup.sentences.length > 1) {
      const closingIdx = lastGroup.sentences.findIndex(s => closingPatterns.test(s.text))
      if (closingIdx > 0) {
        const closingSentences = lastGroup.sentences.splice(closingIdx)
        filtered.push({ title: '✦', sentences: closingSentences })
      }
    }

    return filtered
  }, [sentences, chapters, audioDuration])

  const showMini = !isPlayerVisible && !!audioUrl

  return (
    <>
    <div ref={playerRef} className={`rounded-2xl ${T.wrapper} overflow-hidden`}>
      {audioUrl && <audio ref={audioRef} src={audioUrl} preload="metadata" />}

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
            {/* EN/KO toggle */}
            {hasToggle && (
              <div className={`flex rounded-lg ${T.toggleBg} p-0.5 mr-1`}>
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
                className={`flex items-center gap-1 px-1.5 py-1 rounded-lg ${T.surfaceHover} transition-colors ${T.dim} text-[11px]`}
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
        <div className="flex items-center justify-center mb-3">
          {/* Left spacer to balance right controls */}
          <div className="flex-1" />

          {/* Playback controls */}
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

          {/* Volume + Speed (right side) */}
          <div className="flex-1 flex items-center justify-end gap-2">
            {/* Volume — hover to adjust, click to mute */}
            <div
              className="relative"
              onMouseEnter={() => setVolumePopupOpen(true)}
              onMouseLeave={() => setVolumePopupOpen(false)}
            >
              <button
                onClick={toggleMute}
                className={`p-1 rounded ${T.surfaceHover} transition-colors ${T.muted}`}
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

            {/* Speed — hover to show options, click to cycle */}
            <div
              className="relative"
              onMouseEnter={() => setMainSpeedOpen(true)}
              onMouseLeave={() => setMainSpeedOpen(false)}
            >
              <button
                onClick={() => selectSpeed((speedIndex + 1) % SPEEDS.length)}
                className={`text-[11px] font-medium px-2 py-0.5 rounded-full ${T.speedBtn}`}
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
          {/* Chapter dividers + hover highlight */}
          {chapters.map((ch, i) => {
            const start = ch.position * 100
            const end = i < chapters.length - 1 ? chapters[i + 1].position * 100 : 100
            return (
              <div
                key={i}
                className="group/seg absolute top-0 h-full pointer-events-none"
                style={{ left: `${start}%`, width: `${end - start}%` }}
              >
                {/* Divider line (skip first chapter) */}
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
          {/* Mobile: dropdown */}
          <div className="md:hidden relative">
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
                  initial={{ opacity: 0, y: -4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -4 }}
                  transition={{ duration: 0.15 }}
                  className="absolute top-full mt-1 left-0 right-0 bg-neutral-950 border border-white/15 rounded-lg shadow-2xl py-1 z-20 max-h-60 overflow-y-auto"
                >
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
              <p className={`text-[11px] font-semibold ${T.dim} uppercase tracking-wider mb-2`}>
                Transcript
              </p>
              <div ref={transcriptRef} className="max-h-28 overflow-y-auto pr-2 [&::-webkit-scrollbar]:w-1.5 [&::-webkit-scrollbar-track]:bg-transparent [&::-webkit-scrollbar-thumb]:bg-white/30 [&::-webkit-scrollbar-thumb]:rounded-full">
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
                            <span
                              key={sent.globalIndex}
                              ref={sent.globalIndex === activeSentenceIndex ? (el) => {
                                if (el && !userScrolled && transcriptRef.current) {
                                  const container = transcriptRef.current
                                  const elRect = el.getBoundingClientRect()
                                  const containerRect = container.getBoundingClientRect()
                                  const targetTop = container.scrollTop + (elRect.top - containerRect.top) - container.clientHeight / 3
                                  const start = container.scrollTop
                                  const distance = targetTop - start
                                  const duration = 800
                                  let startTime: number | null = null
                                  const step = (timestamp: number) => {
                                    if (!startTime) startTime = timestamp
                                    const elapsed = timestamp - startTime
                                    const t = Math.min(elapsed / duration, 1)
                                    const ease = t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2
                                    container.scrollTop = start + distance * ease
                                    if (t < 1) requestAnimationFrame(step)
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
                              onClick={() => {
                                if (audioRef.current) {
                                  audioRef.current.currentTime = sent.start
                                  setCurrentTime(sent.start)
                                }
                              }}
                            >
                              {sent.text}{' '}
                            </span>
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

    {/* Sticky mini-player portal */}
    {typeof document !== 'undefined' && createPortal(
      <AnimatePresence>
        {showMini && (
          <motion.div
            initial={{ y: '100%' }}
            animate={{ y: 0 }}
            exit={{ y: '100%' }}
            transition={{ type: 'spring', damping: 25, stiffness: 300 }}
            className={`fixed bottom-0 left-0 right-0 z-50 ${T.miniWrapper}`}
          >
            <div className="max-w-5xl mx-auto px-4 py-2.5 flex items-center gap-3">
              {/* Icon */}
              <div className={`w-8 h-8 rounded-lg ${T.accent} flex items-center justify-center shrink-0`}>
                <span className="text-xs font-bold tracking-tight">AI</span>
              </div>

              {/* Title */}
              {!isMiniMinimized && (
                <div className="shrink-0 hidden sm:block">
                  <p className="text-xs font-medium leading-tight">Daily Briefing</p>
                  <p className={`text-[10px] ${T.dim}`}>{date}</p>
                </div>
              )}

              {/* Progress bar */}
              <div
                className={`flex-1 h-1 ${T.progressBg} rounded-full cursor-pointer group min-w-[60px]`}
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

              {/* Volume — hover to adjust, click to mute */}
              <div
                className="relative shrink-0"
                onMouseEnter={() => setMiniVolumeOpen(true)}
                onMouseLeave={() => setMiniVolumeOpen(false)}
              >
                <button
                  onClick={toggleMute}
                  className={`p-1 rounded ${T.surfaceHover} transition-colors ${T.muted}`}
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

              {/* Play/Pause */}
              <button
                onClick={togglePlay}
                className={`w-8 h-8 rounded-full ${T.miniPlayBtn} flex items-center justify-center hover:scale-105 active:scale-95 transition-transform shrink-0`}
                aria-label={isPlaying ? 'Pause' : 'Play'}
              >
                {isPlaying ? <Pause size={14} fill="currentColor" /> : <Play size={14} fill="currentColor" className="ml-0.5" />}
              </button>

              {/* Speed (hidden when minimized) — hover to show, click to cycle */}
              {!isMiniMinimized && (
                <div
                  className="relative shrink-0"
                  onMouseEnter={() => setMiniSpeedOpen(true)}
                  onMouseLeave={() => setMiniSpeedOpen(false)}
                >
                  <button
                    onClick={() => selectSpeed((speedIndex + 1) % SPEEDS.length)}
                    className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full ${T.speedBtn}`}
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

              {/* Minimize / Expand */}
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
    )}
    </>
  )
}
