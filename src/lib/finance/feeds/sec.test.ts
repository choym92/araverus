// src/lib/finance/feeds/sec.test.ts
// Unit tests for SEC EDGAR Feed Fetcher
// Created: 2025-01-05

import { describe, it, expect } from 'vitest';
import {
  parseSecAtomFeed,
  extractAccessionNo,
  extractFilingType,
  extractLink,
  generateUrlHash,
} from './sec';

// ============================================================
// Sample SEC Atom Feed XML
// ============================================================

const SAMPLE_SEC_FEED = `<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>EDGAR Company Filings - 8-K</title>
  <link href="https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&amp;CIK=0001045810&amp;type=8-K&amp;output=atom" rel="self" type="application/atom+xml"/>
  <updated>2025-01-05T16:30:00-05:00</updated>
  <entry>
    <title>8-K - NVIDIA Corporation (0001045810)</title>
    <link href="https://www.sec.gov/Archives/edgar/data/1045810/000104581025000042/0001045810-25-000042-index.htm" rel="alternate" type="text/html"/>
    <summary type="html">&lt;b&gt;Filed:&lt;/b&gt; 2025-01-05 &lt;b&gt;AccNo:&lt;/b&gt; 0001045810-25-000042 &lt;b&gt;Size:&lt;/b&gt; 123 KB</summary>
    <updated>2025-01-05T16:30:00-05:00</updated>
    <category scheme="https://www.sec.gov/" label="form type" term="8-K"/>
    <id>urn:tag:sec.gov,2008:accession-number=0001045810-25-000042</id>
  </entry>
  <entry>
    <title>8-K/A - NVIDIA Corporation (0001045810)</title>
    <link href="https://www.sec.gov/Archives/edgar/data/1045810/000104581025000041/0001045810-25-000041-index.htm" rel="alternate" type="text/html"/>
    <summary type="html">&lt;b&gt;Filed:&lt;/b&gt; 2025-01-04 &lt;b&gt;AccNo:&lt;/b&gt; 0001045810-25-000041</summary>
    <updated>2025-01-04T10:15:00-05:00</updated>
    <category scheme="https://www.sec.gov/" label="form type" term="8-K/A"/>
    <id>urn:tag:sec.gov,2008:accession-number=0001045810-25-000041</id>
  </entry>
</feed>`;

const EMPTY_SEC_FEED = `<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>EDGAR Company Filings</title>
  <updated>2025-01-05T00:00:00-05:00</updated>
</feed>`;

const SINGLE_ENTRY_FEED = `<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>EDGAR Company Filings - 10-K</title>
  <entry>
    <title>10-K - Alphabet Inc. (0001652044)</title>
    <link href="https://www.sec.gov/Archives/edgar/data/1652044/000165204425000001/0001652044-25-000001-index.htm" rel="alternate" type="text/html"/>
    <summary type="html">Annual Report</summary>
    <updated>2025-01-03T09:00:00-05:00</updated>
    <id>urn:tag:sec.gov,2008:accession-number=0001652044-25-000001</id>
  </entry>
</feed>`;

// ============================================================
// Tests: parseSecAtomFeed
// ============================================================

describe('parseSecAtomFeed', () => {
  it('should parse multiple entries from SEC Atom feed', () => {
    const entries = parseSecAtomFeed(SAMPLE_SEC_FEED);

    expect(entries).toHaveLength(2);

    // First entry
    expect(entries[0].title).toBe('8-K - NVIDIA Corporation (0001045810)');
    expect(entries[0].accessionNo).toBe('0001045810-25-000042');
    expect(entries[0].filingType).toBe('8-K');
    expect(entries[0].link).toContain('0001045810-25-000042');
    expect(entries[0].updated).toBe('2025-01-05T16:30:00-05:00');

    // Second entry (amended filing)
    expect(entries[1].title).toBe('8-K/A - NVIDIA Corporation (0001045810)');
    expect(entries[1].accessionNo).toBe('0001045810-25-000041');
    expect(entries[1].filingType).toBe('8-K/A');
  });

  it('should handle empty feed', () => {
    const entries = parseSecAtomFeed(EMPTY_SEC_FEED);
    expect(entries).toHaveLength(0);
  });

  it('should handle single entry (not array)', () => {
    const entries = parseSecAtomFeed(SINGLE_ENTRY_FEED);

    expect(entries).toHaveLength(1);
    expect(entries[0].title).toBe('10-K - Alphabet Inc. (0001652044)');
    expect(entries[0].accessionNo).toBe('0001652044-25-000001');
    expect(entries[0].filingType).toBe('10-K');
  });

  it('should handle malformed XML gracefully', () => {
    expect(() => parseSecAtomFeed('')).not.toThrow();
    expect(parseSecAtomFeed('')).toHaveLength(0);

    expect(() => parseSecAtomFeed('not xml')).not.toThrow();
  });
});

// ============================================================
// Tests: extractAccessionNo
// ============================================================

describe('extractAccessionNo', () => {
  it('should extract accession number from SEC ID', () => {
    const id = 'urn:tag:sec.gov,2008:accession-number=0001045810-25-000042';
    expect(extractAccessionNo(id)).toBe('0001045810-25-000042');
  });

  it('should handle different accession number formats', () => {
    expect(extractAccessionNo('urn:tag:sec.gov,2008:accession-number=0001652044-25-000001'))
      .toBe('0001652044-25-000001');
    expect(extractAccessionNo('urn:tag:sec.gov,2008:accession-number=0000320193-24-000123'))
      .toBe('0000320193-24-000123');
  });

  it('should return empty string for invalid ID', () => {
    expect(extractAccessionNo('')).toBe('');
    expect(extractAccessionNo('invalid')).toBe('');
    expect(extractAccessionNo('urn:tag:sec.gov,2008:something-else')).toBe('');
  });
});

// ============================================================
// Tests: extractFilingType
// ============================================================

describe('extractFilingType', () => {
  it('should extract filing type from title', () => {
    expect(extractFilingType('8-K - NVIDIA Corporation (0001045810)')).toBe('8-K');
    expect(extractFilingType('10-K - Alphabet Inc. (0001652044)')).toBe('10-K');
    expect(extractFilingType('10-Q - Apple Inc. (0000320193)')).toBe('10-Q');
  });

  it('should handle amended filings', () => {
    expect(extractFilingType('8-K/A - NVIDIA Corporation (0001045810)')).toBe('8-K/A');
    expect(extractFilingType('10-K/A - Company Name')).toBe('10-K/A');
  });

  it('should handle Form 4', () => {
    expect(extractFilingType('4 - Jensen Huang')).toBe('4');
  });

  it('should return empty string for invalid title', () => {
    expect(extractFilingType('')).toBe('');
    expect(extractFilingType('No filing type here')).toBe('');
  });
});

// ============================================================
// Tests: extractLink
// ============================================================

describe('extractLink', () => {
  it('should extract href from link object', () => {
    const link = { '@_href': 'https://www.sec.gov/Archives/...', '@_rel': 'alternate' };
    expect(extractLink(link)).toBe('https://www.sec.gov/Archives/...');
  });

  it('should handle string link', () => {
    expect(extractLink('https://example.com')).toBe('https://example.com');
  });

  it('should handle array of links (pick alternate)', () => {
    const links = [
      { '@_href': 'https://self.com', '@_rel': 'self' },
      { '@_href': 'https://alternate.com', '@_rel': 'alternate' },
    ];
    expect(extractLink(links)).toBe('https://alternate.com');
  });

  it('should handle empty/null', () => {
    expect(extractLink(null)).toBe('');
    expect(extractLink(undefined)).toBe('');
    expect(extractLink({})).toBe('');
  });
});

// ============================================================
// Tests: generateUrlHash
// ============================================================

describe('generateUrlHash', () => {
  it('should generate consistent SHA-256 hash', () => {
    const url = 'https://www.sec.gov/Archives/edgar/data/1045810/000104581025000042/';
    const hash1 = generateUrlHash(url);
    const hash2 = generateUrlHash(url);

    expect(hash1).toBe(hash2);
    expect(hash1).toHaveLength(64); // SHA-256 hex = 64 chars
  });

  it('should generate different hashes for different URLs', () => {
    const hash1 = generateUrlHash('https://example.com/a');
    const hash2 = generateUrlHash('https://example.com/b');

    expect(hash1).not.toBe(hash2);
  });
});
