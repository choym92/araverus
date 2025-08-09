export default function AuthTestPage() {
  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-2xl mx-auto">
        <h1 className="text-3xl font-bold mb-8">Auth Test Page</h1>
        <p>If you can see this, the auth routes are working.</p>
        <p className="mt-4">
          <a href="/auth/callback?code=test" className="text-blue-600 underline">
            Test callback route (should redirect to error page)
          </a>
        </p>
      </div>
    </div>
  );
}