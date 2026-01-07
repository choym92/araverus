// src/lib/finance/feeds/resolver.ts
// Google News URL Resolver - follows redirects to get canonical URLs
// Created: 2025-01-05
//
// Google News RSS returns redirect URLs (news.google.com/rss/articles/...).
// This module resolves them to get the actual article URLs.
//
// IMPORTANT: url_hash is fixed at insert time and NEVER changes.
// Only canonical_url_hash is set after resolution.

import { createHash } from 'crypto';
import { SupabaseClient } from '@supabase/supabase-js';
import {
  getPendingResolveItems,
  updateRawFeedItemResolved,
  updateRawFeedItemResolveFailed,
} from '../db';
import { FETCH_CONFIG, RATE_LIMITS } from '../config';
import type { RawFeedItem, ResolveResult } from '../types';

// ============================================================
// Types
// ============================================================

export interface ResolveItemResult {
  id: string;
  success: boolean;
  canonicalUrl?: string;
  sourceDomain?: string;
  error?: string;
}

// ============================================================
// URL Resolution
// ============================================================

/**
 * Decode a Google News URL to extract the actual article URL.
 *
 * Google News URLs encode the real URL in base64/protobuf format.
 * There are two formats:
 * 1. Old format: URL is directly in the base64 decoded content
 * 2. New format (2024+): Contains "AU_yqL" prefix, requires batchexecute API
 *
 * @param googleUrl - The Google News redirect URL
 * @returns The decoded canonical URL or null if needs API call
 */
export function decodeGoogleNewsUrl(googleUrl: string): string | null {
  try {
    const match = googleUrl.match(/\/articles\/([^/?]+)/);
    if (!match) return null;

    const encoded = match[1];
    const base64 = encoded.replace(/-/g, '+').replace(/_/g, '/');
    const decoded = Buffer.from(base64, 'base64');
    const str = decoded.toString('latin1');

    // Check for protobuf prefix markers
    const prefix = Buffer.from([0x08, 0x13, 0x22]).toString('latin1');
    let content = str;
    if (str.startsWith(prefix)) {
      content = str.substring(prefix.length);
    }

    // Remove known suffix if present
    const suffix = Buffer.from([0xd2, 0x01, 0x00]).toString('latin1');
    if (content.endsWith(suffix)) {
      content = content.substring(0, content.length - suffix.length);
    }

    // Parse length byte and extract inner content
    const bytes = Uint8Array.from(content, c => c.charCodeAt(0));
    const len = bytes[0];
    if (len >= 0x80) {
      content = content.substring(2, len + 2);
    } else {
      content = content.substring(1, len + 1);
    }

    // Check if this is the new format that needs batchexecute API
    if (content.startsWith('AU_yqL')) {
      return null; // Signal that we need to use batchexecute API
    }

    // Old format: look for URL directly
    const urlMatch = content.match(/https?:\/\/[^\s\x00-\x1f"<>]+/);
    if (urlMatch) {
      return urlMatch[0].replace(/[\x00-\x1f\x7f-\xff]+$/, '');
    }

    return null;
  } catch {
    return null;
  }
}

/**
 * Check if a Google News URL uses the new format requiring batchexecute API.
 */
export function needsBatchExecute(googleUrl: string): boolean {
  try {
    const match = googleUrl.match(/\/articles\/([^/?]+)/);
    if (!match) return false;

    const encoded = match[1];
    const base64 = encoded.replace(/-/g, '+').replace(/_/g, '/');
    const decoded = Buffer.from(base64, 'base64').toString('latin1');

    // Check for AU_yqL pattern after protobuf markers
    return decoded.includes('AU_yqL');
  } catch {
    return false;
  }
}

/**
 * Extract the article ID from a Google News URL.
 */
function extractArticleId(googleUrl: string): string | null {
  const match = googleUrl.match(/\/articles\/([^/?]+)/);
  return match ? match[1] : null;
}

/**
 * Decode Google News URL using the batchexecute API.
 * This works for the new format (2024+) with AU_yqL encoding.
 *
 * Two-step process:
 * 1. Fetch the article page to get signature and timestamp
 * 2. Call batchexecute with those parameters
 *
 * Based on: https://github.com/SSujitX/google-news-url-decoder
 */
async function fetchDecodedBatchExecute(articleId: string): Promise<string> {
  // Step 1: Fetch article page to get signature and timestamp
  const articleUrl = `https://news.google.com/articles/${articleId}`;

  const pageResponse = await fetch(articleUrl, {
    method: 'GET',
    headers: {
      'User-Agent': FETCH_CONFIG.headers['User-Agent'],
      'Accept': 'text/html,application/xhtml+xml',
    },
  });

  if (!pageResponse.ok) {
    throw new Error(`Failed to fetch article page: HTTP ${pageResponse.status}`);
  }

  const html = await pageResponse.text();

  // Extract signature (data-n-a-sg) and timestamp (data-n-a-ts)
  const sigMatch = html.match(/data-n-a-sg="([^"]+)"/);
  const tsMatch = html.match(/data-n-a-ts="([^"]+)"/);

  if (!sigMatch || !tsMatch) {
    throw new Error('Could not extract signature/timestamp from article page');
  }

  const signature = sigMatch[1];
  const timestamp = tsMatch[1];

  // Step 2: Call batchexecute with signature and timestamp
  const payload = JSON.stringify([
    [
      [
        'Fbv4je',
        JSON.stringify([
          'garturlreq',
          [
            ['X', 'X', ['X', 'X'], null, null, 1, 1, 'US:en', null, 1, null, null, null, null, null, 0, 1],
            'X',
            'X',
            1,
            [1, 1, 1],
            1,
            1,
            null,
            0,
            0,
            null,
            0,
          ],
          articleId,
          parseInt(timestamp),
          signature,
        ]),
      ],
    ],
  ]);

  const response = await fetch(
    'https://news.google.com/_/DotsSplashUi/data/batchexecute?rpcids=Fbv4je',
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
        'Referer': 'https://news.google.com/',
        'User-Agent': FETCH_CONFIG.headers['User-Agent'],
      },
      body: 'f.req=' + encodeURIComponent(payload),
    }
  );

  if (!response.ok) {
    throw new Error(`batchexecute failed: HTTP ${response.status}`);
  }

  const text = await response.text();

  // Parse the response to extract the URL
  // Response format: ["garturlres","https://...",1] (with possible escaping)
  const urlMatch = text.match(/\["garturlres","(https?:[^"]+)"/);
  if (urlMatch) {
    return urlMatch[1].replace(/\\u003d/g, '=').replace(/\\u0026/g, '&');
  }

  // Alternative format with escaped quotes
  const altMatch = text.match(/\[\\"garturlres\\",\\"(https?:[^"\\]+)\\"/);
  if (altMatch) {
    return altMatch[1].replace(/\\u003d/g, '=').replace(/\\u0026/g, '&');
  }

  throw new Error('Could not parse URL from batchexecute response');
}

/**
 * Fallback: Parse canonical URL from HTML page.
 */
async function fetchCanonicalFromHtml(googleUrl: string): Promise<string | null> {
  try {
    const response = await fetch(googleUrl, {
      method: 'GET',
      headers: {
        'User-Agent': FETCH_CONFIG.headers['User-Agent'],
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
      },
      redirect: 'follow',
    });

    // If we got redirected to a non-Google URL, that's our answer
    if (!response.url.includes('news.google.com')) {
      return response.url;
    }

    const html = await response.text();

    // Try to find canonical URL
    const canonicalMatch = html.match(/<link[^>]+rel=["']canonical["'][^>]+href=["']([^"']+)["']/i);
    if (canonicalMatch && !canonicalMatch[1].includes('news.google.com')) {
      return canonicalMatch[1];
    }

    // Try og:url
    const ogUrlMatch = html.match(/<meta[^>]+property=["']og:url["'][^>]+content=["']([^"']+)["']/i);
    if (ogUrlMatch && !ogUrlMatch[1].includes('news.google.com')) {
      return ogUrlMatch[1];
    }

    return null;
  } catch {
    return null;
  }
}

/**
 * Resolve a Google News URL to get the canonical URL.
 *
 * Multi-strategy approach:
 * 1. Try direct base64 decode (old format, no HTTP needed)
 * 2. For new format (AU_yqL), use Google's batchexecute API
 * 3. Fallback: GET HTML and parse canonical/og:url
 *
 * NOTE: Google News URL format changes frequently. The new AU_yqL format
 * (introduced 2024) is particularly difficult to decode. Some URLs may
 * fail to resolve - this is expected and the pipeline handles it gracefully.
 *
 * @param googleUrl - The Google News redirect URL
 * @returns The canonical URL
 */
export async function resolveGoogleNewsUrl(googleUrl: string): Promise<string> {
  // Sanitize URL - check for whitespace/newlines (indicates bad stored URL)
  const cleanUrl = googleUrl.trim();
  if (/\s/.test(cleanUrl)) {
    throw new Error('URL contains whitespace/newline (corrupted stored URL)');
  }

  // Strategy 1: Try direct decode (works for old format)
  const decodedUrl = decodeGoogleNewsUrl(cleanUrl);
  if (decodedUrl && !decodedUrl.includes('news.google.com')) {
    return decodedUrl;
  }

  // Strategy 2: For new format, use batchexecute API
  // Note: This API is brittle and may not work due to format changes
  if (needsBatchExecute(cleanUrl)) {
    const articleId = extractArticleId(cleanUrl);
    if (articleId) {
      try {
        const url = await fetchDecodedBatchExecute(articleId);
        if (url && !url.includes('news.google.com')) {
          return url;
        }
      } catch {
        // batchexecute failed - expected for many URLs
      }
    }
  }

  // Strategy 3: Fallback - GET HTML and parse canonical URL
  const canonicalUrl = await fetchCanonicalFromHtml(cleanUrl);
  if (canonicalUrl) {
    return canonicalUrl;
  }

  // All strategies failed - this is expected for new AU_yqL format URLs
  throw new Error('URL uses new Google News format (AU_yqL) - decode not available');
}

// ============================================================
// Domain Extraction
// ============================================================

/**
 * Extract the domain from a URL.
 *
 * Examples:
 *   https://www.reuters.com/markets/nvidia → reuters.com
 *   https://finance.yahoo.com/news/nvidia → finance.yahoo.com
 *   https://www.cnbc.com/2025/01/nvidia   → cnbc.com
 *
 * @param url - The full URL
 * @returns The domain (hostname with www. prefix removed)
 */
export function extractDomain(url: string): string {
  try {
    const parsed = new URL(url);
    // Remove 'www.' prefix for cleaner domain, keep other subdomains
    return parsed.hostname.replace(/^www\./, '');
  } catch {
    return '';
  }
}

// ============================================================
// URL Hashing
// ============================================================

/**
 * Generate SHA-256 hash of a URL.
 *
 * Used for canonical_url_hash (NOT url_hash which is set at insert time).
 *
 * @param url - The canonical URL to hash
 * @returns 64-character hex string (SHA-256)
 */
export function generateUrlHash(url: string): string {
  return createHash('sha256').update(url).digest('hex');
}

// ============================================================
// Single Item Resolution with Error Handling
// ============================================================

/**
 * Resolve a single feed item's Google News URL and update the database.
 *
 * On success: sets canonical_url, canonical_url_hash, source_domain, resolve_status='resolved'
 * On failure: sets resolve_status='failed', resolve_error with error message
 *
 * @param supabase - Supabase client
 * @param item - The raw feed item to resolve
 * @returns Result with success status and resolved data or error
 */
export async function resolveItem(
  supabase: SupabaseClient,
  item: RawFeedItem
): Promise<ResolveItemResult> {
  const urlToResolve = item.google_redirect_url || item.url;

  try {
    // Follow redirects to get canonical URL
    const canonicalUrl = await resolveGoogleNewsUrl(urlToResolve);

    // Check if resolution actually worked (not still a Google URL)
    if (canonicalUrl.includes('news.google.com')) {
      throw new Error('Resolution returned Google News URL - redirect may have failed');
    }

    // Extract domain and generate hash
    const sourceDomain = extractDomain(canonicalUrl);
    const canonicalUrlHash = generateUrlHash(canonicalUrl);

    // Update database - sets resolve_status='resolved'
    await updateRawFeedItemResolved(
      supabase,
      item.id,
      canonicalUrl,
      canonicalUrlHash,
      sourceDomain
    );

    return {
      id: item.id,
      success: true,
      canonicalUrl,
      sourceDomain,
    };
  } catch (error) {
    // Extract error message
    const errorMessage = error instanceof Error ? error.message : String(error);

    // Update database - sets resolve_status='failed', stores error
    await updateRawFeedItemResolveFailed(supabase, item.id, errorMessage);

    return {
      id: item.id,
      success: false,
      error: errorMessage,
    };
  }
}

// ============================================================
// Batch Processing
// ============================================================

/**
 * Process the resolve queue - batch resolve pending items.
 *
 * Fetches items with resolve_status='pending' and resolves them
 * one by one with rate limiting between requests.
 *
 * @param supabase - Supabase client
 * @param limit - Maximum number of items to process (default: 50)
 * @returns Statistics: resolved, failed, remaining, duration
 */
export async function processResolveQueue(
  supabase: SupabaseClient,
  limit: number = 50
): Promise<ResolveResult> {
  const startTime = Date.now();

  // Get pending items from database
  const pendingItems = await getPendingResolveItems(supabase, limit);

  let resolved = 0;
  let failed = 0;

  // Process items sequentially with rate limiting
  for (let i = 0; i < pendingItems.length; i++) {
    const item = pendingItems[i];
    const result = await resolveItem(supabase, item);

    if (result.success) {
      resolved++;
    } else {
      failed++;
    }

    // Rate limit: wait between requests (except after last item)
    if (i < pendingItems.length - 1) {
      const delayMs = 1000 / RATE_LIMITS.GOOGLE_NEWS; // 1 req/sec
      await sleep(delayMs);
    }
  }

  // Count remaining items in queue
  const { count } = await supabase
    .from('raw_feed_items')
    .select('*', { count: 'exact', head: true })
    .eq('resolve_status', 'pending');

  return {
    resolved,
    failed,
    remaining: count || 0,
    duration: Date.now() - startTime,
  };
}

// ============================================================
// Utilities
// ============================================================

function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}