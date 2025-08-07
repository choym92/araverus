// src/app/config-error/page.tsx

export default function ConfigErrorPage() {
  return (
    <div className="min-h-screen bg-red-50 flex items-center justify-center">
      <div className="max-w-md w-full space-y-8 p-8">
        <div className="text-center">
          <h2 className="mt-6 text-3xl font-bold text-red-900">
            Configuration Error
          </h2>
          <p className="mt-2 text-sm text-red-700">
            The application is missing required environment variables
          </p>
        </div>
        
        <div className="bg-white p-6 rounded-lg shadow-md border border-red-200">
          <h3 className="text-lg font-semibold text-red-900 mb-4">
            Required Environment Variables
          </h3>
          
          <div className="space-y-3">
            <div className="p-3 bg-gray-50 rounded">
              <code className="text-sm text-gray-800">NEXT_PUBLIC_SUPABASE_URL</code>
              <p className="text-xs text-gray-600 mt-1">Your Supabase project URL</p>
            </div>
            
            <div className="p-3 bg-gray-50 rounded">
              <code className="text-sm text-gray-800">NEXT_PUBLIC_SUPABASE_ANON_KEY</code>
              <p className="text-xs text-gray-600 mt-1">Your Supabase anonymous key</p>
            </div>
            
            <div className="p-3 bg-gray-50 rounded">
              <code className="text-sm text-gray-800">SUPABASE_SERVICE_ROLE_KEY</code>
              <p className="text-xs text-gray-600 mt-1">Your Supabase service role key (server-side only)</p>
            </div>
          </div>
          
          <div className="mt-6 p-4 bg-blue-50 rounded border border-blue-200">
            <h4 className="font-medium text-blue-900">How to fix:</h4>
            <ol className="mt-2 text-sm text-blue-800 space-y-1">
              <li>1. Create a <code>.env.local</code> file in your project root</li>
              <li>2. Add the required environment variables</li>
              <li>3. Restart your development server</li>
            </ol>
          </div>
        </div>
      </div>
    </div>
  );
}