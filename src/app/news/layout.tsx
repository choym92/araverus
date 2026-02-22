import type { Metadata } from 'next'
import { BriefingProvider } from './_components/BriefingContext'
import BriefingMiniPlayer from './_components/BriefingMiniPlayer'

export const metadata: Metadata = {
  title: 'News | Paul Cho',
  description: 'Daily curated finance news and audio briefings from trusted sources.',
}

export default function NewsLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <BriefingProvider>
      {children}
      {/* Standalone mini-player for article pages (full player passes its own visibility) */}
      <BriefingMiniPlayer />
    </BriefingProvider>
  )
}
