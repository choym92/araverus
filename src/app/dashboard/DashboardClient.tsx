'use client';

import { useAuth } from '@/hooks/useAuth';
import { useRouter } from 'next/navigation';
import { useState } from 'react';

export default function DashboardClient() {
  const router = useRouter();
  const { user, signOut } = useAuth();
  const [isSigningOut, setIsSigningOut] = useState(false);

  const handleSignOut = async () => {
    if (isSigningOut) return;
    setIsSigningOut(true);

    await signOut();
    router.push('/');
  };

  const formatLastSignIn = (timestamp: string | null | undefined) => {
    if (!timestamp) return 'Never';
    try {
      return new Date(timestamp).toLocaleString();
    } catch {
      return 'Invalid date';
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-4xl mx-auto p-8">
        <div className="bg-white rounded-lg shadow p-6">
          <h1 className="text-2xl font-bold mb-4">Welcome to Your Dashboard</h1>
          <p className="text-gray-600 mb-6">You are successfully logged in!</p>

          <div className="bg-gray-50 p-4 rounded mb-6">
            <p><strong>Email:</strong> {user?.email}</p>
            <p><strong>User ID:</strong> {user?.id}</p>
            <p><strong>Last Sign In:</strong> {formatLastSignIn(user?.last_sign_in_at)}</p>
          </div>

          <button
            onClick={handleSignOut}
            disabled={isSigningOut}
            className="bg-red-600 text-white px-4 py-2 rounded hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isSigningOut ? 'Signing out...' : 'Sign Out'}
          </button>
        </div>
      </div>
    </div>
  );
}
