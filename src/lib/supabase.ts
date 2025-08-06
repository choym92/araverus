// src/lib/supabase.ts
import { createBrowserClient } from "@supabase/ssr";

/**
 * `supabase` – a ready-to-use client that works in
 * both Client Components and simple API routes.
 */
export const supabase = createBrowserClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
);
