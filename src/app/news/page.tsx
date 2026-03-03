import { Suspense } from 'react'
import NewsShell from './_components/NewsShell'
import NewsContent from './_components/NewsContent'
import NewsContentSkeleton from './_components/NewsContentSkeleton'
import { getNewsData, getStoriesData } from './_lib/data'
import type { Metadata } from 'next'

export const revalidate = 86400 // 24h ISR safety net; on-demand revalidation is primary

export async function generateMetadata(): Promise<Metadata> {
  const titleText = 'AI News Briefing — Tech, Markets & Finance'
  const title = { absolute: titleText }
  const canonical = 'https://chopaul.com/news'

  const description = 'Agentic AI pipeline that threads related news stories, surfaces trends, and delivers daily briefings across Tech, Markets, and Finance.'

  return {
    title,
    description,
    alternates: { canonical },
    openGraph: {
      title: titleText,
      description,
      url: canonical,
      type: 'website',
      images: [{ url: 'https://chopaul.com/og-news-default.png', width: 1200, height: 630 }],
    },
    twitter: {
      card: 'summary_large_image',
      title: titleText,
      description,
      images: ['https://chopaul.com/og-news-default.png'],
    },
  }
}

export default async function NewsPage() {
  const [data, storiesData] = await Promise.all([
    getNewsData(undefined),
    getStoriesData(undefined),
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
          parentThreadGroups={storiesData}
        />
      </Suspense>
    </NewsShell>
  )
}
