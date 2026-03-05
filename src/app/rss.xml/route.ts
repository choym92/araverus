import { NextResponse } from 'next/server';
import { unstable_cache } from 'next/cache';
import { createServiceClient } from '@/lib/supabase-server';
import { NewsService } from '@/lib/news-service';

function escapeXml(s: string) {
  return s.replace(/[<>&'"]/g, c => ({'<':'&lt;','>':'&gt;','&':'&amp;',"'":'&apos;','"':'&quot;'}[c]!));
}

const getRssData = unstable_cache(
  async () => {
    const SITE = process.env.NEXT_PUBLIC_SITE_URL || 'https://araverus.com';

    const supabase = createServiceClient()
    const service = new NewsService(supabase)

    const newsItems = await service.getNewsItems({ limit: 500 }).catch(() => [])

    const latestDate = newsItems.length > 0 && newsItems[0].published_at
      ? new Date(newsItems[0].published_at).toUTCString()
      : new Date().toUTCString()

    const newsRssItems = newsItems
      .filter(i => i.slug)
      .map(i => {
        const link = escapeXml(`${SITE}/news/${i.slug}`);
        const pubDate = i.published_at ? new Date(i.published_at).toUTCString() : new Date().toUTCString();
        const title = escapeXml(i.title || '');
        const description = escapeXml(i.description || '');
        const category = escapeXml(i.feed_name || 'News');
        return `
      <item>
        <title>${title}</title>
        <link>${link}</link>
        <guid>${link}</guid>
        <pubDate>${pubDate}</pubDate>
        <description>${description}</description>
        <category>${category}</category>
      </item>`;
      }).join('');

    return `<?xml version="1.0" encoding="UTF-8"?>
  <rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
    <channel>
      <title>${escapeXml('Araverus — Financial Intelligence')}</title>
      <link>${SITE}</link>
      <description>${escapeXml('Agentic AI pipeline that threads related news stories, surfaces trends, and delivers daily briefings across Tech, Markets, and Finance.')}</description>
      <language>en</language>
      <copyright>Copyright ${new Date().getFullYear()} Araverus</copyright>
      <ttl>60</ttl>
      <lastBuildDate>${latestDate}</lastBuildDate>
      <atom:link href="${SITE}/rss.xml" rel="self" type="application/rss+xml" />
      <image>
        <url>${SITE}/logo-publisher.png</url>
        <title>${escapeXml('Araverus')}</title>
        <link>${SITE}</link>
      </image>
      ${newsRssItems}
    </channel>
  </rss>`;
  },
  ['rss-feed'],
  { revalidate: 86400, tags: ['news'] }
);

export async function GET() {
  const xml = await getRssData();

  return new NextResponse(xml.trim(), {
    headers: {
      'Content-Type': 'application/rss+xml; charset=utf-8',
      'Cache-Control': 's-maxage=86400, stale-while-revalidate',
    },
  });
}
