import { NextRequest, NextResponse } from 'next/server'
import { createServiceClient } from '@/lib/supabase-server'
import { NewsService } from '@/lib/news-service'

const VALID_CATEGORIES = new Set([
  'BUSINESS_MARKETS', 'TECH', 'ECONOMY', 'WORLD', 'POLITICS',
])

export async function GET(request: NextRequest) {
  const { searchParams } = request.nextUrl
  const category = searchParams.get('category') || undefined
  const offset = Math.max(0, parseInt(searchParams.get('offset') || '0', 10) || 0)
  const limit = Math.min(50, Math.max(1, parseInt(searchParams.get('limit') || '20', 10) || 20))

  if (category && !VALID_CATEGORIES.has(category)) {
    return NextResponse.json({ error: 'Invalid category' }, { status: 400 })
  }

  const supabase = createServiceClient()
  const service = new NewsService(supabase)

  // Fetch one extra to determine hasMore
  const items = await service.getNewsItems({ category, offset, limit: limit + 1 })
  const hasMore = items.length > limit
  const result = hasMore ? items.slice(0, limit) : items

  return NextResponse.json(
    { items: result, hasMore },
    {
      headers: {
        'Cache-Control': 'public, s-maxage=1800, stale-while-revalidate=3600',
      },
    },
  )
}
