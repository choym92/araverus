import { createServerClient } from '@supabase/ssr'
import { NextResponse, type NextRequest } from 'next/server'

// Known good bots (allowed): Googlebot, Bingbot, GPTBot, ClaudeBot, Applebot,
// FacebookExternalHit, Twitterbot, LinkedInBot, Slurp, DuckDuckBot, vercel-screenshot

// Known malicious / aggressive bots — block
const BLOCKED_BOTS = /SemrushBot|AhrefsBot|DotBot|MJ12bot|BLEXBot|PetalBot|YandexBot|Bytespider|MegaIndex|Sogou|Baiduspider|DataForSeoBot|serpstatbot|Seekport|ZoominfoBot|BrightBot/i

export async function middleware(request: NextRequest) {
  const ua = request.headers.get('user-agent') || ''

  // Block known bad bots
  if (BLOCKED_BOTS.test(ua)) {
    return new NextResponse(null, { status: 403 })
  }

  // Block suspicious no-UA requests to non-API paths
  if (!ua && !request.nextUrl.pathname.startsWith('/api')) {
    return new NextResponse(null, { status: 403 })
  }

  let supabaseResponse = NextResponse.next({
    request,
  })

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll()
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value }) =>
            request.cookies.set(name, value),
          )
          supabaseResponse = NextResponse.next({
            request,
          })
          cookiesToSet.forEach(({ name, value, options }) =>
            supabaseResponse.cookies.set(name, value, options),
          )
        },
      },
    },
  )

  // Refresh session — must call getUser() not getSession()
  // getUser() contacts the Supabase Auth server, which guarantees
  // the token is valid and refreshes it if needed
  await supabase.auth.getUser()

  return supabaseResponse
}

export const config = {
  matcher: [
    // Match all paths except static files, images, and auth routes
    '/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico)$).*)',
  ],
}
