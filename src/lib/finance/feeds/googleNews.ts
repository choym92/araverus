// src/lib/finance/feeds/googleNews.ts
// Google News RSS Feed Fetcher
// Created: 2025-01-05
//
// Fetches news from Google News RSS feeds for monitored tickers.
// These are Tier B/C sources - need URL resolution to get canonical URLs.
//
// IMPORTANT: Google News URLs are redirects. The actual source URL must be
// resolved in a separate step (see resolver.ts). Items are saved with
// resolve_status='pending' until resolved.

import { XMLParser } from 'fast-xml-parser';
import { SupabaseClient } from '@supabase/supabase-js';
import { createHash } from 'crypto';
import {
  buildGoogleNewsUrl,
  fetchWithRetry,
  GOOGLE_NEWS_QUERIES,
  RATE_LIMITS,
} from '../config';
import {
  insertRawFeedItem,
} from '../db';
import type { CreateRawFeedItemInput } from '../types';

// ============================================================
// Types
// ============================================================

export interface GoogleNewsItem {
  title: string;
  link: string; // This is the Google redirect URL
  pubDate: string;
  description: string;
  source: string; // Source name from RSS
}

export interface GoogleNewsFetchResult {
  ticker: string;
  query: string;
  itemsFetched: number;
  itemsInserted: number;
  itemsSkipped: number;
  errors: string[];
}

// ============================================================
// XML Parsing
// ============================================================

const xmlParser = new XMLParser({
  ignoreAttributes: false,
  attributeNamePrefix: '@_',
  textNodeName: '#text',
  parseAttributeValue: true,
});

/**
 * Parse Google News RSS feed XML into structured items.
 *
 * Google News RSS structure:
 * <rss>
 *   <channel>
 *     <item>
 *       <title>NVIDIA stock surges on AI demand</title>
 *       <link>https://news.google.com/rss/articles/CBMi...</link>
 *       <pubDate>Sun, 05 Jan 2025 10:30:00 GMT</pubDate>
 *       <description>NVIDIA reported strong earnings...</description>
 *       <source url="https://reuters.com">Reuters</source>
 *     </item>
 *   </channel>
 * </rss>
 */
export function parseGoogleNewsRss(xml: string): GoogleNewsItem[] {
  const parsed = xmlParser.parse(xml);

  // Handle empty or invalid feed
  if (!parsed?.rss?.channel?.item) {
    return [];
  }

  // Normalize to array (single item comes as object, not array)
  const items = Array.isArray(parsed.rss.channel.item)
    ? parsed.rss.channel.item
    : [parsed.rss.channel.item];

  return items.map((item: Record<string, unknown>) => {
    const title = String(item.title || '');
    const link = String(item.link || '');
    const pubDate = String(item.pubDate || '');
    const description = extractDescription(item.description);
    const source = extractSource(item.source);

    return {
      title,
      link,
      pubDate,
      description,
      source,
    };
  });
}

/**
 * Extract description text from RSS description field.
 * Can be a string or an object with #text property.
 */
function extractDescription(desc: unknown): string {
  if (typeof desc === 'string') {
    // Strip HTML tags for clean text
    return desc.replace(/<[^>]*>/g, '').trim();
  }
  if (desc && typeof desc === 'object') {
    const descObj = desc as Record<string, unknown>;
    return String(descObj['#text'] || '').replace(/<[^>]*>/g, '').trim();
  }
  return '';
}

/**
 * Extract source name from RSS source field.
 * Can be a string or an object with #text property.
 */
function extractSource(source: unknown): string {
  if (typeof source === 'string') {
    return source;
  }
  if (source && typeof source === 'object') {
    const sourceObj = source as Record<string, unknown>;
    return String(sourceObj['#text'] || '');
  }
  return '';
}

/**
 * Generate URL hash for deduplication.
 * Uses SHA-256 hash of the URL.
 */
function generateUrlHash(url: string): string {
  return createHash('sha256').update(url).digest('hex');
}

/**
 * Parse RFC 2822 date string to ISO format.
 * Input: "Sun, 05 Jan 2025 10:30:00 GMT"
 * Output: "2025-01-05T10:30:00.000Z"
 */
function parseRfc2822Date(dateStr: string): string | null {
  try {
    const date = new Date(dateStr);
    if (isNaN(date.getTime())) {
      return null;
    }
    return date.toISOString();
  } catch {
    return null;
  }
}

/**
 * Determine tier based on source name.
 * This is a rough estimate - will be refined after URL resolution.
 */
function determineTier(source: string): 'A' | 'B' | 'C' {
  const tierA = ['Reuters', 'Bloomberg', 'WSJ', 'Wall Street Journal', 'CNBC', 'Financial Times'];
  const tierB = ['Yahoo Finance', 'MarketWatch', 'Seeking Alpha', 'Barron\'s', 'Investor\'s Business Daily'];

  const sourceLower = source.toLowerCase();

  if (tierA.some(s => sourceLower.includes(s.toLowerCase()))) {
    return 'A';
  }
  if (tierB.some(s => sourceLower.includes(s.toLowerCase()))) {
    return 'B';
  }
  return 'C';
}

// ============================================================
// Main Fetch Function
// ============================================================

/**
 * Fetch Google News for a given ticker and query.
 *
 * @param supabase - Supabase client
 * @param ticker - Stock ticker symbol (e.g., "NVDA")
 * @param queryIndex - Index into GOOGLE_NEWS_QUERIES[ticker] array
 * @returns Fetch result with counts and errors
 */
export async function fetchGoogleNews(
  supabase: SupabaseClient,
  ticker: string,
  queryIndex: number = 0
): Promise<GoogleNewsFetchResult> {
  const queries = GOOGLE_NEWS_QUERIES[ticker];

  if (!queries || queryIndex >= queries.length) {
    return {
      ticker,
      query: '',
      itemsFetched: 0,
      itemsInserted: 0,
      itemsSkipped: 0,
      errors: [`No query found for ticker ${ticker} at index ${queryIndex}`],
    };
  }

  const query = queries[queryIndex];
  const feedUrl = buildGoogleNewsUrl(query);

  const result: GoogleNewsFetchResult = {
    ticker,
    query,
    itemsFetched: 0,
    itemsInserted: 0,
    itemsSkipped: 0,
    errors: [],
  };

  try {
    const response = await fetchWithRetry(feedUrl);

    if (!response.ok) {
      result.errors.push(`HTTP ${response.status}: ${response.statusText}`);
      return result;
    }

    const xml = await response.text();
    const items = parseGoogleNewsRss(xml);
    result.itemsFetched = items.length;

    // Process each item
    for (const item of items) {
      try {
        const inserted = await insertGoogleNewsItem(supabase, ticker, item);
        if (inserted) {
          result.itemsInserted++;
        } else {
          result.itemsSkipped++; // Duplicate
        }
      } catch (err) {
        result.errors.push(`Failed to insert "${item.title.slice(0, 50)}...": ${err}`);
      }
    }
  } catch (err) {
    const errorMessage = err instanceof Error ? err.message : String(err);
    result.errors.push(`Fetch failed: ${errorMessage}`);
  }

  return result;
}

/**
 * Insert a Google News item into raw_feed_items table.
 * Returns true if inserted, false if skipped (duplicate).
 *
 * IMPORTANT: Items are saved with resolve_status='pending' because
 * the link is a Google redirect URL, not the actual article URL.
 */
async function insertGoogleNewsItem(
  supabase: SupabaseClient,
  ticker: string,
  item: GoogleNewsItem
): Promise<boolean> {
  // Hash the Google redirect URL for deduplication
  const urlHash = generateUrlHash(item.link);
  const tier = determineTier(item.source);

  const dbItem: CreateRawFeedItemInput = {
    feed_source_id: null,
    source_name: item.source || 'Google News',
    tier,
    ticker,
    published_at: parseRfc2822Date(item.pubDate),
    title: item.title,
    summary: item.description || null,
    url: item.link, // Google redirect URL
    canonical_url: null, // Will be set after resolution
    url_hash: urlHash,
    canonical_url_hash: null, // Will be set after resolution
    google_redirect_url: item.link,
    resolve_status: 'pending', // Needs URL resolution
    resolve_error: null,
    external_id: null,
    source_domain: null, // Will be set after resolution
    filing_type: null,
    accession_no: null,
    content_type: 'news',
  };

  const result = await insertRawFeedItem(supabase, dbItem);
  return result !== null;
}

/**
 * Fetch Google News for all queries of a given ticker.
 *
 * @param supabase - Supabase client
 * @param ticker - Stock ticker symbol
 * @returns Combined results for all queries
 */
export async function fetchAllGoogleNewsForTicker(
  supabase: SupabaseClient,
  ticker: string
): Promise<GoogleNewsFetchResult[]> {
  const queries = GOOGLE_NEWS_QUERIES[ticker];

  if (!queries) {
    return [{
      ticker,
      query: '',
      itemsFetched: 0,
      itemsInserted: 0,
      itemsSkipped: 0,
      errors: [`No queries configured for ticker ${ticker}`],
    }];
  }

  const results: GoogleNewsFetchResult[] = [];

  for (let i = 0; i < queries.length; i++) {
    const result = await fetchGoogleNews(supabase, ticker, i);
    results.push(result);

    // Rate limit: Be conservative with Google
    await sleep(1000 / RATE_LIMITS.GOOGLE_NEWS);
  }

  return results;
}

/**
 * Fetch Google News for multiple tickers.
 *
 * @param supabase - Supabase client
 * @param tickers - Array of ticker symbols
 * @returns Combined results for all tickers
 */
export async function fetchAllGoogleNews(
  supabase: SupabaseClient,
  tickers: string[]
): Promise<GoogleNewsFetchResult[]> {
  const allResults: GoogleNewsFetchResult[] = [];

  for (const ticker of tickers) {
    const results = await fetchAllGoogleNewsForTicker(supabase, ticker);
    allResults.push(...results);
  }

  return allResults;
}

// ============================================================
// Utilities
// ============================================================

function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// ============================================================
// Exports for Testing
// ============================================================

export {
  extractDescription,
  extractSource,
  generateUrlHash,
  parseRfc2822Date,
  determineTier,
};
