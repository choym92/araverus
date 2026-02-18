import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'News | Paul Cho',
  description: 'Daily curated finance news and audio briefings from trusted sources.',
}

export default function NewsLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return <>{children}</>
}
