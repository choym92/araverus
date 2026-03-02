import { NextResponse } from 'next/server';
import { createServiceClient } from '@/lib/supabase-server';
import { NewsService } from '@/lib/news-service';

function escapeXml(s: string) {
  return s.replace(/[<>&'"]/g, c => ({'<':'&lt;','>':'&gt;','&':'&amp;',"'":'&apos;','"':'&quot;'}[c]!));
}

export async function GET() {
  const SITE = process.env.NEXT_PUBLIC_SITE_URL || 'https://chopaul.com';

  const supabase = createServiceClient()
  const service = new NewsService(supabase)

  const newsItems = await service.getNewsItems({ limit: 50 }).catch(() => []) as
    { slug?: string; title?: string; description?: string; published_at?: string; feed_name?: string }[]

  const latestDate = newsItems.length > 0 && newsItems[0].published_at
    ? new Date(newsItems[0].published_at).toUTCString()
    : new Date().toUTCString()

  const newsRssItems = newsItems
    .filter(i => i.slug)
    .map(i => {
      const link = `${SITE}/news/${i.slug}`;
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

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
  <rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
    <channel>
      <title>${escapeXml('chopaul.com — AI-Powered News & Finance Insights')}</title>
      <link>${SITE}</link>
      <description>${escapeXml('Agentic AI pipeline that threads related news stories, surfaces trends, and delivers daily briefings across Tech, Markets, and Finance.')}</description>
      <language>en</language>
      <copyright>Copyright ${new Date().getFullYear()} chopaul.com</copyright>
      <ttl>60</ttl>
      <lastBuildDate>${latestDate}</lastBuildDate>
      <atom:link href="${SITE}/rss.xml" rel="self" type="application/rss+xml" />
      <image>
        <url>${SITE}/logo-publisher.png</url>
        <title>${escapeXml('chopaul.com')}</title>
        <link>${SITE}</link>
      </image>
      ${newsRssItems}
    </channel>
  </rss>`;

  return new NextResponse(xml.trim(), {
    headers: {
      'Content-Type': 'application/rss+xml; charset=utf-8',
      'Cache-Control': 's-maxage=3600, stale-while-revalidate',
    },
  });
}
