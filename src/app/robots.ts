import type { MetadataRoute } from 'next';

const BASE_URL =
  process.env.NEXT_PUBLIC_SITE_URL ||
  (process.env.VERCEL_URL ? `https://${process.env.VERCEL_URL}` : 'https://localhost:3000');

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: '*',
        allow: '/',
        disallow: ['/dashboard', '/admin'],
      },
      {
        userAgent: 'Googlebot-News',
        allow: '/news/',
      },
      // Block AI training crawlers to reduce bandwidth
      { userAgent: 'GPTBot', disallow: '/' },
      { userAgent: 'ChatGPT-User', disallow: '/' },
      { userAgent: 'CCBot', disallow: '/' },
      { userAgent: 'anthropic-ai', disallow: '/' },
      { userAgent: 'Claude-Web', disallow: '/' },
      { userAgent: 'Bytespider', disallow: '/' },
      { userAgent: 'FacebookBot', disallow: '/' },
    ],
    sitemap: `${BASE_URL}/sitemap.xml`,
  };
}
