// src/lib/supabase-server.ts
import { createServerClient } from '@supabase/ssr'
import { cookies } from 'next/headers'
import { supabaseUrl, supabaseAnonKey, supabaseServiceRoleKey } from './config'

export async function createClient() {
  const cookieStore = await cookies()

  return createServerClient(
    supabaseUrl,
    supabaseAnonKey,
    {
      cookies: {
        getAll() {
          return cookieStore.getAll()
        },
        setAll(cookiesToSet) {
          try {
            cookiesToSet.forEach(({ name, value, options }) =>
              cookieStore.set(name, value, options)
            )
          } catch (error) {
            // Log cookie errors in development for debugging
            if (process.env.NODE_ENV === 'development') {
              console.error('Cookie setting error in server component:', error);
            }
            // In production, this can be ignored if middleware is handling session refresh
            // but we should track these errors for monitoring
            if (process.env.NODE_ENV === 'production') {
              // TODO: Add production error tracking (e.g., Sentry, DataDog)
              console.warn('Cookie operation failed in server component');
            }
          }
        },
      },
    }
  )
}

// For API routes that don't need user session
export function createServiceClient() {
  if (!supabaseServiceRoleKey) {
    throw new Error(
      'SUPABASE_SERVICE_ROLE_KEY is required for service client operations'
    );
  }

  return createServerClient(
    supabaseUrl,
    supabaseServiceRoleKey,
    {
      cookies: {
        getAll() {
          return []
        },
        setAll() {
          // No-op for service client
        },
      },
    }
  )
}