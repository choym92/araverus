import { NextResponse } from 'next/server';
import { getAllPosts } from '@/lib/mdx';

function escapeXml(s: string) {
  return s.replace(/[<>&'"]/g, c => ({'<':'&lt;','>':'&gt;','&':'&amp;',"'":'&apos;','"':'&quot;'}[c]!));
}

export async function GET() {
  const SITE = process.env.NEXT_PUBLIC_SITE_URL || 'http://localhost:3000';
  const posts = await getAllPosts(); // non-draft posts, sorted desc by date
  const items = posts.slice(0, 50).map(p => {
    const link = `${SITE}/blog/${p.slug}`;
    const pubDate = new Date(p.frontmatter.date).toUTCString();
    const title = escapeXml(p.frontmatter.title || p.slug);
    const description = escapeXml(p.frontmatter.excerpt || (p.frontmatter.tags || []).join(', '));
    return `
      <item>
        <title>${title}</title>
        <link>${link}</link>
        <guid>${link}</guid>
        <pubDate>${pubDate}</pubDate>
        <description>${description}</description>
      </item>`;
  }).join('');

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
  <rss version="2.0">
    <channel>
      <title>${escapeXml('chopaul.com blog')}</title>
      <link>${SITE}</link>
      <description>${escapeXml('Personal blog by Paul Cho')}</description>
      <language>ko</language>
      <lastBuildDate>${new Date().toUTCString()}</lastBuildDate>
      ${items}
    </channel>
  </rss>`;

  return new NextResponse(xml.trim(), {
    headers: {
      'Content-Type': 'application/rss+xml; charset=utf-8',
      'Cache-Control': 's-maxage=86400, stale-while-revalidate',
    },
  });
}