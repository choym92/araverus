'use client';

import { useState } from 'react';
import { useAuth } from '@/hooks/useAuth';

export default function SetupAdminPage() {
  const { user } = useAuth();
  const [status, setStatus] = useState<string>('');
  const [loading, setLoading] = useState(false);

  const setupAdmin = async () => {
    setLoading(true);
    setStatus('Setting up admin profile...');
    
    try {
      const res = await fetch('/api/admin/setup', {
        method: 'POST'
      });
      
      const data = await res.json();
      
      if (res.ok) {
        setStatus('✅ Admin profile set up successfully!');
      } else {
        setStatus(`❌ Error: ${data.error}`);
      }
    } catch (error) {
      setStatus(`❌ Failed: ${error}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="bg-white p-8 rounded-lg shadow-lg max-w-md w-full">
        <h1 className="text-2xl font-bold mb-4">Admin Setup</h1>
        
        {user ? (
          <>
            <p className="mb-4 text-gray-600">
              Logged in as: <strong>{user.email}</strong>
            </p>
            
            {user.email === 'choym92@gmail.com' ? (
              <>
                <button
                  onClick={setupAdmin}
                  disabled={loading}
                  className="w-full px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
                >
                  {loading ? 'Setting up...' : 'Set Up Admin Profile'}
                </button>
                
                {status && (
                  <div className="mt-4 p-3 bg-gray-100 rounded-md">
                    {status}
                  </div>
                )}
              </>
            ) : (
              <p className="text-red-600">
                This account is not authorized for admin access.
              </p>
            )}
          </>
        ) : (
          <p className="text-gray-600">
            Please log in first.
          </p>
        )}
      </div>
    </div>
  );
}