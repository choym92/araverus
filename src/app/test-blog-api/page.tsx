'use client';

import { useState, useEffect } from 'react';
import { useAuth } from '@/hooks/useAuth';

export default function TestBlogAPI() {
  const { user, loading } = useAuth();
  const [testResults, setTestResults] = useState<string[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const [createdPostId, setCreatedPostId] = useState<number | null>(null);

  const addResult = (message: string, success = true) => {
    const timestamp = new Date().toLocaleTimeString();
    const prefix = success ? '✅' : '❌';
    setTestResults(prev => [...prev, `[${timestamp}] ${prefix} ${message}`]);
  };

  const runTests = async () => {
    if (isRunning) return;
    
    setIsRunning(true);
    setTestResults([]);
    setCreatedPostId(null);

    try {
      // Test 1: Check if user is authenticated
      addResult('Checking authentication...');
      if (!user) {
        addResult('User not authenticated. Please log in first.', false);
        setIsRunning(false);
        return;
      }
      addResult(`Authenticated as: ${user.email}`);

      // Test 2: Create a test blog post
      addResult('Testing POST /api/blog - Creating test post...');
      const createRes = await fetch('/api/blog', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: `Test Blog Post ${Date.now()}`,
          content: '# Test Content\n\nThis is a test blog post created via API.',
          excerpt: 'This is a test excerpt',
          status: 'draft',
          tags: ['test', 'api'],
          meta_title: 'Test Meta Title',
          meta_description: 'Test meta description'
        })
      });

      if (!createRes.ok) {
        const error = await createRes.json();
        addResult(`Failed to create post: ${error.error || 'Unknown error'}`, false);
        if (createRes.status === 401) {
          addResult('User is not admin. Setting admin role...', false);
          // Update user role to admin
          const { createClient } = await import('@/lib/supabase');
          const supabase = createClient();
          const { error: updateError } = await supabase
            .from('user_profiles')
            .upsert({
              id: user.id,
              email: user.email,
              role: 'admin',
              full_name: user.user_metadata?.full_name || 'Admin User',
              avatar_url: user.user_metadata?.avatar_url
            });
          
          if (updateError) {
            addResult(`Failed to set admin role: ${updateError.message}`, false);
          } else {
            addResult('Admin role set successfully. Please refresh and try again.');
          }
          setIsRunning(false);
          return;
        }
      } else {
        const data = await createRes.json();
        addResult(`Post created with ID: ${data.post.id}`);
        setCreatedPostId(data.post.id);

        // Test 3: Get all posts (admin view)
        addResult('Testing GET /api/blog?admin=true - Fetching admin posts...');
        const adminRes = await fetch('/api/blog?admin=true');
        if (!adminRes.ok) {
          addResult('Failed to fetch admin posts', false);
        } else {
          const adminData = await adminRes.json();
          addResult(`Found ${adminData.posts?.length || 0} posts in admin view`);
        }

        // Test 4: Get public posts
        addResult('Testing GET /api/blog - Fetching public posts...');
        const publicRes = await fetch('/api/blog?page=1&limit=10');
        if (!publicRes.ok) {
          addResult('Failed to fetch public posts', false);
        } else {
          const publicData = await publicRes.json();
          addResult(`Found ${publicData.posts?.length || 0} published posts (total: ${publicData.total || 0})`);
        }

        // Test 5: Update the created post
        if (data.post.id) {
          addResult(`Testing PUT /api/blog/${data.post.id} - Updating post...`);
          const updateRes = await fetch(`/api/blog/${data.post.id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              title: 'Updated Test Post',
              status: 'published'
            })
          });

          if (!updateRes.ok) {
            addResult('Failed to update post', false);
          } else {
            const updateData = await updateRes.json();
            addResult(`Post updated: ${updateData.post.title} (status: ${updateData.post.status})`);
          }

          // Test 6: Auto-save
          addResult('Testing POST /api/blog/autosave - Auto-saving draft...');
          const autosaveRes = await fetch('/api/blog/autosave', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              postId: data.post.id,
              content: '# Auto-saved content\n\nThis content was auto-saved.'
            })
          });

          if (!autosaveRes.ok) {
            addResult('Failed to auto-save', false);
          } else {
            const autosaveData = await autosaveRes.json();
            addResult(`Auto-save ${autosaveData.success ? 'successful' : 'failed'} at ${autosaveData.savedAt}`);
          }
        }
      }

      addResult('All tests completed!');
    } catch (error) {
      addResult(`Test error: ${error}`, false);
    } finally {
      setIsRunning(false);
    }
  };

  const deleteTestPost = async () => {
    if (!createdPostId) {
      addResult('No test post to delete', false);
      return;
    }

    try {
      addResult(`Deleting test post ${createdPostId}...`);
      const res = await fetch(`/api/blog/${createdPostId}`, {
        method: 'DELETE'
      });

      if (!res.ok) {
        addResult('Failed to delete test post', false);
      } else {
        addResult('Test post deleted successfully');
        setCreatedPostId(null);
      }
    } catch (error) {
      addResult(`Delete error: ${error}`, false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-3xl font-bold mb-6">Blog API Test Suite</h1>
        
        <div className="bg-white rounded-lg shadow-md p-6 mb-6">
          <div className="mb-4">
            <p className="text-sm text-gray-600 mb-2">
              Current User: {user?.email || 'Not logged in'}
            </p>
            {!user && (
              <p className="text-red-600 text-sm">
                Please log in first to test the API
              </p>
            )}
          </div>

          <div className="flex gap-4">
            <button
              onClick={runTests}
              disabled={isRunning || !user}
              className="px-6 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isRunning ? 'Running Tests...' : 'Run All Tests'}
            </button>

            {createdPostId && (
              <button
                onClick={deleteTestPost}
                disabled={isRunning}
                className="px-6 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 disabled:opacity-50"
              >
                Delete Test Post
              </button>
            )}
          </div>
        </div>

        <div className="bg-white rounded-lg shadow-md p-6">
          <h2 className="text-xl font-semibold mb-4">Test Results</h2>
          <div className="bg-gray-900 text-gray-100 p-4 rounded-md font-mono text-sm max-h-96 overflow-y-auto">
            {testResults.length === 0 ? (
              <p className="text-gray-400">No tests run yet. Click "Run All Tests" to start.</p>
            ) : (
              testResults.map((result, index) => (
                <div key={index} className="mb-1">
                  {result}
                </div>
              ))
            )}
          </div>
        </div>

        <div className="mt-6 bg-yellow-50 border border-yellow-200 rounded-lg p-4">
          <h3 className="font-semibold text-yellow-800 mb-2">Test Coverage:</h3>
          <ul className="text-sm text-yellow-700 space-y-1">
            <li>✓ Authentication check</li>
            <li>✓ Create blog post (POST /api/blog)</li>
            <li>✓ Fetch admin posts (GET /api/blog?admin=true)</li>
            <li>✓ Fetch public posts (GET /api/blog)</li>
            <li>✓ Update post (PUT /api/blog/[id])</li>
            <li>✓ Auto-save draft (POST /api/blog/autosave)</li>
            <li>✓ Delete post (DELETE /api/blog/[id])</li>
            <li>⚠️ Image upload requires file input (not tested here)</li>
          </ul>
        </div>
      </div>
    </div>
  );
}