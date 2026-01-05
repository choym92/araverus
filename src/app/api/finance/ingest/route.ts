// src/app/api/finance/ingest/route.ts
// API endpoint for ingesting SEC and Google News feeds
// Created: 2025-01-05
//
// Called by cron job to fetch and store new feed items.
// Requires CRON_SECRET for authentication.

import { NextRequest, NextResponse } from 'next/server';
import { createServiceClient } from '@/lib/supabase-server';
import { getActiveTickers, startPipelineRun, finishPipelineRun } from '@/lib/finance/db';
import { fetchSecFilings } from '@/lib/finance/feeds/sec';
import { fetchGoogleNews } from '@/lib/finance/feeds/googleNews';

// ============================================================
// Authentication Helper
// ============================================================

function verifyCronSecret(request: NextRequest): boolean {
  const cronSecret = process.env.CRON_SECRET;

  if (!cronSecret) {
    console.error('[ingest] CRON_SECRET not configured');
    return false;
  }

  const authHeader = request.headers.get('Authorization');
  return authHeader === `Bearer ${cronSecret}`;
}

// ============================================================
// POST Handler
// ============================================================

export async function POST(request: NextRequest) {
  const startTime = Date.now();

  // 10.2: Verify CRON_SECRET authentication
  if (!verifyCronSecret(request)) {
    return NextResponse.json(
      { error: 'Unauthorized' },
      { status: 401 }
    );
  }

  // 10.3: Fetch feeds and insert items
  const supabase = createServiceClient();
  let pipelineRun: { id: string } | null = null;

  try {
    // 10.4: Start pipeline run logging
    pipelineRun = await startPipelineRun(supabase, { run_type: 'ingest' });

    // Get active tickers from database
    const tickers = await getActiveTickers(supabase);

    if (tickers.length === 0) {
      // Log empty run
      await finishPipelineRun(supabase, pipelineRun.id, {
        status: 'success',
        items_processed: 0,
        items_created: 0,
        metadata: { message: 'No active tickers found' },
      });

      return NextResponse.json({
        success: true,
        message: 'No active tickers found',
        stats: {
          secItems: 0,
          newsItems: 0,
          resolveQueueSize: 0,
          duration: Date.now() - startTime,
        },
      });
    }

    // Track stats
    let secItemsFetched = 0;
    let secItemsInserted = 0;
    let newsItemsFetched = 0;
    let newsItemsInserted = 0;
    const errors: string[] = [];

    // Fetch SEC filings for each ticker
    for (const ticker of tickers) {
      try {
        const result = await fetchSecFilings(
          supabase,
          ticker.ticker,
          ticker.cik
        );
        secItemsFetched += result.itemsFetched;
        secItemsInserted += result.itemsInserted;
        if (result.errors.length > 0) {
          errors.push(...result.errors.map(e => `[SEC/${ticker.ticker}] ${e}`));
        }
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        errors.push(`[SEC/${ticker.ticker}] ${msg}`);
      }
    }

    // Fetch Google News for each ticker
    for (const ticker of tickers) {
      try {
        const result = await fetchGoogleNews(supabase, ticker);
        newsItemsFetched += result.itemsFetched;
        newsItemsInserted += result.itemsInserted;
        if (result.errors.length > 0) {
          errors.push(...result.errors.map(e => `[News/${ticker.ticker}] ${e}`));
        }
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        errors.push(`[News/${ticker.ticker}] ${msg}`);
      }
    }

    // Count items pending resolution
    const { count: resolveQueueSize } = await supabase
      .from('raw_feed_items')
      .select('*', { count: 'exact', head: true })
      .eq('resolve_status', 'pending');

    // 10.4: Finish pipeline run logging (success)
    await finishPipelineRun(supabase, pipelineRun.id, {
      status: 'success',
      items_processed: secItemsFetched + newsItemsFetched,
      items_created: secItemsInserted + newsItemsInserted,
      errors_count: errors.length,
      error_message: errors.length > 0 ? errors[0] : undefined,
      metadata: {
        tickers: tickers.map(t => t.ticker),
        secItemsFetched,
        secItemsInserted,
        newsItemsFetched,
        newsItemsInserted,
        resolveQueueSize: resolveQueueSize || 0,
      },
    });

    return NextResponse.json({
      success: true,
      stats: {
        tickers: tickers.map(t => t.ticker),
        secItems: secItemsInserted,
        newsItems: newsItemsInserted,
        resolveQueueSize: resolveQueueSize || 0,
        errors: errors.length > 0 ? errors : undefined,
        duration: Date.now() - startTime,
      },
    });
  } catch (err) {
    const errorMessage = err instanceof Error ? err.message : String(err);
    console.error('[ingest] Fatal error:', errorMessage);

    // 10.4: Finish pipeline run logging (failed)
    if (pipelineRun) {
      try {
        await finishPipelineRun(supabase, pipelineRun.id, {
          status: 'failed',
          error_message: errorMessage,
        });
      } catch (logErr) {
        console.error('[ingest] Failed to log pipeline failure:', logErr);
      }
    }

    return NextResponse.json(
      {
        success: false,
        error: errorMessage,
        duration: Date.now() - startTime,
      },
      { status: 500 }
    );
  }
}
