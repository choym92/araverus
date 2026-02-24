'use client'

import { createContext, useContext, useRef, useState, useCallback, useEffect, useMemo, type ReactNode } from 'react'

// Re-export types from BriefingPlayer for convenience
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

export interface BriefingData {
  date: string
  duration: number
  sourceCount?: number
  sources?: BriefingSource[]
  en?: BriefingLangData
  ko?: BriefingLangData
  defaultLang?: 'en' | 'ko'
}

const SPEEDS = [1, 1.1, 1.25, 1.5, 2] as const
const SPEED_PRESETS = [1, 1.25, 1.5, 2] as const
const SPEED_MIN = 0.5
const SPEED_MAX = 3.0
const SPEED_STEP = 0.05

interface BriefingContextValue {
  // Briefing data
  data: BriefingData | null
  setData: (data: BriefingData) => void

  // Full player visibility (set by BriefingPlayer via IntersectionObserver)
  isFullPlayerVisible: boolean
  setFullPlayerVisible: (v: boolean) => void

  // Audio ref (for direct access in transcript click-to-seek etc.)
  audioRef: React.RefObject<HTMLAudioElement | null>

  // Playback state
  lang: 'en' | 'ko'
  isPlaying: boolean
  currentTime: number
  audioDuration: number
  speed: number
  volume: number
  isMuted: boolean

  // Control methods
  switchLang: (lang: 'en' | 'ko') => void
  togglePlay: () => void
  skip: (seconds: number) => void
  handleSeek: (e: React.MouseEvent<HTMLDivElement>) => void
  setSpeed: (value: number) => void
  handleVolumeChange: (e: React.ChangeEvent<HTMLInputElement>) => void
  toggleMute: () => void
  jumpToChapter: (position: number) => void
  seekTo: (time: number) => void

  // Derived values
  audioUrl: string
  chapters: BriefingChapter[]
  transcript: string
  sentences: BriefingSentence[]
  hasToggle: boolean
  progress: number
  remaining: number
  activeChapterIndex: number
  activeSentenceIndex: number
  chapterGroups: { title: string | null; sentences: (BriefingSentence & { globalIndex: number })[] }[]
}

const BriefingContext = createContext<BriefingContextValue | null>(null)

export function useBriefing() {
  const ctx = useContext(BriefingContext)
  if (!ctx) throw new Error('useBriefing must be used within BriefingProvider')
  return ctx
}

export function useBriefingOptional() {
  return useContext(BriefingContext)
}

export function BriefingProvider({ children }: { children: ReactNode }) {
  const audioRef = useRef<HTMLAudioElement>(null)
  const [data, setData] = useState<BriefingData | null>(null)
  const [isFullPlayerVisible, setFullPlayerVisible] = useState(false)

  const [lang, setLang] = useState<'en' | 'ko'>('en')
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [audioDuration, setAudioDuration] = useState(0)
  const [speed, setSpeedRaw] = useState(1.1)
  const [volume, setVolume] = useState(1)
  const [isMuted, setIsMuted] = useState(false)

  // When data is set, initialize defaults
  const handleSetData = useCallback((newData: BriefingData) => {
    setData(prev => {
      // Don't re-initialize if same briefing
      if (prev?.en?.audioUrl === newData.en?.audioUrl && prev?.ko?.audioUrl === newData.ko?.audioUrl) {
        return prev
      }
      return newData
    })
    if (!data) {
      setLang(newData.defaultLang ?? 'en')
      setAudioDuration(newData.duration)
    }
  }, [data])

  // Active language data
  const activeLang = lang === 'ko' && data?.ko ? data.ko : data?.en
  const audioUrl = activeLang?.audioUrl ?? ''
  const chapters = useMemo(() => Array.isArray(activeLang?.chapters) ? activeLang.chapters : [], [activeLang?.chapters])
  const transcript = activeLang?.transcript ?? ''
  const sentences = useMemo(() => Array.isArray(activeLang?.sentences) ? activeLang.sentences : [], [activeLang?.sentences])
  const hasToggle = !!data?.en && !!data?.ko

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
    setAudioDuration(data?.duration ?? 0)
    setTimeout(() => {
      const a = audioRef.current
      if (a && wasPlaying) {
        a.play()
        setIsPlaying(true)
      }
    }, 100)
  }, [lang, isPlaying, data?.duration])

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

  const setSpeed = useCallback((value: number) => {
    const clamped = Math.round(Math.max(SPEED_MIN, Math.min(SPEED_MAX, value)) * 100) / 100
    setSpeedRaw(clamped)
    if (audioRef.current) {
      audioRef.current.playbackRate = clamped
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

  const seekTo = useCallback((time: number) => {
    if (audioRef.current) {
      audioRef.current.currentTime = time
      setCurrentTime(time)
    }
  }, [])

  // Audio event listeners
  useEffect(() => {
    const audio = audioRef.current
    if (!audio) return

    const onTimeUpdate = () => {
      setCurrentTime(audio.currentTime)
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

    if (audio.duration && isFinite(audio.duration)) {
      setAudioDuration(audio.duration)
    }
    audio.playbackRate = speed

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

  // Resume position: save
  useEffect(() => {
    if (!audioUrl || currentTime === 0) return
    const key = `briefing-resume:${audioUrl}`
    localStorage.setItem(key, String(currentTime))
  }, [currentTime, audioUrl])

  // Resume position: restore
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

  // Derived values
  const progress = audioDuration > 0 ? (currentTime / audioDuration) * 100 : 0
  const remaining = audioDuration - currentTime

  const activeChapterIndex = useMemo(() => {
    if (chapters.length === 0) return -1
    return chapters.reduce((active, ch, i) => {
      const chTime = ch.position * audioDuration
      return currentTime >= chTime ? i : active
    }, 0)
  }, [chapters, currentTime, audioDuration])

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

  const value = useMemo<BriefingContextValue>(() => ({
    data,
    setData: handleSetData,
    isFullPlayerVisible,
    setFullPlayerVisible,
    audioRef,
    lang,
    isPlaying,
    currentTime,
    audioDuration,
    speed,
    volume,
    isMuted,
    switchLang,
    togglePlay,
    skip,
    handleSeek,
    setSpeed,
    handleVolumeChange,
    toggleMute,
    jumpToChapter,
    seekTo,
    audioUrl,
    chapters,
    transcript,
    sentences,
    hasToggle,
    progress,
    remaining,
    activeChapterIndex,
    activeSentenceIndex,
    chapterGroups,
  }), [
    data, handleSetData, isFullPlayerVisible, lang, isPlaying, currentTime, audioDuration,
    speed, volume, isMuted, switchLang, togglePlay, skip, handleSeek,
    setSpeed, handleVolumeChange, toggleMute, jumpToChapter, seekTo,
    audioUrl, chapters, transcript, sentences, hasToggle, progress, remaining,
    activeChapterIndex, activeSentenceIndex, chapterGroups,
  ])

  return (
    <BriefingContext.Provider value={value}>
      {audioUrl && <audio ref={audioRef} src={audioUrl} preload="metadata" />}
      {children}
    </BriefingContext.Provider>
  )
}

export { SPEEDS, SPEED_PRESETS, SPEED_MIN, SPEED_MAX, SPEED_STEP }
export function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}
