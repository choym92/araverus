// src/lib/supabase.ts
import { createBrowserClient } from "@supabase/ssr";
import { supabaseUrl, supabaseAnonKey } from "./config";

/**
 * Creates a Supabase client for use in Client Components.
 * Uses validated environment variables from config.
 * Each component should create its own instance to avoid session bleeding.
 */
export function createClient() {
  return createBrowserClient(supabaseUrl, supabaseAnonKey);
}
