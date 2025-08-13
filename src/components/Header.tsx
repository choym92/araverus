'use client';

import { Search, Menu, User, LogOut, Loader2 } from 'lucide-react';
import { useState } from 'react';
import { useAuth } from '@/hooks/useAuth';
import { motion, AnimatePresence } from 'framer-motion';

interface HeaderProps {
  sidebarOpen: boolean;
  onToggleSidebar: () => void;
}

export default function Header({ sidebarOpen, onToggleSidebar }: HeaderProps) {
  const { user, loading, supabase, signOut } = useAuth();
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const [isLoggingOut, setIsLoggingOut] = useState(false);

  const handleLogin = async () => {
    try {
      const { error } = await supabase.auth.signInWithOAuth({
        provider: 'google',
        options: {
          redirectTo: `${window.location.origin}/`,
        }
      });
      if (error) throw error;
    } catch (error) {
      console.error('Login error:', error);
    }
  };

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
    <header className="fixed top-0 right-0 left-0 h-16 bg-white/80 backdrop-blur-md border-b border-gray-100 z-30">
      <div className="h-full px-6 flex items-center justify-between">
        {/* Left side - Logo and Toggle button always visible */}
        <div className="flex items-center gap-3">
          {/* OpenAI Logo - Always visible */}
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-black rounded-sm flex items-center justify-center">
              <span className="text-white font-bold text-sm">O</span>
            </div>
            <span className="font-semibold text-lg">ClosedAI</span>
          </div>
          
          {/* Toggle button - Always visible with improved accessibility */}
          <button
            onClick={onToggleSidebar}
            aria-label={sidebarOpen ? "Close sidebar" : "Open sidebar"}
            aria-controls="app-sidebar"
            aria-expanded={sidebarOpen}
            className="p-2 hover:bg-gray-100 rounded-md transition-colors"
          >
            <Menu size={20} className="text-gray-600" />
          </button>
        </div>
        
        {/* Right side - Search and Auth */}
        <div className="flex items-center gap-3">
          <button
            className="p-2 hover:bg-gray-100 rounded-md transition-colors"
            aria-label="Search"
          >
            <Search size={20} className="text-gray-600" />
          </button>
          
          {loading ? (
            <div className="px-4 py-2">
              <Loader2 size={18} className="animate-spin text-gray-500" />
            </div>
          ) : user ? (
            /* Authenticated User Menu */
            <div className="relative">
              <button
                onClick={() => setIsProfileOpen(!isProfileOpen)}
                className="flex items-center gap-2 px-3 py-2 hover:bg-gray-100 rounded-md transition-colors"
                aria-label="User menu"
              >
                {user.user_metadata?.avatar_url ? (
                  <img 
                    src={user.user_metadata.avatar_url} 
                    alt={user.user_metadata?.full_name || 'User'}
                    className="w-6 h-6 rounded-full"
                  />
                ) : (
                  <User size={18} className="text-gray-600" />
                )}
                <span className="text-sm font-medium text-gray-700 max-w-[100px] truncate">
                  {user.user_metadata?.full_name || user.email?.split('@')[0] || 'User'}
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
            <button 
              onClick={handleLogin}
              className="px-4 py-2 text-sm font-medium text-gray-700 hover:text-gray-900 hover:bg-gray-100 rounded-md transition-colors"
            >
              Log in
            </button>
          )}
        </div>
      </div>
    </header>
  );
}