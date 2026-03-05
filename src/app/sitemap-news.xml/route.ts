import { NextResponse } from 'next/server';
import { unstable_cache } from 'next/cache';
import { createServiceClient } from '@/lib/supabase-server';
import { NewsService } from '@/lib/news-service';

function escapeXml(s: string) {
  return s.replace(/[<>&'"]/g, c => ({'<':'&lt;','>':'&gt;','&':'&amp;',"'":'&apos;','"':'&quot;'}[c]!));
}

const getNewsSitemapData = unstable_cache(
  async () => {
    const SITE = process.env.NEXT_PUBLIC_SITE_URL || 'https://araverus.com';

    const supabase = createServiceClient();
    const service = new NewsService(supabase);

    // Google News Sitemap: only articles from last 48 hours
    const since = new Date(Date.now() - 48 * 60 * 60 * 1000).toISOString();
    const newsItems = await service.getNewsItems({ limit: 1000, since }).catch(() => []);

    const urls = newsItems
      .filter(i => i.slug)
      .map(i => {
        const loc = escapeXml(`${SITE}/news/${i.slug}`);
        const pubDate = i.published_at
          ? new Date(i.published_at).toISOString()
          : new Date().toISOString();
        const title = escapeXml(i.title || '');
        return `
  <url>
    <loc>${loc}</loc>
    <news:news>
      <news:publication>
        <news:name>Araverus</news:name>
        <news:language>en</news:language>
      </news:publication>
      <news:publication_date>${pubDate}</news:publication_date>
      <news:title>${title}</news:title>
    </news:news>
  </url>`;
      }).join('');

    return `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">
${urls}
</urlset>`;
  },
  ['news-sitemap'],
  { revalidate: 3600, tags: ['news'] }
);

export async function GET() {
  const xml = await getNewsSitemapData();

  return new NextResponse(xml.trim(), {
    headers: {
      'Content-Type': 'application/xml; charset=utf-8',
      'Cache-Control': 's-maxage=3600, stale-while-revalidate',
    },
  });
}
