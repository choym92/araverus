'use client';

import { useEffect, useState } from 'react';
import { getBaseUrl, getEnvironment, isProduction, isDevelopment } from '@/lib/config/environment';
import { useAuth } from '@/hooks/useAuth';

export default function TestEnvironmentPage() {
  const { user, supabase } = useAuth();
  const [clientInfo, setClientInfo] = useState<any>(null);

  useEffect(() => {
    // Client-side environment detection
    setClientInfo({
      baseUrl: getBaseUrl(),
      environment: getEnvironment(),
      isProduction: isProduction(),
      isDevelopment: isDevelopment(),
      windowOrigin: typeof window !== 'undefined' ? window.location.origin : 'N/A',
      nodeEnv: process.env.NODE_ENV,
      vercelEnv: process.env.VERCEL_ENV,
      vercelUrl: process.env.VERCEL_URL,
      publicBaseUrl: process.env.NEXT_PUBLIC_BASE_URL,
      supabaseUrl: process.env.NEXT_PUBLIC_SUPABASE_URL,
    });
  }, []);

  const testAuthRedirect = async () => {
    const { data, error } = await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: {
        redirectTo: `${getBaseUrl()}/test-env`,
        skipBrowserRedirect: true, // Just get the URL, don't redirect
      }
    });
    
    if (data?.url) {
      alert(`Auth would redirect to:\n${data.url}\n\nCallback URL: ${getBaseUrl()}/test-env`);
    }
    if (error) {
      alert(`Error: ${error.message}`);
    }
  };

  return (
    <div className="min-h-screen p-8 bg-gray-50">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-3xl font-bold mb-8">Environment Test Page</h1>
        
        {/* Current User */}
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <h2 className="text-xl font-semibold mb-4">Authentication Status</h2>
          <div className="space-y-2">
            <p><strong>Logged in:</strong> {user ? 'Yes' : 'No'}</p>
            {user && (
              <>
                <p><strong>Email:</strong> {user.email}</p>
                <p><strong>ID:</strong> {user.id}</p>
              </>
            )}
          </div>
        </div>

        {/* Environment Info */}
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <h2 className="text-xl font-semibold mb-4">Environment Configuration</h2>
          {clientInfo ? (
            <div className="space-y-2 font-mono text-sm">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-gray-600">Environment:</p>
                  <p className={`font-bold ${clientInfo.environment === 'production' ? 'text-red-600' : 'text-green-600'}`}>
                    {clientInfo.environment}
                  </p>
                </div>
                <div>
                  <p className="text-gray-600">Node Environment:</p>
                  <p className="font-bold">{clientInfo.nodeEnv}</p>
                </div>
                <div>
                  <p className="text-gray-600">Base URL:</p>
                  <p className="font-bold text-blue-600 break-all">{clientInfo.baseUrl}</p>
                </div>
                <div>
                  <p className="text-gray-600">Window Origin:</p>
                  <p className="font-bold break-all">{clientInfo.windowOrigin}</p>
                </div>
                <div>
                  <p className="text-gray-600">Is Production:</p>
                  <p className="font-bold">{clientInfo.isProduction ? '✅ Yes' : '❌ No'}</p>
                </div>
                <div>
                  <p className="text-gray-600">Is Development:</p>
                  <p className="font-bold">{clientInfo.isDevelopment ? '✅ Yes' : '❌ No'}</p>
                </div>
              </div>
              
              <div className="mt-4 pt-4 border-t">
                <p className="text-gray-600 mb-2">Environment Variables:</p>
                <div className="bg-gray-100 p-3 rounded text-xs">
                  <p><strong>VERCEL_ENV:</strong> {clientInfo.vercelEnv || 'undefined'}</p>
                  <p><strong>VERCEL_URL:</strong> {clientInfo.vercelUrl || 'undefined'}</p>
                  <p><strong>NEXT_PUBLIC_BASE_URL:</strong> {clientInfo.publicBaseUrl || 'undefined'}</p>
                  <p><strong>SUPABASE_URL:</strong> {clientInfo.supabaseUrl ? '✅ Set' : '❌ Not set'}</p>
                </div>
              </div>
            </div>
          ) : (
            <p>Loading...</p>
          )}
        </div>

        {/* Test Actions */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold mb-4">Test Actions</h2>
          <div className="space-y-4">
            <button
              onClick={testAuthRedirect}
              className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
            >
              Test Auth Redirect URL
            </button>
            
            <div className="text-sm text-gray-600">
              <p>Click to see what URL Supabase would use for authentication callback.</p>
              <p>This should match your current environment.</p>
            </div>
          </div>
        </div>

        {/* Instructions */}
        <div className="mt-8 p-6 bg-yellow-50 border border-yellow-200 rounded-lg">
          <h3 className="font-semibold mb-2">🧪 How to Test the Workflow:</h3>
          <ol className="list-decimal list-inside space-y-2 text-sm">
            <li>Access this page from different environments:
              <ul className="list-disc list-inside ml-4 mt-1">
                <li><code>http://localhost:3000/test-env</code> (local)</li>
                <li><code>https://araverus-*.vercel.app/test-env</code> (preview)</li>
                <li><code>https://chopaul.com/test-env</code> (production)</li>
              </ul>
            </li>
            <li>Check that the environment detection is correct</li>
            <li>Test the auth redirect button - it should use the current domain</li>
            <li>Try logging in from each environment</li>
          </ol>
        </div>
      </div>
    </div>
  );
}