// src/lib/finance/keywords/dictionary.ts
// Loughran-McDonald Dictionary Loader & Feature Extraction Utility
// Created: 2025-12-30
//
// PURPOSE: This is a "dictionary/feature utility", NOT a sentiment scoring engine.
// - L-M dictionary is built for 10-K filings, not news headlines
// - Use it for RISK SIGNALS (uncertainty, litigious, constraining)
// - Do NOT use positive/negative as final sentiment labels for headlines
// - Final scoring combines: TF-IDF keywords + L-M risk features + source tier

import * as fs from 'fs';
import * as path from 'path';

// ============================================================
// Types
// ============================================================

export type LMCategory =
  | 'negative'
  | 'positive'
  | 'uncertainty'
  | 'litigious'
  | 'strong_modal'
  | 'weak_modal'
  | 'constraining';

export interface DictionaryWord {
  word: string;
  categories: LMCategory[];
  syllables: number;
}

export interface LMDictionary {
  words: Map<string, DictionaryWord>;
  negative: Set<string>;
  positive: Set<string>;
  uncertainty: Set<string>;
  litigious: Set<string>;
  strong_modal: Set<string>;
  weak_modal: Set<string>;
  constraining: Set<string>;
}

/**
 * Feature extraction result from L-M dictionary.
 * Contains both raw counts and ratios (count / total tokens).
 */
export interface LMFeatures {
  // Token info
  tokenCount: number;

  // Raw counts per category
  counts: Record<LMCategory, number>;

  // Ratios (count / tokenCount) - useful for comparing texts of different lengths
  ratios: Record<LMCategory, number>;

  // Risk score: weighted combination of uncertainty + litigious + constraining
  // This is what L-M is actually good at for news
  riskScore: number;

  // Matched words per category (for debugging)
  matchedWords: Record<LMCategory, string[]>;
}

// ============================================================
// CSV Parsing (Internal)
// ============================================================

interface CSVRow {
  Word: string;
  Negative: string;
  Positive: string;
  Uncertainty: string;
  Litigious: string;
  Strong_Modal: string;
  Weak_Modal: string;
  Constraining: string;
  Syllables: string;
}

function parseCSVLine(line: string, headers: string[]): CSVRow | null {
  const values = line.split(',');
  if (values.length !== headers.length) return null;

  const row: Record<string, string> = {};
  headers.forEach((header, i) => {
    row[header] = values[i] || '';
  });

  return row as unknown as CSVRow;
}

// ============================================================
// Dictionary Loading
// ============================================================

let cachedDictionary: LMDictionary | null = null;

/**
 * Load and parse the Loughran-McDonald Master Dictionary CSV.
 * Results are cached after first load.
 */
export function loadLMDictionary(): LMDictionary {
  if (cachedDictionary) {
    return cachedDictionary;
  }

  const csvPath = path.join(
    process.cwd(),
    'src/lib/finance/data/LoughranMcDonald_MasterDictionary.csv'
  );

  const content = fs.readFileSync(csvPath, 'utf-8');
  const lines = content.split('\n');

  if (lines.length < 2) {
    throw new Error('Loughran-McDonald dictionary CSV is empty or malformed');
  }

  const headers = lines[0].split(',');

  const dictionary: LMDictionary = {
    words: new Map(),
    negative: new Set(),
    positive: new Set(),
    uncertainty: new Set(),
    litigious: new Set(),
    strong_modal: new Set(),
    weak_modal: new Set(),
    constraining: new Set(),
  };

  for (let i = 1; i < lines.length; i++) {
    const line = lines[i].trim();
    if (!line) continue;

    const row = parseCSVLine(line, headers);
    if (!row || !row.Word) continue;

    const word = row.Word.toUpperCase();
    const categories: LMCategory[] = [];

    // Non-zero value (year) means word belongs to category
    if (row.Negative !== '0' && row.Negative !== '') {
      categories.push('negative');
      dictionary.negative.add(word);
    }
    if (row.Positive !== '0' && row.Positive !== '') {
      categories.push('positive');
      dictionary.positive.add(word);
    }
    if (row.Uncertainty !== '0' && row.Uncertainty !== '') {
      categories.push('uncertainty');
      dictionary.uncertainty.add(word);
    }
    if (row.Litigious !== '0' && row.Litigious !== '') {
      categories.push('litigious');
      dictionary.litigious.add(word);
    }
    if (row.Strong_Modal !== '0' && row.Strong_Modal !== '') {
      categories.push('strong_modal');
      dictionary.strong_modal.add(word);
    }
    if (row.Weak_Modal !== '0' && row.Weak_Modal !== '') {
      categories.push('weak_modal');
      dictionary.weak_modal.add(word);
    }
    if (row.Constraining !== '0' && row.Constraining !== '') {
      categories.push('constraining');
      dictionary.constraining.add(word);
    }

    dictionary.words.set(word, {
      word,
      categories,
      syllables: parseInt(row.Syllables, 10) || 0,
    });
  }

  cachedDictionary = dictionary;
  return dictionary;
}

// ============================================================
// Lookup Functions
// ============================================================

/**
 * Check if a word belongs to a specific L-M category.
 */
export function isInCategory(word: string, category: LMCategory): boolean {
  const dict = loadLMDictionary();
  const upperWord = word.toUpperCase();

  switch (category) {
    case 'negative': return dict.negative.has(upperWord);
    case 'positive': return dict.positive.has(upperWord);
    case 'uncertainty': return dict.uncertainty.has(upperWord);
    case 'litigious': return dict.litigious.has(upperWord);
    case 'strong_modal': return dict.strong_modal.has(upperWord);
    case 'weak_modal': return dict.weak_modal.has(upperWord);
    case 'constraining': return dict.constraining.has(upperWord);
    default: return false;
  }
}

/**
 * Get all L-M categories a word belongs to.
 */
export function getWordCategories(word: string): LMCategory[] {
  const dict = loadLMDictionary();
  const entry = dict.words.get(word.toUpperCase());
  return entry?.categories || [];
}

/**
 * Check if word exists in L-M dictionary (any category or no category).
 */
export function isInDictionary(word: string): boolean {
  const dict = loadLMDictionary();
  return dict.words.has(word.toUpperCase());
}

// ============================================================
// Feature Extraction (Main Purpose of This File)
// ============================================================

/**
 * Extract L-M features from text (headline, summary, etc.)
 *
 * Returns counts, ratios, and a risk score.
 * Use riskScore for scoring - it combines uncertainty + litigious + constraining.
 *
 * NOTE: Do NOT use positive/negative counts as "market sentiment".
 * L-M was built for 10-K filings, not news headlines.
 */
export function extractLMFeatures(text: string): LMFeatures {
  const dict = loadLMDictionary();

  // Tokenize: split on non-alphabetic, filter short words
  const tokens = text
    .toUpperCase()
    .split(/[^A-Z]+/)
    .filter(w => w.length > 1);

  const tokenCount = tokens.length;

  // Initialize counts and matched words
  const counts: Record<LMCategory, number> = {
    negative: 0,
    positive: 0,
    uncertainty: 0,
    litigious: 0,
    strong_modal: 0,
    weak_modal: 0,
    constraining: 0,
  };

  const matchedWords: Record<LMCategory, string[]> = {
    negative: [],
    positive: [],
    uncertainty: [],
    litigious: [],
    strong_modal: [],
    weak_modal: [],
    constraining: [],
  };

  // Count matches
  for (const token of tokens) {
    if (dict.negative.has(token)) {
      counts.negative++;
      matchedWords.negative.push(token);
    }
    if (dict.positive.has(token)) {
      counts.positive++;
      matchedWords.positive.push(token);
    }
    if (dict.uncertainty.has(token)) {
      counts.uncertainty++;
      matchedWords.uncertainty.push(token);
    }
    if (dict.litigious.has(token)) {
      counts.litigious++;
      matchedWords.litigious.push(token);
    }
    if (dict.strong_modal.has(token)) {
      counts.strong_modal++;
      matchedWords.strong_modal.push(token);
    }
    if (dict.weak_modal.has(token)) {
      counts.weak_modal++;
      matchedWords.weak_modal.push(token);
    }
    if (dict.constraining.has(token)) {
      counts.constraining++;
      matchedWords.constraining.push(token);
    }
  }

  // Calculate ratios
  const ratios: Record<LMCategory, number> = {
    negative: tokenCount > 0 ? counts.negative / tokenCount : 0,
    positive: tokenCount > 0 ? counts.positive / tokenCount : 0,
    uncertainty: tokenCount > 0 ? counts.uncertainty / tokenCount : 0,
    litigious: tokenCount > 0 ? counts.litigious / tokenCount : 0,
    strong_modal: tokenCount > 0 ? counts.strong_modal / tokenCount : 0,
    weak_modal: tokenCount > 0 ? counts.weak_modal / tokenCount : 0,
    constraining: tokenCount > 0 ? counts.constraining / tokenCount : 0,
  };

  // Risk score: weighted combination of what L-M is actually good at
  // uncertainty (0.4) + litigious (0.4) + constraining (0.2)
  const riskScore =
    counts.uncertainty * 0.4 +
    counts.litigious * 0.4 +
    counts.constraining * 0.2;

  return {
    tokenCount,
    counts,
    ratios,
    riskScore,
    matchedWords,
  };
}

// ============================================================
// Dictionary Statistics (for debugging/logging)
// ============================================================

export function getDictionaryStats(): Record<string, number> {
  const dict = loadLMDictionary();

  return {
    totalWords: dict.words.size,
    negative: dict.negative.size,
    positive: dict.positive.size,
    uncertainty: dict.uncertainty.size,
    litigious: dict.litigious.size,
    strong_modal: dict.strong_modal.size,
    weak_modal: dict.weak_modal.size,
    constraining: dict.constraining.size,
  };
}
