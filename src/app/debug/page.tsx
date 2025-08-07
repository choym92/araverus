'use client';

import { useAuth } from '@/hooks/useAuth';

export default function DebugPage() {
  const { user, profile, loading, error, isAdmin, supabase, refreshProfile } = useAuth();

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-3xl font-bold mb-8">Debug Information</h1>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Environment Check */}
          <div className="bg-white p-6 rounded-lg shadow">
            <h2 className="text-xl font-semibold mb-4">Environment Variables</h2>
            <div className="space-y-2 text-sm">
              <p>
                <strong>Supabase URL:</strong> {' '}
                <span className={process.env.NEXT_PUBLIC_SUPABASE_URL ? 'text-green-600' : 'text-red-600'}>
                  {process.env.NEXT_PUBLIC_SUPABASE_URL ? '✓ Set' : '✗ Missing'}
                </span>
              </p>
              <p>
                <strong>Anon Key:</strong> {' '}
                <span className={process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ? 'text-green-600' : 'text-red-600'}>
                  {process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ? '✓ Set' : '✗ Missing'}
                </span>
              </p>
              <p className="text-xs text-gray-500 mt-2">
                URL: {process.env.NEXT_PUBLIC_SUPABASE_URL || 'Not set'}
              </p>
            </div>
          </div>

          {/* Auth State */}
          <div className="bg-white p-6 rounded-lg shadow">
            <h2 className="text-xl font-semibold mb-4">Authentication State</h2>
            <div className="space-y-2 text-sm">
              <p><strong>Loading:</strong> {loading ? '✓ Yes' : '✗ No'}</p>
              <p><strong>Error:</strong> {error || 'None'}</p>
              <p><strong>User:</strong> {user ? '✓ Logged in' : '✗ Not logged in'}</p>
              <p><strong>Is Admin:</strong> {isAdmin ? '✓ Yes' : '✗ No'}</p>
              <p><strong>Profile Role:</strong> {profile?.role || 'No profile'}</p>
            </div>
          </div>

          {/* User Details */}
          <div className="bg-white p-6 rounded-lg shadow">
            <h2 className="text-xl font-semibold mb-4">User Details</h2>
            <pre className="text-xs bg-gray-100 p-4 rounded overflow-auto">
              {user ? JSON.stringify(user, null, 2) : 'No user logged in'}
            </pre>
          </div>

          {/* Profile Details */}
          <div className="bg-white p-6 rounded-lg shadow">
            <h2 className="text-xl font-semibold mb-4">Profile Details</h2>
            <pre className="text-xs bg-gray-100 p-4 rounded overflow-auto">
              {profile ? JSON.stringify(profile, null, 2) : 'No profile data'}
            </pre>
          </div>
        </div>

        {/* Quick Actions */}
        <div className="mt-8 bg-white p-6 rounded-lg shadow">
          <h2 className="text-xl font-semibold mb-4">Quick Actions</h2>
          <div className="flex gap-4">
            <button
              onClick={() => window.location.href = '/login'}
              className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
            >
              Go to Login
            </button>
            <button
              onClick={() => window.location.href = '/admin'}
              className="bg-green-600 text-white px-4 py-2 rounded hover:bg-green-700"
            >
              Try Admin
            </button>
            <button
              onClick={async () => {
                try {
                  const { data, error } = await supabase.from('user_profiles').select('*').limit(1);
                  console.log('DB Test:', { data, error });
                  alert('Check console for DB test results');
                } catch (err) {
                  console.error('DB Test Error:', err);
                  alert('DB test failed - check console');
                }
              }}
              className="bg-purple-600 text-white px-4 py-2 rounded hover:bg-purple-700"
            >
              Test DB Connection
            </button>
            <button
              onClick={async () => {
                try {
                  // Check if profile exists for current user
                  if (user) {
                    const { data, error } = await supabase
                      .from('user_profiles')
                      .select('*')
                      .eq('id', user.id)
                      .single();
                    console.log('Profile Check:', { data, error });
                    alert(`Profile Check: ${data ? `Found - Role: ${data.role}` : `Not found - Error: ${error?.message}`}`);
                  } else {
                    alert('No user logged in');
                  }
                } catch (err) {
                  console.error('Profile Check Error:', err);
                  alert('Profile check failed - check console');
                }
              }}
              className="bg-orange-600 text-white px-4 py-2 rounded hover:bg-orange-700"
            >
              Check My Profile
            </button>
            <button
              onClick={() => {
                window.location.reload();
              }}
              className="bg-gray-600 text-white px-4 py-2 rounded hover:bg-gray-700"
            >
              Refresh Page
            </button>
            <button
              onClick={async () => {
                await refreshProfile();
                alert('Profile refreshed! Check if admin status changed.');
              }}
              className="bg-red-600 text-white px-4 py-2 rounded hover:bg-red-700"
            >
              Refresh Profile
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}