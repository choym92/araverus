'use client';

import Link from 'next/link';
import { useEffect, Suspense } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { useAuth } from '@/hooks/useAuth';

function AuthCodeHandler() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const { supabase } = useAuth();

  useEffect(() => {
    const code = searchParams.get('code');
    if (code) {
      // Exchange code for session
      supabase.auth.exchangeCodeForSession(code).then(({ error }) => {
        if (error) {
          console.error('Auth exchange failed:', error);
          router.push('/login');
        } else {
          router.push('/dashboard');
        }
      });
    }
  }, [searchParams, router, supabase]);

  return null;
}

export default function Home() {
  return (
    <main className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100">
      <Suspense fallback={null}>
        <AuthCodeHandler />
      </Suspense>
      <section className="mx-auto max-w-4xl px-6 py-24">
        {/* Hero Section */}
        <div className="text-center mb-16">
          <h1 className="text-6xl font-bold text-gray-900 mb-6">
            Paul Cho
          </h1>
          <p className="text-xl text-gray-600 mb-8 max-w-2xl mx-auto leading-relaxed">
            Welcome to my personal website. I&apos;m passionate about technology, innovation, 
            and building meaningful digital experiences.
          </p>
        </div>

        {/* Quick Intro Cards */}
        <div className="grid md:grid-cols-3 gap-8 mb-16">
          <div className="bg-white p-6 rounded-xl shadow-sm border">
            <h3 className="text-lg font-semibold text-gray-900 mb-3">Developer</h3>
            <p className="text-gray-600">
              Building modern web applications with cutting-edge technologies
            </p>
          </div>
          
          <div className="bg-white p-6 rounded-xl shadow-sm border">
            <h3 className="text-lg font-semibold text-gray-900 mb-3">Innovator</h3>
            <p className="text-gray-600">
              Exploring new ideas and turning concepts into reality
            </p>
          </div>
          
          <div className="bg-white p-6 rounded-xl shadow-sm border">
            <h3 className="text-lg font-semibold text-gray-900 mb-3">Learner</h3>
            <p className="text-gray-600">
              Continuously growing and adapting to new challenges
            </p>
          </div>
        </div>

        {/* Admin Access (Hidden) */}
        <div className="text-center">
          <Link 
            href="/login" 
            className="text-sm text-gray-400 hover:text-gray-600 transition-colors"
          >
            Admin
          </Link>
        </div>
      </section>
    </main>
  );
}