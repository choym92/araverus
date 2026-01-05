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
 * Resolve a Google News redirect URL to get the canonical URL.
 *
 * Google News URLs are like:
 * https://news.google.com/rss/articles/CBMiK2h0dHBzOi8vd3d3LnJldXRlcnMuY29tLy4uLg
 *
 * Following the redirect gives us the actual article URL:
 * https://www.reuters.com/markets/nvidia-stock-surges/
 *
 * @param googleUrl - The Google News redirect URL
 * @returns The canonical URL after following redirects
 */
export async function resolveGoogleNewsUrl(googleUrl: string): Promise<string> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), FETCH_CONFIG.timeout);

  try {
    // Use HEAD request (faster - we only need the final URL, not content)
    const response = await fetch(googleUrl, {
      method: 'HEAD',
      redirect: 'follow', // Automatically follow redirects
      headers: {
        'User-Agent': FETCH_CONFIG.headers['User-Agent'],
        'Accept': 'text/html,application/xhtml+xml',
      },
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    // response.url is the final URL after all redirects
    return response.url;
  } catch (error) {
    clearTimeout(timeoutId);

    // If HEAD fails, try GET (some servers don't support HEAD)
    if (error instanceof Error && !error.message.includes('abort')) {
      return resolveWithGet(googleUrl);
    }

    throw error;
  }
}

/**
 * Fallback: resolve URL using GET request.
 * Some servers don't support HEAD requests.
 */
async function resolveWithGet(googleUrl: string): Promise<string> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), FETCH_CONFIG.timeout);

  try {
    const response = await fetch(googleUrl, {
      method: 'GET',
      redirect: 'follow',
      headers: {
        'User-Agent': FETCH_CONFIG.headers['User-Agent'],
        'Accept': 'text/html,application/xhtml+xml',
      },
      signal: controller.signal,
    });

    clearTimeout(timeoutId);
    return response.url;
  } finally {
    clearTimeout(timeoutId);
  }
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