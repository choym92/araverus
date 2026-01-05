// src/app/api/finance/resolve/route.ts
// API endpoint for resolving Google News redirect URLs
// Created: 2025-01-05
//
// Called by cron job to process pending URL resolutions.
// Requires CRON_SECRET for authentication.

import { NextRequest, NextResponse } from 'next/server';
import { createServiceClient } from '@/lib/supabase-server';
import { startPipelineRun, finishPipelineRun } from '@/lib/finance/db';
import { processResolveQueue } from '@/lib/finance/feeds/resolver';

// ============================================================
// Authentication Helper
// ============================================================

function verifyCronSecret(request: NextRequest): boolean {
  const cronSecret = process.env.CRON_SECRET;

  if (!cronSecret) {
    console.error('[resolve] CRON_SECRET not configured');
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

  // Verify CRON_SECRET authentication
  if (!verifyCronSecret(request)) {
    return NextResponse.json(
      { error: 'Unauthorized' },
      { status: 401 }
    );
  }

  // Get optional limit from query string (default: 50)
  const { searchParams } = new URL(request.url);
  const limit = Math.min(
    parseInt(searchParams.get('limit') || '50', 10),
    200 // Max 200 to prevent timeout
  );

  const supabase = createServiceClient();
  let pipelineRun: { id: string } | null = null;

  try {
    // 10.8: Start pipeline run logging
    pipelineRun = await startPipelineRun(supabase, { run_type: 'resolve' });

    // 10.7: Process the resolve queue
    const result = await processResolveQueue(supabase, limit);

    // 10.8: Finish pipeline run logging (success)
    await finishPipelineRun(supabase, pipelineRun.id, {
      status: 'success',
      items_processed: result.resolved + result.failed,
      items_created: result.resolved,
      errors_count: result.failed,
      metadata: {
        resolved: result.resolved,
        failed: result.failed,
        remaining: result.remaining,
      },
    });

    // 10.9: Return stats
    return NextResponse.json({
      success: true,
      stats: {
        resolved: result.resolved,
        failed: result.failed,
        remaining: result.remaining,
        duration: Date.now() - startTime,
      },
    });
  } catch (err) {
    const errorMessage = err instanceof Error ? err.message : String(err);
    console.error('[resolve] Fatal error:', errorMessage);

    // Log failure
    if (pipelineRun) {
      try {
        await finishPipelineRun(supabase, pipelineRun.id, {
          status: 'failed',
          error_message: errorMessage,
        });
      } catch (logErr) {
        console.error('[resolve] Failed to log pipeline failure:', logErr);
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
