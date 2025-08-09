import { createServerClient } from '@supabase/ssr'
import { NextResponse, type NextRequest } from 'next/server'

export async function middleware(request: NextRequest) {
  let response = NextResponse.next({
    request: {
      headers: request.headers,
    },
  })

  // Validate environment variables
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

  if (!supabaseUrl || !supabaseAnonKey) {
    // Log configuration errors only in development
    if (process.env.NODE_ENV === 'development') {
      console.error('Missing Supabase environment variables in middleware');
    }
    // Return generic error in production to avoid config exposure
    return NextResponse.json(
      { error: 'Service temporarily unavailable' },
      { status: 503 }
    );
  }

  const supabase = createServerClient(
    supabaseUrl,
    supabaseAnonKey,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll()
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value, options }) => {
            response.cookies.set(name, value, options)
          })
        },
      },
    }
  )

  // Only check auth for protected routes to avoid timeouts
  const isProtectedRoute = request.nextUrl.pathname.startsWith('/dashboard') || 
                          request.nextUrl.pathname.startsWith('/admin')
  const isLoginRoute = request.nextUrl.pathname === '/login'

  if (isProtectedRoute || isLoginRoute) {
    try {
      // Add timeout to prevent middleware blocking
      const authPromise = supabase.auth.getUser()
      const timeoutPromise = new Promise((_, reject) => 
        setTimeout(() => reject(new Error('Auth timeout')), 2000)
      )
      
      const { data: { user }, error } = await Promise.race([
        authPromise, 
        timeoutPromise
      ]) as Awaited<typeof authPromise>

      if (isProtectedRoute && (!user || error)) {
        return NextResponse.redirect(new URL('/login', request.url))
      }

      if (isLoginRoute && user && !error) {
        return NextResponse.redirect(new URL('/dashboard', request.url))
      }
    } catch (err) {
      // If auth check fails, allow through but log the issue
      console.warn('Middleware auth check failed:', err)
      if (isProtectedRoute) {
        return NextResponse.redirect(new URL('/login', request.url))
      }
    }
  }

  return response
}

export const config = {
  matcher: [
    /*
     * Match all request paths except for the ones starting with:
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     * Feel free to modify this pattern to include more paths.
     */
    '/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)',
  ],
}