'use client';

import { useEffect, useState } from 'react';
import Sidebar from '@/components/Sidebar';
import Header from '@/components/Header';
import Hero from '@/components/Hero';

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
        <Hero />
      </div>

    </div>
  );
}