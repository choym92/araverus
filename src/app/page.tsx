// src/app/page.tsx
import Link from 'next/link';

export default function Home() {
  return (
    <section className="mx-auto max-w-3xl py-24 text-center">
      <h1 className="text-5xl font-bold text-emerald-600">Araverus</h1>
      <p className="mt-4 text-lg text-gray-600 dark:text-gray-300">
        AI-powered SEC-filing screener &amp; market dashboard
      </p>
      
      <div className="mt-8 space-x-4">
        <Link 
          href="/login" 
          className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-3 rounded-md font-medium transition-colors inline-block"
        >
          Sign In
        </Link>
        <Link 
          href="/dashboard" 
          className="bg-emerald-600 hover:bg-emerald-700 text-white px-6 py-3 rounded-md font-medium transition-colors inline-block"
        >
          Dashboard
        </Link>
      </div>
    </section>
  );
}
