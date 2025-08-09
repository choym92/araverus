'use client';

import { useAuth } from '@/hooks/useAuth';
import { useState } from 'react';

export default function CheckAdminPage() {
  const { user, profile, loading, error, isAdmin, supabase } = useAuth();
  const [profileData, setProfileData] = useState<any>(null);

  const checkProfile = async () => {
    if (!user) {
      alert('No user logged in');
      return;
    }
    
    const { data, error } = await supabase
      .from('user_profiles')
      .select('*')
      .eq('id', user.id)
      .single();
    
    setProfileData(data);
    console.log('Profile from DB:', data);
    
    if (error) {
      alert(`Error: ${error.message}`);
    } else if (!data) {
      alert('No profile found - need to create one');
    } else {
      alert(`Profile found! Role: ${data.role}`);
    }
  };

  const makeAdmin = async () => {
    if (!user) {
      alert('No user logged in');
      return;
    }
    
    const { data, error } = await supabase
      .from('user_profiles')
      .upsert({
        id: user.id,
        email: user.email,
        role: 'admin',
        full_name: 'Paul Cho'
      })
      .select()
      .single();
    
    if (error) {
      alert(`Error: ${error.message}`);
    } else {
      alert('Admin role set! Refresh the page.');
      setProfileData(data);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-2xl mx-auto">
        <h1 className="text-3xl font-bold mb-8">Admin Status Check</h1>
        
        <div className="bg-white p-6 rounded-lg shadow mb-6">
          <h2 className="text-xl font-semibold mb-4">Current Status</h2>
          <div className="space-y-2">
            <p><strong>Loading:</strong> {loading ? 'Yes' : 'No'}</p>
            <p><strong>User Email:</strong> {user?.email || 'Not logged in'}</p>
            <p><strong>User ID:</strong> {user?.id || 'N/A'}</p>
            <p><strong>Profile Role (from hook):</strong> {profile?.role || 'No profile'}</p>
            <p><strong>Is Admin (computed):</strong> {isAdmin ? 'YES ✅' : 'NO ❌'}</p>
            <p><strong>Error:</strong> {error || 'None'}</p>
          </div>
        </div>

        <div className="bg-white p-6 rounded-lg shadow mb-6">
          <h2 className="text-xl font-semibold mb-4">Profile from Database</h2>
          <pre className="bg-gray-100 p-4 rounded text-xs overflow-auto">
            {profileData ? JSON.stringify(profileData, null, 2) : 'Click "Check Profile" to load'}
          </pre>
        </div>

        <div className="flex gap-4">
          <button
            onClick={checkProfile}
            className="bg-blue-600 text-white px-6 py-3 rounded hover:bg-blue-700"
          >
            Check Profile in DB
          </button>
          
          <button
            onClick={makeAdmin}
            className="bg-green-600 text-white px-6 py-3 rounded hover:bg-green-700"
          >
            Make Me Admin
          </button>
          
          <button
            onClick={() => window.location.reload()}
            className="bg-gray-600 text-white px-6 py-3 rounded hover:bg-gray-700"
          >
            Refresh Page
          </button>
          
          <button
            onClick={() => window.location.href = '/admin'}
            className="bg-purple-600 text-white px-6 py-3 rounded hover:bg-purple-700"
          >
            Try /admin
          </button>
        </div>
      </div>
    </div>
  );
}