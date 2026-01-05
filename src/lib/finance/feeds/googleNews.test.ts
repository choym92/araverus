// src/lib/finance/feeds/googleNews.test.ts
// Unit tests for Google News RSS Fetcher
// Created: 2025-01-05
// Updated: 2025-01-05 - Updated for simplified query building

import { describe, it, expect } from 'vitest';
import {
  parseGoogleNewsRss,
  buildSearchQuery,
  extractDescription,
  extractSource,
  generateUrlHash,
  parseRfc2822Date,
  determineTier,
} from './googleNews';
import type { Ticker } from '../types';

// ============================================================
// Sample Google News RSS Feed XML
// ============================================================

const SAMPLE_GOOGLE_NEWS_FEED = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>NVDA OR NVIDIA - Google News</title>
    <link>https://news.google.com</link>
    <description>Google News</description>
    <item>
      <title>NVIDIA stock surges 5% on strong AI chip demand</title>
      <link>https://news.google.com/rss/articles/CBMiK2h0dHBzOi8vd3d3LnJldXRlcnMuY29tL252aWRpYS1zdG9jay1zdXJnZXM</link>
      <pubDate>Sun, 05 Jan 2025 10:30:00 GMT</pubDate>
      <description>&lt;a href="https://reuters.com"&gt;Reuters&lt;/a&gt; - NVIDIA reported strong demand for its AI chips...</description>
      <source url="https://www.reuters.com">Reuters</source>
    </item>
    <item>
      <title>NVIDIA announces new Blackwell GPU architecture</title>
      <link>https://news.google.com/rss/articles/CBMiMmh0dHBzOi8vd3d3LmNuYmMuY29tL252aWRpYS1ibGFja3dlbGwtYW5ub3VuY2U</link>
      <pubDate>Sat, 04 Jan 2025 14:15:00 GMT</pubDate>
      <description>NVIDIA unveiled its next-generation GPU...</description>
      <source url="https://www.cnbc.com">CNBC</source>
    </item>
    <item>
      <title>Why NVIDIA is the most important AI stock</title>
      <link>https://news.google.com/rss/articles/CBMiNWh0dHBzOi8vc2Vla2luZ2FscGhhLmNvbS9udmlkaWEtYWktc3RvY2s</link>
      <pubDate>Fri, 03 Jan 2025 09:00:00 GMT</pubDate>
      <description>Analysis of NVIDIA's market position...</description>
      <source url="https://seekingalpha.com">Seeking Alpha</source>
    </item>
  </channel>
</rss>`;

const EMPTY_GOOGLE_NEWS_FEED = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Search Results - Google News</title>
    <link>https://news.google.com</link>
  </channel>
</rss>`;

const SINGLE_ITEM_FEED = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>GOOG - Google News</title>
    <item>
      <title>Alphabet reports Q4 earnings beat</title>
      <link>https://news.google.com/rss/articles/CBMiYWxwaGFiZXQtZWFybmluZ3M</link>
      <pubDate>Thu, 02 Jan 2025 16:00:00 GMT</pubDate>
      <description>Alphabet Inc. reported better-than-expected earnings...</description>
      <source url="https://www.bloomberg.com">Bloomberg</source>
    </item>
  </channel>
</rss>`;

// Feed with HTML in description
const FEED_WITH_HTML_DESCRIPTION = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Test Article</title>
      <link>https://news.google.com/test</link>
      <pubDate>Mon, 06 Jan 2025 12:00:00 GMT</pubDate>
      <description>&lt;ol&gt;&lt;li&gt;&lt;a href="https://example.com"&gt;Example&lt;/a&gt;&lt;/li&gt;&lt;li&gt;Some text here&lt;/li&gt;&lt;/ol&gt;</description>
      <source>Test Source</source>
    </item>
  </channel>
</rss>`;

// ============================================================
// Tests: buildSearchQuery
// ============================================================

describe('buildSearchQuery', () => {
  it('should build query from ticker and company name', () => {
    const ticker: Ticker = {
      ticker: 'NVDA',
      company_name: 'NVIDIA Corporation',
      cik: '0001045810',
      aliases: [],
      is_active: true,
      created_at: '2025-01-01',
    };

    expect(buildSearchQuery(ticker)).toBe('NVDA OR NVIDIA');
  });

  it('should include aliases in query', () => {
    const ticker: Ticker = {
      ticker: 'GOOG',
      company_name: 'Alphabet Inc.',
      cik: '0001652044',
      aliases: ['GOOGL'],
      is_active: true,
      created_at: '2025-01-01',
    };

    expect(buildSearchQuery(ticker)).toBe('GOOG OR Alphabet OR GOOGL');
  });

  it('should not duplicate ticker if company name starts with same word', () => {
    const ticker: Ticker = {
      ticker: 'META',
      company_name: 'Meta Platforms Inc.',
      cik: '0001234567',
      aliases: [],
      is_active: true,
      created_at: '2025-01-01',
    };

    // Should not have "META OR Meta" - just "META"
    expect(buildSearchQuery(ticker)).toBe('META');
  });

  it('should handle ticker with multiple aliases', () => {
    const ticker: Ticker = {
      ticker: 'BRK.A',
      company_name: 'Berkshire Hathaway',
      cik: '0001234567',
      aliases: ['BRK.B', 'Berkshire'],
      is_active: true,
      created_at: '2025-01-01',
    };

    expect(buildSearchQuery(ticker)).toBe('BRK.A OR Berkshire OR BRK.B');
  });
});

// ============================================================
// Tests: parseGoogleNewsRss
// ============================================================

describe('parseGoogleNewsRss', () => {
  it('should parse multiple items from Google News RSS feed', () => {
    const items = parseGoogleNewsRss(SAMPLE_GOOGLE_NEWS_FEED);

    expect(items).toHaveLength(3);

    // First item
    expect(items[0].title).toBe('NVIDIA stock surges 5% on strong AI chip demand');
    expect(items[0].link).toContain('news.google.com/rss/articles');
    expect(items[0].source).toBe('Reuters');
    expect(items[0].pubDate).toBe('Sun, 05 Jan 2025 10:30:00 GMT');

    // Second item
    expect(items[1].title).toBe('NVIDIA announces new Blackwell GPU architecture');
    expect(items[1].source).toBe('CNBC');

    // Third item
    expect(items[2].title).toBe('Why NVIDIA is the most important AI stock');
    expect(items[2].source).toBe('Seeking Alpha');
  });

  it('should handle empty feed', () => {
    const items = parseGoogleNewsRss(EMPTY_GOOGLE_NEWS_FEED);
    expect(items).toHaveLength(0);
  });

  it('should handle single item (not array)', () => {
    const items = parseGoogleNewsRss(SINGLE_ITEM_FEED);

    expect(items).toHaveLength(1);
    expect(items[0].title).toBe('Alphabet reports Q4 earnings beat');
    expect(items[0].source).toBe('Bloomberg');
  });

  it('should handle malformed XML gracefully', () => {
    expect(() => parseGoogleNewsRss('')).not.toThrow();
    expect(parseGoogleNewsRss('')).toHaveLength(0);

    expect(() => parseGoogleNewsRss('not xml')).not.toThrow();
  });

  it('should strip HTML from description', () => {
    const items = parseGoogleNewsRss(FEED_WITH_HTML_DESCRIPTION);

    expect(items).toHaveLength(1);
    expect(items[0].description).not.toContain('<');
    expect(items[0].description).not.toContain('>');
    expect(items[0].description).toContain('Some text here');
  });
});

// ============================================================
// Tests: extractDescription
// ============================================================

describe('extractDescription', () => {
  it('should extract string description', () => {
    expect(extractDescription('Simple description')).toBe('Simple description');
  });

  it('should strip HTML tags', () => {
    expect(extractDescription('<a href="x">Link</a> text')).toBe('Link text');
    expect(extractDescription('<b>Bold</b> and <i>italic</i>')).toBe('Bold and italic');
  });

  it('should handle object with #text property', () => {
    expect(extractDescription({ '#text': 'Text content' })).toBe('Text content');
  });

  it('should handle null/undefined', () => {
    expect(extractDescription(null)).toBe('');
    expect(extractDescription(undefined)).toBe('');
  });
});

// ============================================================
// Tests: extractSource
// ============================================================

describe('extractSource', () => {
  it('should extract string source', () => {
    expect(extractSource('Reuters')).toBe('Reuters');
  });

  it('should extract source from object with #text', () => {
    expect(extractSource({ '#text': 'Bloomberg', '@_url': 'https://bloomberg.com' }))
      .toBe('Bloomberg');
  });

  it('should handle null/undefined', () => {
    expect(extractSource(null)).toBe('');
    expect(extractSource(undefined)).toBe('');
  });
});

// ============================================================
// Tests: generateUrlHash
// ============================================================

describe('generateUrlHash', () => {
  it('should generate consistent SHA-256 hash', () => {
    const url = 'https://news.google.com/rss/articles/CBMiK2h0dHBz';
    const hash1 = generateUrlHash(url);
    const hash2 = generateUrlHash(url);

    expect(hash1).toBe(hash2);
    expect(hash1).toHaveLength(64); // SHA-256 hex = 64 chars
  });

  it('should generate different hashes for different URLs', () => {
    const hash1 = generateUrlHash('https://news.google.com/a');
    const hash2 = generateUrlHash('https://news.google.com/b');

    expect(hash1).not.toBe(hash2);
  });
});

// ============================================================
// Tests: parseRfc2822Date
// ============================================================

describe('parseRfc2822Date', () => {
  it('should parse RFC 2822 date to ISO format', () => {
    const result = parseRfc2822Date('Sun, 05 Jan 2025 10:30:00 GMT');

    expect(result).toBe('2025-01-05T10:30:00.000Z');
  });

  it('should handle different timezones', () => {
    const result = parseRfc2822Date('Sat, 04 Jan 2025 14:15:00 -0500');

    expect(result).not.toBeNull();
    // Should convert to UTC
    expect(result).toContain('2025-01-04');
  });

  it('should return null for invalid date', () => {
    expect(parseRfc2822Date('')).toBeNull();
    expect(parseRfc2822Date('not a date')).toBeNull();
    expect(parseRfc2822Date('invalid')).toBeNull();
  });
});

// ============================================================
// Tests: determineTier
// ============================================================

describe('determineTier', () => {
  it('should return A for tier A sources', () => {
    expect(determineTier('Reuters')).toBe('A');
    expect(determineTier('Bloomberg')).toBe('A');
    expect(determineTier('CNBC')).toBe('A');
    expect(determineTier('Wall Street Journal')).toBe('A');
    expect(determineTier('WSJ')).toBe('A');
    expect(determineTier('Financial Times')).toBe('A');
  });

  it('should return B for tier B sources', () => {
    expect(determineTier('Yahoo Finance')).toBe('B');
    expect(determineTier('MarketWatch')).toBe('B');
    expect(determineTier('Seeking Alpha')).toBe('B');
    expect(determineTier('Barron\'s')).toBe('B');
  });

  it('should return C for unknown sources', () => {
    expect(determineTier('Random Blog')).toBe('C');
    expect(determineTier('Unknown Source')).toBe('C');
    expect(determineTier('')).toBe('C');
  });

  it('should be case insensitive', () => {
    expect(determineTier('reuters')).toBe('A');
    expect(determineTier('REUTERS')).toBe('A');
    expect(determineTier('yahoo finance')).toBe('B');
  });
});
