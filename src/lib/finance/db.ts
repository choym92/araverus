// src/lib/finance/db.ts
// Typed Supabase query helpers for Finance TTS Briefing System
// Created: 2025-12-30

import { SupabaseClient } from '@supabase/supabase-js';
import type {
  Ticker,
  FeedSource,
  RawFeedItem,
  EventCluster,
  EventScore,
  Brief,
  PipelineRun,
  CreateRawFeedItemInput,
  CreateEventClusterInput,
  CreateBriefInput,
  CreatePipelineRunInput,
  EventClusterWithScore,
} from './types';

// ============================================================
// Tickers
// ============================================================

export async function getActiveTickers(supabase: SupabaseClient): Promise<Ticker[]> {
  const { data, error } = await supabase
    .from('tickers')
    .select('*')
    .eq('is_active', true);

  if (error) throw error;
  return data || [];
}

export async function getTickerByCik(supabase: SupabaseClient, cik: string): Promise<Ticker | null> {
  const { data, error } = await supabase
    .from('tickers')
    .select('*')
    .eq('cik', cik)
    .single();

  if (error && error.code !== 'PGRST116') throw error;
  return data;
}

export async function getTickerBySymbol(supabase: SupabaseClient, symbol: string): Promise<Ticker | null> {
  const { data, error } = await supabase
    .from('tickers')
    .select('*')
    .eq('ticker', symbol.toUpperCase())
    .single();

  if (error && error.code !== 'PGRST116') throw error;
  return data;
}

// ============================================================
// Feed Sources
// ============================================================

export async function getEnabledFeedSources(supabase: SupabaseClient): Promise<FeedSource[]> {
  const { data, error } = await supabase
    .from('feed_sources')
    .select('*')
    .eq('is_enabled', true);

  if (error) throw error;
  return data || [];
}

export async function getFeedSourcesByTicker(
  supabase: SupabaseClient,
  ticker: string
): Promise<FeedSource[]> {
  const { data, error } = await supabase
    .from('feed_sources')
    .select('*')
    .eq('ticker', ticker)
    .eq('is_enabled', true);

  if (error) throw error;
  return data || [];
}

export async function updateFeedSourceAfterFetch(
  supabase: SupabaseClient,
  id: string,
  updates: {
    etag?: string | null;
    last_modified?: string | null;
    last_error?: string | null;
    error_count?: number;
  }
): Promise<void> {
  const { error } = await supabase
    .from('feed_sources')
    .update({
      ...updates,
      last_fetched_at: new Date().toISOString(),
    })
    .eq('id', id);

  if (error) throw error;
}

// ============================================================
// Raw Feed Items
// ============================================================

export async function insertRawFeedItem(
  supabase: SupabaseClient,
  item: CreateRawFeedItemInput
): Promise<RawFeedItem | null> {
  const { data, error } = await supabase
    .from('raw_feed_items')
    .insert(item)
    .select()
    .single();

  // Handle unique constraint violation (duplicate url_hash)
  if (error?.code === '23505') {
    return null; // Duplicate, skip
  }
  if (error) throw error;
  return data;
}

export async function getRawFeedItemByUrlHash(
  supabase: SupabaseClient,
  urlHash: string
): Promise<RawFeedItem | null> {
  const { data, error } = await supabase
    .from('raw_feed_items')
    .select('*')
    .eq('url_hash', urlHash)
    .single();

  if (error && error.code !== 'PGRST116') throw error;
  return data;
}

export async function getPendingResolveItems(
  supabase: SupabaseClient,
  limit: number = 50
): Promise<RawFeedItem[]> {
  const { data, error } = await supabase
    .from('raw_feed_items')
    .select('*')
    .eq('resolve_status', 'pending')
    .order('fetched_at', { ascending: true })
    .limit(limit);

  if (error) throw error;
  return data || [];
}

export async function updateRawFeedItemResolved(
  supabase: SupabaseClient,
  id: string,
  canonicalUrl: string,
  canonicalUrlHash: string,
  sourceDomain: string
): Promise<void> {
  const { error } = await supabase
    .from('raw_feed_items')
    .update({
      canonical_url: canonicalUrl,
      canonical_url_hash: canonicalUrlHash,
      source_domain: sourceDomain,
      resolve_status: 'resolved',
      resolved_at: new Date().toISOString(),
    })
    .eq('id', id);

  if (error) throw error;
}

export async function updateRawFeedItemResolveFailed(
  supabase: SupabaseClient,
  id: string,
  errorMessage: string
): Promise<void> {
  const { error } = await supabase
    .from('raw_feed_items')
    .update({
      resolve_status: 'failed',
      resolve_error: errorMessage,
      resolved_at: new Date().toISOString(),
    })
    .eq('id', id);

  if (error) throw error;
}

export async function getUnclusteredItems(
  supabase: SupabaseClient,
  ticker: string,
  since: Date
): Promise<RawFeedItem[]> {
  // Step 1: Get all clustered item IDs
  // Note: Supabase JS client doesn't support nested subqueries in .not()
  // See: https://github.com/supabase/ssr/issues/105
  const { data: clusteredItems, error: clusteredError } = await supabase
    .from('cluster_items')
    .select('raw_item_id');

  if (clusteredError) throw clusteredError;

  const clusteredIds = (clusteredItems || []).map(item => item.raw_item_id);

  // Step 2: Get raw items that are resolved and not yet clustered
  const query = supabase
    .from('raw_feed_items')
    .select('*')
    .eq('ticker', ticker)
    .eq('resolve_status', 'resolved')
    .gte('published_at', since.toISOString())
    .order('published_at', { ascending: true });

  // Step 3: Exclude clustered items using proper PostgREST syntax
  // Use .filter() with raw PostgREST format: not.in.(id1,id2,...)
  if (clusteredIds.length > 0) {
    const { data, error } = await query.filter(
      'id',
      'not.in',
      `(${clusteredIds.join(',')})`
    );
    if (error) throw error;
    return data || [];
  }

  const { data, error } = await query;
  if (error) throw error;
  return data || [];
}

// ============================================================
// Event Clusters
// ============================================================

export async function createEventCluster(
  supabase: SupabaseClient,
  cluster: CreateEventClusterInput
): Promise<EventCluster> {
  const { data, error } = await supabase
    .from('event_clusters')
    .insert(cluster)
    .select()
    .single();

  if (error) throw error;
  return data;
}

export async function getRecentClusters(
  supabase: SupabaseClient,
  ticker: string,
  since: Date
): Promise<EventCluster[]> {
  const { data, error } = await supabase
    .from('event_clusters')
    .select('*')
    .eq('ticker', ticker)
    .gte('first_seen_at', since.toISOString())
    .order('first_seen_at', { ascending: false });

  if (error) throw error;
  return data || [];
}

export async function updateClusterMetadata(
  supabase: SupabaseClient,
  clusterId: string,
  updates: Partial<Pick<EventCluster, 'last_seen_at' | 'item_count' | 'source_count' | 'highest_tier' | 'representative_url'>>
): Promise<void> {
  const { error } = await supabase
    .from('event_clusters')
    .update(updates)
    .eq('cluster_id', clusterId);

  if (error) throw error;
}

export async function addItemToCluster(
  supabase: SupabaseClient,
  clusterId: string,
  rawItemId: string
): Promise<void> {
  const { error } = await supabase
    .from('cluster_items')
    .insert({ cluster_id: clusterId, raw_item_id: rawItemId });

  if (error && error.code !== '23505') throw error; // Ignore duplicate
}

// ============================================================
// Event Scores
// ============================================================

export async function upsertEventScore(
  supabase: SupabaseClient,
  score: Omit<EventScore, 'updated_at'>
): Promise<void> {
  const { error } = await supabase
    .from('event_scores')
    .upsert({
      ...score,
      updated_at: new Date().toISOString(),
    });

  if (error) throw error;
}

export async function getTopScoredClusters(
  supabase: SupabaseClient,
  tickers: string[],
  date: Date,
  limit: number = 7
): Promise<EventClusterWithScore[]> {
  const startOfDay = new Date(date);
  startOfDay.setHours(0, 0, 0, 0);
  const endOfDay = new Date(date);
  endOfDay.setHours(23, 59, 59, 999);

  // Note: Supabase JS client doesn't support ordering by joined relation columns
  // We fetch all matching clusters with scores, then sort and limit in JS
  const { data, error } = await supabase
    .from('event_clusters')
    .select(`
      *,
      score:event_scores(*)
    `)
    .in('ticker', tickers)
    .gte('first_seen_at', startOfDay.toISOString())
    .lte('first_seen_at', endOfDay.toISOString());

  if (error) throw error;

  // Transform and sort by impact_score descending
  const clustersWithScores: EventClusterWithScore[] = (data || []).map(cluster => ({
    ...cluster,
    score: cluster.score?.[0] || null,
  }));

  // Sort by impact_score (descending), null scores go to the end
  clustersWithScores.sort((a, b) => {
    const scoreA = a.score?.impact_score ?? -Infinity;
    const scoreB = b.score?.impact_score ?? -Infinity;
    return scoreB - scoreA;
  });

  return clustersWithScores.slice(0, limit);
}

// ============================================================
// Briefs
// ============================================================

export async function createBrief(
  supabase: SupabaseClient,
  brief: CreateBriefInput
): Promise<Brief> {
  const { data, error } = await supabase
    .from('briefs')
    .insert(brief)
    .select()
    .single();

  if (error) throw error;
  return data;
}

export async function getBriefByDate(
  supabase: SupabaseClient,
  date: string,
  tickerGroup: string = 'default'
): Promise<Brief | null> {
  const { data, error } = await supabase
    .from('briefs')
    .select('*')
    .eq('brief_date', date)
    .eq('ticker_group', tickerGroup)
    .single();

  if (error && error.code !== 'PGRST116') throw error;
  return data;
}

// ============================================================
// Pipeline Runs
// ============================================================

export async function startPipelineRun(
  supabase: SupabaseClient,
  input: CreatePipelineRunInput
): Promise<PipelineRun> {
  const { data, error } = await supabase
    .from('pipeline_runs')
    .insert({
      run_type: input.run_type,
      metadata: input.metadata || null,
    })
    .select()
    .single();

  if (error) throw error;
  return data;
}

export async function finishPipelineRun(
  supabase: SupabaseClient,
  id: string,
  result: {
    status: 'success' | 'failed';
    items_processed?: number;
    items_created?: number;
    errors_count?: number;
    error_message?: string;
    metadata?: Record<string, unknown>;
  }
): Promise<void> {
  const { error } = await supabase
    .from('pipeline_runs')
    .update({
      ...result,
      finished_at: new Date().toISOString(),
    })
    .eq('id', id);

  if (error) throw error;
}

export async function getRecentPipelineRuns(
  supabase: SupabaseClient,
  runType: PipelineRun['run_type'],
  limit: number = 10
): Promise<PipelineRun[]> {
  const { data, error } = await supabase
    .from('pipeline_runs')
    .select('*')
    .eq('run_type', runType)
    .order('started_at', { ascending: false })
    .limit(limit);

  if (error) throw error;
  return data || [];
}
