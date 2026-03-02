import type { MetadataRoute } from 'next';
import { createServiceClient } from '@/lib/supabase-server';
import { NewsService } from '@/lib/news-service';

const BASE_URL =
  process.env.NEXT_PUBLIC_SITE_URL ||
  (process.env.VERCEL_URL ? `https://${process.env.VERCEL_URL}` : 'https://localhost:3000');

const NEWS_CATEGORIES = ['TECH', 'BUSINESS_MARKETS', 'ECONOMY', 'WORLD', 'POLITICS'];

export const revalidate = 3600;

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const supabase = createServiceClient()
  const service = new NewsService(supabase)

  const newsItems = await service.getNewsItems({ limit: 100 }).catch(() => []);

  const latestNewsDate = (newsItems as { published_at?: string }[]).length > 0
    ? new Date((newsItems as { published_at?: string }[])[0].published_at ?? new Date())
    : new Date()

  const staticRoutes: MetadataRoute.Sitemap = [
    { url: BASE_URL, lastModified: new Date(), changeFrequency: 'weekly', priority: 1 },
    { url: `${BASE_URL}/news`, lastModified: latestNewsDate, changeFrequency: 'daily', priority: 1 },
  ];

  const categoryRoutes: MetadataRoute.Sitemap = NEWS_CATEGORIES.map((cat) => ({
    url: `${BASE_URL}/news?category=${cat}`,
    lastModified: latestNewsDate,
    changeFrequency: 'daily' as const,
    priority: 0.9,
  }));

  const newsRoutes: MetadataRoute.Sitemap = (newsItems as { slug?: string; published_at?: string }[])
    .filter((item) => item.slug)
    .map((item) => ({
      url: `${BASE_URL}/news/${item.slug}`,
      lastModified: item.published_at ? new Date(item.published_at) : new Date(),
      changeFrequency: 'weekly' as const,
      priority: 0.8,
    }));

  return [...staticRoutes, ...categoryRoutes, ...newsRoutes];
}
