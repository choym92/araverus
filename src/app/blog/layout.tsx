'use client';

import { useState, useEffect } from 'react';
import { usePathname } from 'next/navigation';
import Sidebar from '@/components/Sidebar';
import Header from '@/components/Header';

export default function BlogLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [mounted, setMounted] = useState(false);
  const [sidebarKey, setSidebarKey] = useState(0);

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

  // Trigger sidebar animation on route change
  useEffect(() => {
    if (mounted && pathname) {
      setSidebarKey(prev => prev + 1);
    }
  }, [pathname, mounted]);

  const handleNavigation = (page: string) => {
    // Handle navigation
    if (window.innerWidth < 768) {
      setSidebarOpen(false);
    }
  };

  if (!mounted) return null;

  return (
    <div 
      className="min-h-screen bg-white relative overflow-hidden"
      style={{ '--sidebar-w': '16rem' } as React.CSSProperties}
    >
      {/* Animated background gradient */}
      <div className="fixed inset-0 bg-gradient-to-br from-blue-50/30 via-white to-purple-50/30 pointer-events-none" />
      
      {/* Sidebar with key to trigger animation on route change */}
      <Sidebar 
        key={`sidebar-${sidebarKey}`}
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        onNavigate={handleNavigation}
        currentPage="blogs"
      />
      
      {/* Main Content */}
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
        {children}
      </div>
    </div>
  );
}