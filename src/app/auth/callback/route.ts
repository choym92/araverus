import { createClient } from '@/lib/supabase-server';
import { NextRequest, NextResponse } from 'next/server';

export async function GET(request: NextRequest) {
  console.log('AUTH CALLBACK HIT');
  console.log('Full URL:', request.url);
  
  const { searchParams } = new URL(request.url);
  const code = searchParams.get('code');
  const next = searchParams.get('next') ?? '/dashboard';
  
  console.log('Auth code:', code ? 'Present' : 'Missing');
  console.log('Next URL:', next);

  if (code) {
    try {
      const supabase = await createClient();
      console.log('Exchanging code for session...');
      
      const { data, error } = await supabase.auth.exchangeCodeForSession(code);
      
      if (error) {
        console.error('Exchange code error:', error);
        const errorUrl = new URL('/auth/auth-code-error', request.url);
        errorUrl.searchParams.set('error', error.message);
        return NextResponse.redirect(errorUrl);
      }
      
      console.log('Session created successfully');
      console.log('User:', data.session?.user.email);
      
      // Redirect to dashboard on success
      const redirectUrl = new URL('/dashboard', request.url);
      return NextResponse.redirect(redirectUrl);
      
    } catch (err) {
      console.error('Callback error:', err);
      const errorUrl = new URL('/auth/auth-code-error', request.url);
      errorUrl.searchParams.set('error', 'Callback processing failed');
      return NextResponse.redirect(errorUrl);
    }
  }

  console.log('No code provided in callback');
  const errorUrl = new URL('/auth/auth-code-error', request.url);
  errorUrl.searchParams.set('error', 'No authorization code provided');
  return NextResponse.redirect(errorUrl);
}