'use client';

import { useState } from 'react';
import { createClient } from '@/lib/supabase';

interface TestResult {
  test: string;
  status: 'SUCCESS' | 'FAILED';
  result?: unknown;
  error?: string;
  duration: string;
}

export default function TestDBPage() {
  const [results, setResults] = useState<TestResult[]>([]);
  const [loading, setLoading] = useState(false);

  const supabase = createClient();

  const runTest = async (testName: string, testFn: () => Promise<unknown>) => {
    setLoading(true);
    const startTime = Date.now();
    
    try {
      console.log(`Starting ${testName}...`);
      
      // Add timeout
      const result = await Promise.race([
        testFn(),
        new Promise((_, reject) => 
          setTimeout(() => reject(new Error('Timeout')), 5000)
        )
      ]);
      
      const duration = Date.now() - startTime;
      setResults(prev => [...prev, { 
        test: testName, 
        status: 'SUCCESS', 
        result, 
        duration: `${duration}ms`
      }]);
    } catch (error: unknown) {
      const duration = Date.now() - startTime;
      setResults(prev => [...prev, { 
        test: testName, 
        status: 'FAILED', 
        error: error instanceof Error ? error.message : 'Unknown error', 
        duration: `${duration}ms`
      }]);
    }
    setLoading(false);
  };

  const tests = [
    {
      name: 'Basic Connection',
      fn: async () => {
        const { data, error } = await supabase.from('user_profiles').select('count').limit(1);
        return { data, error };
      }
    },
    {
      name: 'Auth Check',
      fn: async () => {
        const { data, error } = await supabase.auth.getUser();
        return { user: data.user?.email || 'No user', error };
      }
    },
    {
      name: 'Profile Query',
      fn: async () => {
        const { data: { user } } = await supabase.auth.getUser();
        if (!user) return { message: 'No user logged in' };
        
        const { data, error } = await supabase
          .from('user_profiles')
          .select('*')
          .eq('id', user.id)
          .single();
        return { data, error };
      }
    },
    {
      name: 'All Profiles',
      fn: async () => {
        const { data, error } = await supabase
          .from('user_profiles')
          .select('id, email, role')
          .limit(5);
        return { data, error };
      }
    }
  ];

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-3xl font-bold mb-8">Database Connection Tests</h1>
        
        <div className="mb-6">
          <p className="text-sm text-gray-600 mb-4">
            Environment: {process.env.NEXT_PUBLIC_SUPABASE_URL ? '✓ Connected' : '✗ Missing Config'}
          </p>
          
          <div className="flex gap-4 mb-6">
            <button
              onClick={() => {
                setResults([]);
                tests.forEach(test => runTest(test.name, test.fn));
              }}
              disabled={loading}
              className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 disabled:opacity-50"
            >
              {loading ? 'Running Tests...' : 'Run All Tests'}
            </button>
            
            <button
              onClick={() => setResults([])}
              className="bg-gray-600 text-white px-4 py-2 rounded hover:bg-gray-700"
            >
              Clear Results
            </button>
          </div>
        </div>

        <div className="space-y-4">
          {results.map((result, idx) => (
            <div key={idx} className="bg-white p-6 rounded-lg shadow">
              <div className="flex justify-between items-start mb-4">
                <h3 className="text-lg font-semibold">{result.test}</h3>
                <div className="flex items-center gap-2">
                  <span className={`px-2 py-1 text-xs rounded ${
                    result.status === 'SUCCESS' 
                      ? 'bg-green-100 text-green-800' 
                      : 'bg-red-100 text-red-800'
                  }`}>
                    {result.status}
                  </span>
                  <span className="text-xs text-gray-500">{result.duration}</span>
                </div>
              </div>
              
              <pre className="text-xs bg-gray-100 p-4 rounded overflow-auto">
                {result.status === 'SUCCESS' 
                  ? JSON.stringify(result.result, null, 2)
                  : `ERROR: ${result.error}`
                }
              </pre>
            </div>
          ))}
        </div>

        {results.length === 0 && (
          <div className="text-center text-gray-500 py-12">
            Click &ldquo;Run All Tests&rdquo; to start testing database connectivity
          </div>
        )}
      </div>
    </div>
  );
}