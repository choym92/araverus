// src/lib/finance/feeds/sec.ts
// SEC EDGAR Atom Feed Fetcher
// Created: 2025-01-05
//
// Fetches official SEC filings (8-K, 10-K, 10-Q, Form 4) for monitored tickers.
// These are Tier A sources - the most authoritative financial information.

import { XMLParser } from 'fast-xml-parser';
import { SupabaseClient } from '@supabase/supabase-js';
import { createHash } from 'crypto';
import {
  buildSecFeedUrl,
  fetchWithRetry,
  SEC_CONFIG,
  FETCH_CONFIG,
} from '../config';
import {
  getFeedSourcesByTicker,
  updateFeedSourceAfterFetch,
  insertRawFeedItem,
} from '../db';
import type { FeedSource, CreateRawFeedItemInput } from '../types';

// ============================================================
// Types
// ============================================================

export interface SecFeedEntry {
  title: string;
  link: string;
  summary: string;
  updated: string;
  // SEC-specific fields extracted from the entry
  accessionNo: string;
  filingType: string;
  filedDate: string;
}

export interface SecFetchResult {
  ticker: string;
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
 * Parse SEC EDGAR Atom feed XML into structured entries.
 *
 * SEC Atom feed structure:
 * <feed>
 *   <entry>
 *     <title>8-K - NVIDIA Corporation (0001045810)</title>
 *     <link href="https://www.sec.gov/Archives/edgar/data/..." />
 *     <summary>...</summary>
 *     <updated>2025-01-05T16:30:00-05:00</updated>
 *     <id>urn:tag:sec.gov,2008:accession-number=0001045810-25-000042</id>
 *   </entry>
 * </feed>
 */
export function parseSecAtomFeed(xml: string): SecFeedEntry[] {
  const parsed = xmlParser.parse(xml);

  // Handle empty feed
  if (!parsed?.feed?.entry) {
    return [];
  }

  // Normalize to array (single entry comes as object, not array)
  const entries = Array.isArray(parsed.feed.entry)
    ? parsed.feed.entry
    : [parsed.feed.entry];

  return entries.map((entry: Record<string, unknown>) => {
    const title = String(entry.title || '');
    const link = extractLink(entry.link);
    const summary = String(entry.summary || '');
    const updated = String(entry.updated || '');
    const id = String(entry.id || '');

    // Extract accession number from the id field
    // Format: urn:tag:sec.gov,2008:accession-number=0001045810-25-000042
    const accessionNo = extractAccessionNo(id);

    // Extract filing type from title
    // Format: "8-K - NVIDIA Corporation (0001045810)"
    const filingType = extractFilingType(title);

    // Filed date is the updated timestamp
    const filedDate = updated;

    return {
      title,
      link,
      summary,
      updated,
      accessionNo,
      filingType,
      filedDate,
    };
  });
}

/**
 * Extract link href from Atom link element.
 * Can be either { @_href: "..." } or just a string.
 */
function extractLink(link: unknown): string {
  if (typeof link === 'string') {
    return link;
  }
  if (link && typeof link === 'object') {
    const linkObj = link as Record<string, unknown>;
    // Handle single link or array of links
    if (Array.isArray(linkObj)) {
      // Find the alternate link or first link
      const altLink = linkObj.find((l: Record<string, unknown>) => l['@_rel'] === 'alternate');
      return String((altLink || linkObj[0])?.['@_href'] || '');
    }
    return String(linkObj['@_href'] || '');
  }
  return '';
}

/**
 * Extract accession number from SEC entry ID.
 * Input: "urn:tag:sec.gov,2008:accession-number=0001045810-25-000042"
 * Output: "0001045810-25-000042"
 */
function extractAccessionNo(id: string): string {
  const match = id.match(/accession-number=([0-9-]+)/);
  return match ? match[1] : '';
}

/**
 * Extract filing type from SEC entry title.
 * Input: "8-K - NVIDIA Corporation (0001045810)"
 * Output: "8-K"
 */
function extractFilingType(title: string): string {
  // Filing type is at the start, before the " - "
  const match = title.match(/^([A-Z0-9-/]+(?:\/A)?)\s*-/);
  return match ? match[1].trim() : '';
}

/**
 * Generate URL hash for deduplication.
 * Uses SHA-256 hash of the URL.
 */
function generateUrlHash(url: string): string {
  return createHash('sha256').update(url).digest('hex');
}

// ============================================================
// Main Fetch Function
// ============================================================

/**
 * Fetch SEC filings for a given ticker.
 *
 * @param supabase - Supabase client
 * @param ticker - Stock ticker symbol (e.g., "NVDA")
 * @param cik - SEC CIK number (e.g., "0001045810")
 * @param feedSource - Optional feed source record for ETag tracking
 * @returns Fetch result with counts and errors
 */
export async function fetchSecFilings(
  supabase: SupabaseClient,
  ticker: string,
  cik: string,
  feedSource?: FeedSource
): Promise<SecFetchResult> {
  const result: SecFetchResult = {
    ticker,
    itemsFetched: 0,
    itemsInserted: 0,
    itemsSkipped: 0,
    errors: [],
  };

  try {
    // Fetch for each filing type configured
    for (const filingType of SEC_CONFIG.filingTypes) {
      const feedUrl = buildSecFeedUrl(cik, filingType);

      // Build request headers with conditional fetch support
      const headers: Record<string, string> = {
        ...FETCH_CONFIG.headers,
      };

      // Add ETag/Last-Modified for conditional request if available
      if (feedSource?.etag) {
        headers['If-None-Match'] = feedSource.etag;
      }
      if (feedSource?.last_modified) {
        headers['If-Modified-Since'] = feedSource.last_modified;
      }

      const response = await fetchWithRetry(feedUrl, { headers });

      // Handle 304 Not Modified
      if (response.status === 304) {
        continue; // No new data, skip to next filing type
      }

      if (!response.ok) {
        result.errors.push(`HTTP ${response.status} for ${filingType}: ${response.statusText}`);
        continue;
      }

      const xml = await response.text();
      const entries = parseSecAtomFeed(xml);
      result.itemsFetched += entries.length;

      // Process each entry
      for (const entry of entries) {
        try {
          const inserted = await insertSecEntry(supabase, ticker, entry, feedSource?.id);
          if (inserted) {
            result.itemsInserted++;
          } else {
            result.itemsSkipped++; // Duplicate
          }
        } catch (err) {
          result.errors.push(`Failed to insert ${entry.accessionNo}: ${err}`);
        }
      }

      // Update feed source with new ETag/Last-Modified
      if (feedSource) {
        await updateFeedSourceAfterFetch(supabase, feedSource.id, {
          etag: response.headers.get('etag'),
          last_modified: response.headers.get('last-modified'),
          last_error: null,
          error_count: 0,
        });
      }
    }
  } catch (err) {
    const errorMessage = err instanceof Error ? err.message : String(err);
    result.errors.push(`Fetch failed: ${errorMessage}`);

    // Update feed source with error
    if (feedSource) {
      await updateFeedSourceAfterFetch(supabase, feedSource.id, {
        last_error: errorMessage,
        error_count: (feedSource.error_count || 0) + 1,
      });
    }
  }

  return result;
}

/**
 * Insert a SEC entry into raw_feed_items table.
 * Returns true if inserted, false if skipped (duplicate).
 */
async function insertSecEntry(
  supabase: SupabaseClient,
  ticker: string,
  entry: SecFeedEntry,
  feedSourceId?: string
): Promise<boolean> {
  const urlHash = generateUrlHash(entry.link);

  const item: CreateRawFeedItemInput = {
    feed_source_id: feedSourceId || null,
    source_name: 'SEC EDGAR',
    tier: 'A', // SEC is always Tier A
    ticker,
    published_at: entry.filedDate || null,
    title: entry.title,
    summary: entry.summary || null,
    url: entry.link,
    canonical_url: entry.link, // SEC URLs are already canonical
    url_hash: urlHash,
    canonical_url_hash: urlHash,
    google_redirect_url: null,
    resolve_status: 'resolved', // SEC URLs don't need resolution
    resolve_error: null,
    external_id: entry.accessionNo || null,
    source_domain: 'sec.gov',
    filing_type: entry.filingType || null,
    accession_no: entry.accessionNo || null,
    content_type: 'filing',
  };

  const result = await insertRawFeedItem(supabase, item);
  return result !== null;
}

/**
 * Fetch SEC filings for all active tickers.
 *
 * @param supabase - Supabase client
 * @param tickers - Array of { ticker, cik } objects
 * @returns Combined results for all tickers
 */
export async function fetchAllSecFilings(
  supabase: SupabaseClient,
  tickers: Array<{ ticker: string; cik: string }>
): Promise<SecFetchResult[]> {
  const results: SecFetchResult[] = [];

  for (const { ticker, cik } of tickers) {
    // Get feed source for this ticker (if exists)
    const feedSources = await getFeedSourcesByTicker(supabase, ticker);
    const secSource = feedSources.find(s => s.feed_type === 'SEC');

    const result = await fetchSecFilings(supabase, ticker, cik, secSource);
    results.push(result);

    // Rate limit: SEC allows ~10 req/sec, but be conservative
    await sleep(200); // 5 requests per second max
  }

  return results;
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
  extractAccessionNo,
  extractFilingType,
  extractLink,
  generateUrlHash,
};
