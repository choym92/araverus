import type { Metadata } from 'next'
import { BriefingProvider } from './_components/BriefingContext'
import BriefingMiniPlayer from './_components/BriefingMiniPlayer'

const podcastSeriesJsonLd = {
  '@context': 'https://schema.org',
  '@type': 'PodcastSeries',
  name: 'AI News Briefing — chopaul.com',
  description: 'Daily AI-curated audio briefing covering tech, markets, and finance news.',
  url: 'https://chopaul.com/news',
  webFeed: 'https://chopaul.com/podcast.xml',
  author: { '@type': 'Person', name: 'Paul Cho' },
  image: 'https://chopaul.com/podcast-cover.png',
}

export const metadata: Metadata = {
  title: 'News | Paul Cho',
  description: 'Daily curated finance news and audio briefings from trusted sources.',
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
