// src/lib/config.ts

interface Config {
  supabaseUrl: string;
  supabaseAnonKey: string;
  supabaseServiceRoleKey?: string; // Optional, only for server-side admin operations
}

function validateConfig(): Config {
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  const supabaseServiceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY;

  // Validate required environment variables
  if (!supabaseUrl) {
    throw new Error(
      'Missing required environment variable: NEXT_PUBLIC_SUPABASE_URL'
    );
  }

  if (!supabaseAnonKey) {
    throw new Error(
      'Missing required environment variable: NEXT_PUBLIC_SUPABASE_ANON_KEY'
    );
  }

  // Validate URL format
  try {
    new URL(supabaseUrl);
  } catch {
    throw new Error(
      'Invalid NEXT_PUBLIC_SUPABASE_URL format. Must be a valid URL.'
    );
  }

  // Validate that it looks like a Supabase URL
  if (!supabaseUrl.includes('.supabase.co')) {
    throw new Error(
      'NEXT_PUBLIC_SUPABASE_URL does not appear to be a valid Supabase URL'
    );
  }

  // Validate anon key format (should be a JWT)
  if (!supabaseAnonKey.startsWith('eyJ')) {
    throw new Error(
      'NEXT_PUBLIC_SUPABASE_ANON_KEY does not appear to be a valid JWT token'
    );
  }

  // Validate service role key if present
  if (supabaseServiceRoleKey && !supabaseServiceRoleKey.startsWith('eyJ')) {
    throw new Error(
      'SUPABASE_SERVICE_ROLE_KEY does not appear to be a valid JWT token'
    );
  }

  return {
    supabaseUrl,
    supabaseAnonKey,
    supabaseServiceRoleKey,
  };
}

// Export the validated config
export const config = validateConfig();

// Export individual values for convenience
export const {
  supabaseUrl,
  supabaseAnonKey,
  supabaseServiceRoleKey,
} = config;