# Command: Ensure RSS
# Usage: /ensure-rss
# Goal: Provide /rss.xml via App Router, using MDX post metadata.

## Notes
- Uses getAllPosts() from src/lib/mdx.ts.
- Site URL: process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000".
- Cache: 1일 (s-maxage=86400), SWR.

## Steps
1) CREATE (or OVERWRITE): src/app/rss.xml/route.ts with the code below.
2) ADD a feed link to the site head:
   - If src/app/layout.tsx uses export const metadata, add:
     ```ts
     alternates: { types: { 'application/rss+xml': '/rss.xml' } },
     ```
   - Else, inject `<link rel="alternate" type="application/rss+xml" href="/rss.xml" />` inside <head>.
3) Validate:
   - Build passes.
   - Print first 6 lines of GET /rss.xml (local mock by assembling the same xml) as a smoke check.

## File: src/app/rss.xml/route.ts
```ts
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
```

## Output Contract
- List modified/created files.
- Show head-link injection result (one line).
- Remind to set NEXT_PUBLIC_SITE_URL in .env.local.

## Rollback
```bash
git restore -SW src/app/rss.xml/ src/app/layout.tsx
```