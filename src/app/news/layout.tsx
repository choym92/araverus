import type { Metadata } from 'next'
import { BriefingProvider } from './_components/BriefingContext'
import BriefingMiniPlayer from './_components/BriefingMiniPlayer'

const podcastSeriesJsonLd = {
  '@context': 'https://schema.org',
  '@type': 'PodcastSeries',
  name: 'AI News Briefing — Araverus',
  description: 'Agentic AI-powered briefings that turn hours of news into minutes — uncover hidden connections across Tech, Markets, and Finance that others miss.',
  url: 'https://araverus.com/news',
  webFeed: 'https://araverus.com/podcast.xml',
  author: { '@type': 'Organization', name: 'Araverus' },
  image: 'https://araverus.com/podcast-cover.png',
}

export const metadata: Metadata = {
  title: 'News | Araverus',
  description: 'Agentic AI-powered briefings that turn hours of news into minutes — uncover hidden connections across Tech, Markets, and Finance that others miss.',
  alternates: {
    types: {
      'application/rss+xml': '/podcast.xml',
    },
  },
}

export default function NewsLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <BriefingProvider>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(podcastSeriesJsonLd) }}
      />
      {children}
      {/* Standalone mini-player for article pages (full player passes its own visibility) */}
      <BriefingMiniPlayer />
    </BriefingProvider>
  )
}
