import { NextResponse } from 'next/server';
import { unstable_cache } from 'next/cache';
import { createServiceClient } from '@/lib/supabase-server';
import { NewsService } from '@/lib/news-service';

function escapeXml(s: string) {
  return s.replace(/[<>&'"]/g, c => ({'<':'&lt;','>':'&gt;','&':'&amp;',"'":'&apos;','"':'&quot;'}[c]!));
}

const getPodcastData = unstable_cache(
  async () => {
    const SITE = process.env.NEXT_PUBLIC_SITE_URL || 'https://chopaul.com';

    const supabase = createServiceClient();
    const service = new NewsService(supabase);
    const { en } = await service.getLatestBriefings();

    let itemXml = '';
    if (en) {
      const pubDate = new Date(en.date + 'T06:00:00Z').toUTCString();
      const title = escapeXml(`AI News Briefing — ${new Date(en.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}`);
      const audioUrl = escapeXml(en.audio_url || `${SITE}/audio/chirp3-en-pro-friendly-${en.date}.wav`);
      const duration = en.audio_duration ? Math.round(en.audio_duration) : 660;

      itemXml = `
    <item>
      <title>${title}</title>
      <enclosure url="${audioUrl}" length="0" type="audio/mpeg"/>
      <guid isPermaLink="false">briefing-en-${en.date}</guid>
      <pubDate>${pubDate}</pubDate>
      <itunes:duration>${duration}</itunes:duration>
      <itunes:explicit>false</itunes:explicit>
      <itunes:episodeType>full</itunes:episodeType>
      <description>${escapeXml('AI-curated daily briefing covering tech, markets, and finance.')}</description>
    </item>`;
    }

    return `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
  xmlns:itunes="http://www.itunes.apple.com/dtds/podcast-1.0.dtd"
  xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>${escapeXml('AI News Briefing — chopaul.com')}</title>
    <link>${SITE}/news</link>
    <language>en</language>
    <copyright>Copyright ${new Date().getFullYear()} chopaul.com</copyright>
    <description>${escapeXml('Agentic AI pipeline that threads related news stories, surfaces trends, and delivers daily audio briefings across Tech, Markets, and Finance.')}</description>
    <itunes:author>chopaul.com</itunes:author>
    <itunes:summary>${escapeXml('Daily AI-curated audio briefing covering tech, markets, and finance news.')}</itunes:summary>
    <itunes:category text="News">
      <itunes:category text="Daily News"/>
    </itunes:category>
    <itunes:image href="${SITE}/podcast-cover.png"/>
    <itunes:explicit>false</itunes:explicit>
    <itunes:type>episodic</itunes:type>
    <atom:link href="${SITE}/podcast.xml" rel="self" type="application/rss+xml"/>
    <image>
      <url>${SITE}/podcast-cover.png</url>
      <title>${escapeXml('AI News Briefing — chopaul.com')}</title>
      <link>${SITE}/news</link>
    </image>
    ${itemXml}
  </channel>
</rss>`;
  },
  ['podcast-feed'],
  { revalidate: 86400, tags: ['news'] }
);

export async function GET() {
  const xml = await getPodcastData();

  return new NextResponse(xml.trim(), {
    headers: {
      'Content-Type': 'application/rss+xml; charset=utf-8',
      'Cache-Control': 's-maxage=86400, stale-while-revalidate',
    },
  });
}
