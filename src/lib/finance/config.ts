// src/lib/finance/config.ts
// Centralized configuration for Finance TTS Briefing System
// Created: 2025-12-30

// ============================================================
// Fetch Configuration
// ============================================================

export const FETCH_CONFIG = {
  // User-Agent (SEC recommends including contact email)
  headers: {
    'User-Agent': 'FinanceBriefBot/1.0 (contact@araverus.com)',
    'Accept': 'application/xml, application/atom+xml, text/xml, */*',
  },

  // Timeout in milliseconds
  timeout: 10000, // 10 seconds

  // Retry settings
  retry: {
    maxAttempts: 3,
    baseDelay: 1000,      // 1 second
    maxDelay: 10000,      // 10 seconds
    backoffMultiplier: 2, // Double delay each retry
  },
};

// Rate limits (requests per second)
export const RATE_LIMITS = {
  SEC: 10,           // SEC allows ~10 req/sec
  GOOGLE_NEWS: 1,    // Be conservative with Google
};

// ============================================================
// Scoring Configuration
// ============================================================
// Scoring formula: impact_score = tier_score + source_bonus + risk_weight - novelty_penalty
// - tier_score: Source tier (A=50, B=25, C=5)
// - source_bonus: min(20, source_count × 3)
// - risk_weight: From Loughran-McDonald dictionary (see keywords/dictionary.ts)
// - novelty_penalty: Reduce score for repeated topics

export const SCORING_CONFIG = {
  tierScores: { A: 50, B: 25, C: 5 } as const,
  sourceBonus: { multiplier: 3, max: 20 },
  riskWeight: { multiplier: 4, max: 10 },
  noveltyPenalty: { maxPenalty: 20, decayDays: 3 },
};

// ============================================================
// SEC Feed Configuration
// ============================================================

export const SEC_CONFIG = {
  // Base URL for SEC EDGAR Atom feeds
  baseUrl: 'https://www.sec.gov/cgi-bin/browse-edgar',

  // Filing types to monitor
  filingTypes: ['8-K', '10-K', '10-Q', '4'],

  // Number of items to fetch per request
  itemCount: 40,
};

// ============================================================
// Clustering Configuration
// ============================================================

export const CLUSTERING_CONFIG = {
  // Similarity threshold for pg_trgm (0-1)
  similarityThreshold: 0.72,

  // Time window for clustering (hours)
  clusterWindowHours: 48,

  // Minimum items to form a significant cluster
  minClusterSize: 1,
};

// ============================================================
// Briefing Configuration
// ============================================================

export const BRIEFING_CONFIG = {
  // Number of top events to include in briefing
  topEventsCount: 7,

  // Minimum score to include in briefing
  minScore: 10,

  // Default ticker group
  defaultTickerGroup: 'default',
};

// ============================================================
// fetchWithRetry() - Auto-retry with exponential backoff
// ============================================================

export async function fetchWithRetry(
  url: string,
  options: RequestInit = {},
  config = FETCH_CONFIG
): Promise<Response> {
  const { maxAttempts, baseDelay, maxDelay, backoffMultiplier } = config.retry;

  let lastError: Error | null = null;

  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), config.timeout);

      const response = await fetch(url, {
        ...options,
        headers: {
          ...config.headers,
          ...options.headers,
        },
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      // If response is OK or client error (4xx), return it
      if (response.ok || (response.status >= 400 && response.status < 500)) {
        return response;
      }

      // Server error (5xx) - retry
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);

    } catch (error) {
      lastError = error instanceof Error ? error : new Error(String(error));

      // Don't retry on abort (timeout) for last attempt
      if (attempt === maxAttempts) {
        break;
      }

      // Calculate delay with exponential backoff
      const delay = Math.min(
        baseDelay * Math.pow(backoffMultiplier, attempt - 1),
        maxDelay
      );

      console.warn(
        `[fetchWithRetry] Attempt ${attempt}/${maxAttempts} failed for ${url}. ` +
        `Retrying in ${delay}ms...`,
        lastError.message
      );

      await sleep(delay);
    }
  }

  throw new Error(
    `[fetchWithRetry] All ${maxAttempts} attempts failed for ${url}: ${lastError?.message}`
  );
}

// Helper: sleep for given milliseconds
function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// ============================================================
// URL Utilities
// ============================================================

export function buildGoogleNewsUrl(query: string): string {
  const encodedQuery = encodeURIComponent(query);
  return `https://news.google.com/rss/search?q=${encodedQuery}&hl=en-US&gl=US&ceid=US:en`;
}

export function buildSecFeedUrl(cik: string, filingType: string = '8-K'): string {
  const params = new URLSearchParams({
    action: 'getcompany',
    CIK: cik,
    type: filingType,
    dateb: '',
    owner: 'include',
    count: String(SEC_CONFIG.itemCount),
    output: 'atom',
  });
  return `${SEC_CONFIG.baseUrl}?${params.toString()}`;
}
