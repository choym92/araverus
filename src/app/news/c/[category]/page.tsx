import { Suspense } from 'react'
import { notFound } from 'next/navigation'
import NewsShell from '../../_components/NewsShell'
import NewsContent from '../../_components/NewsContent'
import NewsContentSkeleton from '../../_components/NewsContentSkeleton'
import { getNewsData, getStoriesData, CATEGORY_SLUG_MAP, CATEGORY_SLUGS } from '../../_lib/data'
import type { Metadata } from 'next'

export const revalidate = 86400

export function generateStaticParams() {
  return CATEGORY_SLUGS.map((category) => ({ category }))
}

const CATEGORY_META: Record<string, { title: string; description: string }> = {
  tech: {
    title: 'Tech News Briefing — AI, Software & Hardware',
    description: 'AI-curated tech news covering artificial intelligence, software development, hardware, and emerging technology trends.',
  },
  markets: {
    title: 'Markets News Briefing — Stocks, Crypto & Finance',
    description: 'AI-curated markets news covering stocks, cryptocurrency, financial markets, and investment trends.',
  },
  economy: {
    title: 'Economy News Briefing — Macro, Policy & Trade',
    description: 'AI-curated economy news covering macroeconomics, fiscal policy, trade, and global economic trends.',
  },
  world: {
    title: 'World News Briefing — Global Affairs & Geopolitics',
    description: 'AI-curated world news covering international relations, geopolitics, and global events.',
  },
  politics: {
    title: 'Politics News Briefing — Policy, Elections & Government',
    description: 'AI-curated politics news covering government policy, elections, and political developments.',
  },
}

interface Props {
  params: Promise<{ category: string }>
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { category } = await params
  const meta = CATEGORY_META[category]
  if (!meta) return {}

  const canonical = `https://chopaul.com/news/c/${category}`
  return {
    title: { absolute: meta.title },
    description: meta.description,
    alternates: { canonical },
    openGraph: {
      title: meta.title,
      description: meta.description,
      url: canonical,
      type: 'website',
      images: [{ url: 'https://chopaul.com/og-news-default.png', width: 1200, height: 630 }],
    },
    twitter: {
      card: 'summary_large_image',
      title: meta.title,
      description: meta.description,
      images: ['https://chopaul.com/og-news-default.png'],
    },
  }
}

export default async function CategoryNewsPage({ params }: Props) {
  const { category } = await params
  const feedName = CATEGORY_SLUG_MAP[category]
  if (!feedName) notFound()

  const [data, storiesData] = await Promise.all([
    getNewsData(feedName),
    getStoriesData(feedName),
  ])

  return (
    <NewsShell>
      <Suspense fallback={<NewsContentSkeleton />}>
        <NewsContent
          items={data.sortedItems}
          briefingPlayerData={data.briefingPlayerData}
          threadTimelines={data.threadTimelines}
          threadMeta={data.threadMeta}
          allKeywords={data.allKeywords}
          allSubcategories={data.allSubcategories}
          serverCategory={feedName}
          parentThreadGroups={storiesData}
        />
      </Suspense>
    </NewsShell>
  )
}
