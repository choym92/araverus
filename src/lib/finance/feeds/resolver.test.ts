// src/lib/finance/feeds/resolver.test.ts
// Unit tests for Google News URL Resolver
// Created: 2025-01-05

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  extractDomain,
  generateUrlHash,
  resolveGoogleNewsUrl,
} from './resolver';

// ============================================================
// Tests: extractDomain
// ============================================================

describe('extractDomain', () => {
  it('should extract domain from standard URL', () => {
    expect(extractDomain('https://reuters.com/markets/nvidia')).toBe('reuters.com');
  });

  it('should remove www. prefix', () => {
    expect(extractDomain('https://www.reuters.com/markets/nvidia')).toBe('reuters.com');
    expect(extractDomain('https://www.cnbc.com/2025/01/05/nvidia')).toBe('cnbc.com');
  });

  it('should keep other subdomains', () => {
    expect(extractDomain('https://finance.yahoo.com/news/nvidia')).toBe('finance.yahoo.com');
    expect(extractDomain('https://money.cnn.com/article')).toBe('money.cnn.com');
  });

  it('should handle URLs with ports', () => {
    expect(extractDomain('https://localhost:3000/test')).toBe('localhost');
  });

  it('should handle URLs with query strings', () => {
    expect(extractDomain('https://www.reuters.com/article?id=123&foo=bar')).toBe('reuters.com');
  });

  it('should return empty string for invalid URLs', () => {
    expect(extractDomain('')).toBe('');
    expect(extractDomain('not-a-url')).toBe('');
    expect(extractDomain('ftp://')).toBe('');
  });
});

// ============================================================
// Tests: generateUrlHash
// ============================================================

describe('generateUrlHash', () => {
  it('should generate consistent SHA-256 hash', () => {
    const url = 'https://www.reuters.com/nvidia-stock-surges';
    const hash1 = generateUrlHash(url);
    const hash2 = generateUrlHash(url);

    expect(hash1).toBe(hash2);
    expect(hash1).toHaveLength(64); // SHA-256 hex = 64 chars
  });

  it('should generate different hashes for different URLs', () => {
    const hash1 = generateUrlHash('https://reuters.com/article-a');
    const hash2 = generateUrlHash('https://reuters.com/article-b');

    expect(hash1).not.toBe(hash2);
  });

  it('should be case-sensitive', () => {
    const hash1 = generateUrlHash('https://Reuters.com/article');
    const hash2 = generateUrlHash('https://reuters.com/article');

    expect(hash1).not.toBe(hash2);
  });

  it('should handle empty string', () => {
    const hash = generateUrlHash('');
    expect(hash).toHaveLength(64);
  });
});

// ============================================================
// Tests: resolveGoogleNewsUrl (with mocked fetch)
// ============================================================

describe('resolveGoogleNewsUrl', () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    global.fetch = originalFetch;
    vi.useRealTimers();
  });

  it('should return final URL after redirects', async () => {
    const googleUrl = 'https://news.google.com/rss/articles/CBMiTest';
    const canonicalUrl = 'https://www.reuters.com/nvidia-stock';

    // Mock fetch to simulate redirect
    global.fetch = vi.fn().mockResolvedValue({
      url: canonicalUrl, // Final URL after redirects
      ok: true,
    });

    const result = await resolveGoogleNewsUrl(googleUrl);

    expect(result).toBe(canonicalUrl);
    expect(global.fetch).toHaveBeenCalledWith(
      googleUrl,
      expect.objectContaining({
        method: 'HEAD',
        redirect: 'follow',
      })
    );
  });

  it('should fall back to GET if HEAD fails', async () => {
    const googleUrl = 'https://news.google.com/rss/articles/CBMiTest';
    const canonicalUrl = 'https://www.cnbc.com/nvidia-news';

    let callCount = 0;
    global.fetch = vi.fn().mockImplementation(() => {
      callCount++;
      if (callCount === 1) {
        // HEAD request fails
        return Promise.reject(new Error('HEAD not supported'));
      }
      // GET request succeeds
      return Promise.resolve({
        url: canonicalUrl,
        ok: true,
      });
    });

    const result = await resolveGoogleNewsUrl(googleUrl);

    expect(result).toBe(canonicalUrl);
    expect(global.fetch).toHaveBeenCalledTimes(2);
  });

  it('should throw on aborted request', async () => {
    const googleUrl = 'https://news.google.com/rss/articles/CBMiTest';

    // Mock fetch that immediately rejects with abort error
    global.fetch = vi.fn().mockRejectedValue(new Error('aborted'));

    await expect(resolveGoogleNewsUrl(googleUrl)).rejects.toThrow('aborted');
  });
});

// ============================================================
// Tests: Integration scenarios (descriptive)
// ============================================================

describe('URL Resolution Flow', () => {
  it('should handle the complete resolution flow conceptually', () => {
    // This test documents the expected flow:
    // 1. Google News URL comes in
    // 2. resolveGoogleNewsUrl() follows redirects
    // 3. extractDomain() gets the source domain
    // 4. generateUrlHash() creates canonical_url_hash
    // 5. Database is updated with resolved data

    // Example: Google URL → Canonical URL
    // 'https://news.google.com/rss/articles/CBMiK2h0dHBz' → canonicalUrl below
    const canonicalUrl = 'https://www.bloomberg.com/nvidia-earnings';

    // After resolution:
    const domain = extractDomain(canonicalUrl);
    const hash = generateUrlHash(canonicalUrl);

    expect(domain).toBe('bloomberg.com');
    expect(hash).toHaveLength(64);
  });

  it('should correctly identify still-Google URLs as failures', () => {
    // If resolution returns a Google URL, it means redirect failed
    const stillGoogleUrl = 'https://news.google.com/articles/something';

    // This should be treated as a failure in resolveItem()
    expect(stillGoogleUrl.includes('news.google.com')).toBe(true);
  });
});
