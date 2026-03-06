'use client';

import Link from 'next/link';
import { Menu, LogOut, Loader2 } from 'lucide-react';
import { useState } from 'react';
import { useAuth } from '@/hooks/useAuth';
import { motion, AnimatePresence } from 'framer-motion';

interface HeaderProps {
  sidebarOpen?: boolean;
  onToggleSidebar?: () => void;
}

export default function Header({ sidebarOpen, onToggleSidebar }: HeaderProps) {
  const { user, loading, signOut } = useAuth();
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const [isLoggingOut, setIsLoggingOut] = useState(false);

  const handleLogout = async () => {
    setIsLoggingOut(true);
    try {
      await signOut();
      setIsProfileOpen(false);
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      setIsLoggingOut(false);
    }
  };

  return (
    <header className="fixed top-0 right-0 left-0 h-14 md:h-20 md:pt-2 bg-white/80 backdrop-blur-md z-30">
      <div className="h-full px-4 md:px-12 lg:px-16 flex items-center justify-between">
        {/* Left side - Logo and Toggle */}
        <div className="flex items-center gap-3 md:gap-8">
          <Link href="/" className="flex items-center">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/logo-header.svg"
              alt="Araverus"
              className="h-9 md:h-10 w-auto"
            />
          </Link>

          {onToggleSidebar && (
            <button
              onClick={onToggleSidebar}
              aria-label={sidebarOpen ? "Close sidebar" : "Open sidebar"}
              aria-controls="app-sidebar"
              aria-expanded={sidebarOpen}
              className="p-1.5 md:p-2 hover:bg-gray-100 rounded-md transition-colors"
            >
              <Menu className="w-5 h-5 text-gray-600" />
            </button>
          )}
        </div>

        {/* Right side - Auth */}
        <div className="flex items-center gap-2 md:gap-3">

          {loading ? (
            <div className="px-2 py-1 md:px-4 md:py-2">
              <Loader2 className="w-4 h-4 md:w-[18px] md:h-[18px] animate-spin text-gray-500" />
            </div>
          ) : user ? (
            <div className="relative">
              <button
                onClick={() => setIsProfileOpen(!isProfileOpen)}
                className="flex items-center gap-1.5 px-2 py-1.5 md:gap-2 md:px-3 md:py-2 hover:bg-gray-100 rounded-md transition-colors"
                aria-label="User menu"
              >
                <span className="text-sm md:text-base font-medium text-gray-900">
                  Welcome, {user.user_metadata?.full_name?.split(' ')[0] || user.email?.split('@')[0] || 'User'}
                </span>
              </button>

              {/* Dropdown Menu */}
              <AnimatePresence>
                {isProfileOpen && (
                  <motion.div
                    initial={{ opacity: 0, scale: 0.95, y: -10 }}
                    animate={{ opacity: 1, scale: 1, y: 0 }}
                    exit={{ opacity: 0, scale: 0.95, y: -10 }}
                    transition={{ duration: 0.15 }}
                    className="absolute right-0 top-full mt-2 w-48 bg-white border border-gray-200 rounded-md shadow-lg z-50"
                  >
                    <div className="p-3 border-b border-gray-100">
                      <p className="text-sm font-medium text-gray-900 truncate">
                        {user.user_metadata?.full_name || 'User'}
                      </p>
                      <p className="text-xs text-gray-500 truncate">
                        {user.email}
                      </p>
                    </div>
                    <button
                      onClick={handleLogout}
                      disabled={isLoggingOut}
                      className="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 transition-colors disabled:opacity-50"
                    >
                      {isLoggingOut ? (
                        <Loader2 size={16} className="animate-spin" />
                      ) : (
                        <LogOut size={16} />
                      )}
                      {isLoggingOut ? 'Signing out...' : 'Sign out'}
                    </button>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          ) : (
            /* Login Button */
            <Link
              href="/login"
              className="px-3 py-1.5 text-sm md:px-4 md:py-2 md:text-sm font-medium text-gray-900 hover:text-gray-600 transition-colors flex items-center gap-2"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" /></svg>
              Sign in
            </Link>
          )}
        </div>
      </div>
    </header>
  );
}