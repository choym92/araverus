'use client';

import { useEffect, Suspense, useState } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { useAuth } from '@/hooks/useAuth';
import Sidebar from '@/components/Sidebar';
import Header from '@/components/Header';
import Hero from '@/components/Hero';
import BlogsPage from '@/components/BlogsPage';

function AuthCodeHandler() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const { supabase } = useAuth();
  const [isProcessing, setIsProcessing] = useState(false);

  useEffect(() => {
    const code = searchParams.get('code');
    if (code && !isProcessing) {
      setIsProcessing(true);
      // Exchange code for session
      supabase.auth.exchangeCodeForSession(code).then(({ data, error }) => {
        if (error) {
          console.error('Auth exchange failed:', error);
          // Redirect to login with error parameter
          router.push('/login?error=auth_failed');
        } else {
          console.log('Authentication successful:', data.user?.email);
          router.push('/dashboard');
        }
      }).catch((err) => {
        console.error('Unexpected auth error:', err);
        router.push('/login?error=unexpected');
      }).finally(() => {
        setIsProcessing(false);
      });
    }
  }, [searchParams, router, supabase, isProcessing]);

  // Show processing state if handling auth code
  if (isProcessing) {
    return (
      <div className="fixed inset-0 bg-white bg-opacity-80 flex items-center justify-center z-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Completing sign in...</p>
        </div>
      </div>
    );
  }

  return null;
}

export default function Home() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [currentPage, setCurrentPage] = useState('home');
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    // Check saved preference
    const saved = localStorage.getItem('sidebar-open');
    if (saved !== null) {
      setSidebarOpen(saved === 'true');
    }
  }, []);

  useEffect(() => {
    if (mounted) {
      localStorage.setItem('sidebar-open', String(sidebarOpen));
    }
  }, [sidebarOpen, mounted]);

  const handleNavigation = (page: string) => {
    setCurrentPage(page);
    // Close sidebar on mobile after navigation
    if (window.innerWidth < 768) {
      setSidebarOpen(false);
    }
  };

  if (!mounted) return null;

  return (
    <div 
      className="min-h-screen bg-white relative overflow-hidden"
      style={{ '--sidebar-w': '16rem' } as React.CSSProperties} // 16rem = 256px
    >
      {/* Animated background gradient */}
      <div className="fixed inset-0 bg-gradient-to-br from-blue-50/30 via-white to-purple-50/30 pointer-events-none" />
      
      {/* Performance-friendly blur for supported browsers */}
      <div className="fixed inset-0 pointer-events-none opacity-40 supports-[backdrop-filter]:backdrop-blur-[60px]" />
      
      {/* Sidebar */}
      <Sidebar 
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        onNavigate={handleNavigation}
        currentPage={currentPage}
      />
      
      {/* Main Content - CSS transition, desktop only push */}
      <div
        className={`relative transition-[margin] duration-300 ease-out pt-16 ${
          sidebarOpen ? 'lg:ml-[var(--sidebar-w)]' : 'lg:ml-0'
        }`}
      >
        {/* Header */}
        <Header 
          sidebarOpen={sidebarOpen}
          onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
        />
        
        {/* Page Content */}
        {currentPage === 'home' ? (
          <Hero />
        ) : currentPage === 'blogs' ? (
          <BlogsPage />
        ) : (
          <Hero />
        )}
      </div>

      <Suspense fallback={null}>
        <AuthCodeHandler />
      </Suspense>
    </div>
  );
}