// src/lib/finance/types.ts
// TypeScript interfaces for Finance TTS Briefing System
// Created: 2025-12-30

// ============================================================
// Database Entity Types
// ============================================================

export interface Ticker {
  ticker: string;
  company_name: string;
  cik: string;
  aliases: string[];
  is_active: boolean;
  created_at: string;
}

export interface FeedSource {
  id: string;
  source_name: string;
  ticker: string;
  tier: 'A' | 'B' | 'C';
  feed_type: 'SEC' | 'IR' | 'RSS' | 'GOOGLE_NEWS' | 'GDELT';
  feed_url: string;
  is_enabled: boolean;
  poll_minutes: number;
  etag: string | null;
  last_modified: string | null;
  last_fetched_at: string | null;
  last_error: string | null;
  error_count: number;
  created_at: string;
}

export interface RawFeedItem {
  id: string;
  feed_source_id: string | null;
  source_name: string;
  tier: 'A' | 'B' | 'C';
  ticker: string | null;

  // Timestamps
  published_at: string | null;
  fetched_at: string;

  // Content metadata
  title: string;
  summary: string | null;
  url: string;
  canonical_url: string | null;
  url_hash: string;
  canonical_url_hash: string | null;

  // Google News specific
  google_redirect_url: string | null;
  resolve_status: 'pending' | 'resolved' | 'failed';
  resolved_at: string | null;
  resolve_error: string | null;

  // External identifiers
  external_id: string | null;
  source_domain: string | null;

  // SEC specific
  filing_type: string | null;
  accession_no: string | null;

  content_type: string | null;
}

export interface EventCluster {
  cluster_id: string;
  ticker: string | null;
  cluster_title: string;
  cluster_fingerprint: string | null;
  first_seen_at: string;
  last_seen_at: string;
  representative_url: string | null;
  highest_tier: 'A' | 'B' | 'C' | null;
  source_count: number;
  item_count: number;
  created_at: string;
}

export interface ClusterItem {
  cluster_id: string;
  raw_item_id: string;
}

export interface EventScore {
  cluster_id: string;
  impact_score: number;
  event_type: string | null;
  horizon: string | null;
  why_it_matters: string | null;
  novelty_score: number | null;
  updated_at: string;
}

export interface Brief {
  id: string;
  brief_date: string;
  ticker_group: string;
  tickers: string[];
  top_cluster_ids: string[];
  script_text: string;
  created_at: string;
}

export interface AudioAsset {
  brief_id: string;
  storage_path: string | null;
  duration_sec: number | null;
  tts_provider: string | null;
  voice: string | null;
  created_at: string;
}

export interface PipelineRun {
  id: string;
  run_type: 'ingest' | 'resolve' | 'cluster' | 'score' | 'brief';
  started_at: string;
  finished_at: string | null;
  status: 'running' | 'success' | 'failed';
  items_processed: number;
  items_created: number;
  errors_count: number;
  error_message: string | null;
  metadata: Record<string, unknown> | null;
  created_at: string;
}

// ============================================================
// Input Types (for creating/updating records)
// ============================================================

export type CreateFeedSourceInput = Omit<FeedSource, 'id' | 'created_at' | 'last_fetched_at' | 'last_error' | 'error_count'>;

export type CreateRawFeedItemInput = Omit<RawFeedItem, 'id' | 'fetched_at' | 'resolved_at'>;

export type CreateEventClusterInput = Omit<EventCluster, 'cluster_id' | 'created_at'>;

export type CreateBriefInput = Omit<Brief, 'id' | 'created_at'>;

export type CreatePipelineRunInput = Pick<PipelineRun, 'run_type'> & {
  metadata?: Record<string, unknown>;
};

// ============================================================
// Enriched Types (with joined data)
// ============================================================

export interface EventClusterWithScore extends EventCluster {
  score: EventScore | null;
}

export interface EventClusterWithItems extends EventCluster {
  items: RawFeedItem[];
  score: EventScore | null;
}

export interface BriefWithClusters extends Brief {
  clusters: EventClusterWithScore[];
}

// ============================================================
// API Response Types
// ============================================================

export interface IngestResult {
  itemsIngested: number;
  itemsSkipped: number;
  clustersCreated: number;
  resolveQueueSize: number;
  duration: number;
  errors: string[];
}

export interface ResolveResult {
  resolved: number;
  failed: number;
  remaining: number;
  duration: number;
}

export interface BriefingResponse {
  date: string;
  tickers: string[];
  script: string;
  topEvents: EventClusterWithScore[];
  generatedAt: string;
}
