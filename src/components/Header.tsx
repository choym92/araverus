'use client';

import { Search, Menu } from 'lucide-react';

interface HeaderProps {
  sidebarOpen: boolean;
  onToggleSidebar: () => void;
}

export default function Header({ sidebarOpen, onToggleSidebar }: HeaderProps) {
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
            <span className="font-semibold text-lg">OpenAI</span>
          </div>
          
          {/* Toggle button - Always visible */}
          <button
            onClick={onToggleSidebar}
            className="p-2 hover:bg-gray-100 rounded-md transition-colors"
            aria-label={sidebarOpen ? "Close sidebar" : "Open sidebar"}
          >
            <Menu size={20} className="text-gray-600" />
          </button>
        </div>
        
        {/* Right side - Search and Login */}
        <div className="flex items-center gap-3">
          <button
            className="p-2 hover:bg-gray-100 rounded-md transition-colors"
            aria-label="Search"
          >
            <Search size={20} className="text-gray-600" />
          </button>
          <button className="px-4 py-2 text-sm font-medium text-gray-700 hover:text-gray-900 hover:bg-gray-100 rounded-md transition-colors">
            Log in
          </button>
        </div>
      </div>
    </header>
  );
}