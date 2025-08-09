'use client';

import { createClient } from '@/lib/supabase';
import { useState } from 'react';

export default function OAuthTestPage() {
  const [status, setStatus] = useState<string>('');
  const [error, setError] = useState<string>('');
  const supabase = createClient();

  const testGoogleLogin = async () => {
    setStatus('Starting Google OAuth...');
    setError('');
    
    try {
      const { data, error } = await supabase.auth.signInWithOAuth({
        provider: 'google',
        options: {
          redirectTo: `${window.location.origin}/auth/callback`,
          queryParams: {
            access_type: 'offline',
            prompt: 'consent',
          },
        },
      });

      if (error) {
        setError(`OAuth Error: ${error.message}`);
        console.error('OAuth error:', error);
      } else {
        setStatus('Redirecting to Google...');
        console.log('OAuth data:', data);
      }
    } catch (err) {
      setError(`Unexpected error: ${err}`);
      console.error('Unexpected error:', err);
    }
  };

  const checkSession = async () => {
    const { data: { session }, error } = await supabase.auth.getSession();
    
    if (error) {
      setError(`Session error: ${error.message}`);
    } else if (session) {
      setStatus(`Logged in as: ${session.user.email}`);
    } else {
      setStatus('No active session');
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-2xl mx-auto">
        <h1 className="text-3xl font-bold mb-8">OAuth Test Page</h1>
        
        <div className="bg-white p-6 rounded-lg shadow mb-6">
          <h2 className="text-xl font-semibold mb-4">Test Google OAuth</h2>
          
          <div className="space-y-4">
            <button
              onClick={testGoogleLogin}
              className="bg-blue-600 text-white px-6 py-3 rounded hover:bg-blue-700"
            >
              Sign in with Google (Manual)
            </button>
            
            <button
              onClick={checkSession}
              className="bg-green-600 text-white px-6 py-3 rounded hover:bg-green-700"
            >
              Check Current Session
            </button>
          </div>
          
          {status && (
            <div className="mt-4 p-4 bg-blue-50 rounded">
              <p className="text-blue-800">Status: {status}</p>
            </div>
          )}
          
          {error && (
            <div className="mt-4 p-4 bg-red-50 rounded">
              <p className="text-red-800">Error: {error}</p>
            </div>
          )}
        </div>
        
        <div className="bg-white p-6 rounded-lg shadow">
          <h2 className="text-xl font-semibold mb-4">Debug Info</h2>
          <div className="text-sm space-y-2">
            <p><strong>Supabase URL:</strong> {process.env.NEXT_PUBLIC_SUPABASE_URL}</p>
            <p><strong>Current Origin:</strong> {typeof window !== 'undefined' ? window.location.origin : 'SSR'}</p>
            <p><strong>Callback URL:</strong> {typeof window !== 'undefined' ? `${window.location.origin}/auth/callback` : 'SSR'}</p>
          </div>
        </div>
      </div>
    </div>
  );
}