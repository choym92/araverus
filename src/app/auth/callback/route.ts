import { createClient } from '@/lib/supabase-server';
import { NextRequest, NextResponse } from 'next/server';

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const code = searchParams.get('code');
  const next = searchParams.get('next') ?? '/dashboard';

  if (code) {
    const supabase = await createClient();
    const { error } = await supabase.auth.exchangeCodeForSession(code);
    
    if (!error) {
      // Successfully authenticated - redirect to dashboard
      const redirectUrl = new URL(next, request.url);
      return NextResponse.redirect(redirectUrl);
    } else {
      console.error('OAuth callback error:', error);
      // Redirect to error page with error details
      const errorUrl = new URL('/auth/auth-code-error', request.url);
      errorUrl.searchParams.set('error', error.message);
      return NextResponse.redirect(errorUrl);
    }
  }

  // No code provided - redirect to error page
  const errorUrl = new URL('/auth/auth-code-error', request.url);
  errorUrl.searchParams.set('error', 'No authorization code provided');
  return NextResponse.redirect(errorUrl);
}