// Environment configuration helper
export const getBaseUrl = () => {
  // In production, always use chopaul.com
  if (process.env.NODE_ENV === 'production' && process.env.NEXT_PUBLIC_BASE_URL) {
    return process.env.NEXT_PUBLIC_BASE_URL;
  }
  
  // For Vercel preview deployments
  if (process.env.VERCEL_URL) {
    return `https://${process.env.VERCEL_URL}`;
  }
  
  // For local development
  return process.env.NEXT_PUBLIC_BASE_URL || 'http://localhost:3000';
};

export const getAuthCallbackUrl = () => {
  const baseUrl = getBaseUrl();
  return `${baseUrl}/auth/callback`;
};

export const isProduction = () => {
  return process.env.NODE_ENV === 'production' && 
         process.env.NEXT_PUBLIC_BASE_URL?.includes('chopaul.com');
};

export const isDevelopment = () => {
  return process.env.NODE_ENV === 'development' || 
         !process.env.NEXT_PUBLIC_BASE_URL?.includes('chopaul.com');
};

// Get environment name for debugging
export const getEnvironment = () => {
  if (isProduction()) return 'production';
  if (process.env.VERCEL_URL) return 'preview';
  return 'development';
};

// Supabase config with environment awareness
export const supabaseConfig = {
  url: process.env.NEXT_PUBLIC_SUPABASE_URL!,
  anonKey: process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
  serviceRoleKey: process.env.SUPABASE_SERVICE_ROLE_KEY,
  environment: getEnvironment(),
};