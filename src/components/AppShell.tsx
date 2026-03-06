'use client'

import { useState, useEffect } from 'react'
import Header from '@/components/Header'
import Sidebar from '@/components/Sidebar'

interface AppShellProps {
  children: React.ReactNode
  currentPage?: string
}

export default function AppShell({ children, currentPage = 'news' }: AppShellProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false)

  // Close sidebar on mount (always starts with sidebar hidden)
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
        currentPage={currentPage}
      />

      {/* Content shifts right when sidebar is open on desktop */}
      <div
        className={`relative pt-14 md:pt-20 transition-[margin] duration-300 ease-out ${
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
