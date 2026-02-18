'use client'

import { useState, useEffect } from 'react'
import Header from '@/components/Header'
import Sidebar from '@/components/Sidebar'

export default function NewsShell({ children }: { children: React.ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(false)

  // Close sidebar on mount (news page always starts with sidebar hidden)
  useEffect(() => {
    setSidebarOpen(false)
  }, [])

  return (
    <div
      className="min-h-screen bg-white relative"
      style={{ '--sidebar-w': '16rem' } as React.CSSProperties}
    >
      <Sidebar
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        onNavigate={() => {}}
        currentPage="news"
      />

      {/* Content shifts right when sidebar is open on desktop */}
      <div
        className={`relative pt-20 transition-[margin] duration-300 ease-out ${
          sidebarOpen ? 'lg:ml-[var(--sidebar-w)]' : 'lg:ml-0'
        }`}
      >
        <Header
          sidebarOpen={sidebarOpen}
          onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
        />

        {children}
      </div>
    </div>
  )
}
