import type { NextConfig } from "next";

const cspHeader = `
  default-src 'self';
  script-src 'self' 'unsafe-eval' 'unsafe-inline';
  style-src 'self' 'unsafe-inline';
  img-src 'self' https: blob: data:;
  font-src 'self';
  connect-src 'self' https://*.supabase.co wss://*.supabase.co;
  media-src 'self' https://*.supabase.co;
  object-src 'none';
  base-uri 'self';
  form-action 'self';
  frame-ancestors 'none';
  upgrade-insecure-requests;
`.replace(/\n/g, '');

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      { source: '/sitemap-news.xml', destination: '/api/sitemap-news' },
    ]
  },
  async redirects() {
    return [
      { source: '/news', has: [{ type: 'query', key: 'category', value: 'TECH' }], destination: '/news/c/tech', permanent: true },
      { source: '/news', has: [{ type: 'query', key: 'category', value: 'BUSINESS_MARKETS' }], destination: '/news/c/markets', permanent: true },
      { source: '/news', has: [{ type: 'query', key: 'category', value: 'ECONOMY' }], destination: '/news/c/economy', permanent: true },
      { source: '/news', has: [{ type: 'query', key: 'category', value: 'WORLD' }], destination: '/news/c/world', permanent: true },
      { source: '/news', has: [{ type: 'query', key: 'category', value: 'POLITICS' }], destination: '/news/c/politics', permanent: true },
    ]
  },
  async headers() {
    return [
      {
        source: '/(.*)',
        headers: [
          { key: 'X-Frame-Options', value: 'DENY' },
          { key: 'X-Content-Type-Options', value: 'nosniff' },
          {
            key: 'Strict-Transport-Security',
            value: 'max-age=63072000; includeSubDomains; preload',
          },
          {
            key: 'Referrer-Policy',
            value: 'strict-origin-when-cross-origin',
          },
          {
            key: 'Permissions-Policy',
            value: 'camera=(), microphone=(), geolocation=()',
          },
          {
            // Report-Only first — switch to Content-Security-Policy after monitoring
            key: 'Content-Security-Policy-Report-Only',
            value: cspHeader,
          },
        ],
      },
    ];
  },
  images: {
    remotePatterns: [
      // TODO: Replace wildcards with image proxy API to prevent open proxy abuse
      {
        protocol: 'https',
        hostname: '**',
      },
      {
        protocol: 'http',
        hostname: '**',
      },
      {
        protocol: 'https',
        hostname: 'lh3.googleusercontent.com',
      },
      {
        protocol: 'https',
        hostname: 'obqjrbwguutgtsjaivrh.supabase.co',
      },
    ],
  },
};

export default nextConfig;
