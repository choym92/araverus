'use client';

import { useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
  onNavigate: (page: string) => void;
  currentPage: string;
}

// Nav Items
const navItems = [
  { id: 'home', label: 'Home' },
  { id: 'blogs', label: 'Blog' },
  { id: 'finance', label: 'Finance' },
  { id: 'contact', label: 'Contact' },
];


export default function Sidebar({ isOpen, onClose, onNavigate, currentPage }: SidebarProps) {
  // ESC로 닫기
  useEffect(() => {
    if (!isOpen) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [isOpen, onClose]);

  // 모바일 오픈 시 배경 스크롤 락
  useEffect(() => {
    if (!isOpen) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = prev; };
  }, [isOpen]);

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Mobile overlay */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-40 bg-black/20 supports-[backdrop-filter]:backdrop-blur-sm lg:hidden"
            onClick={onClose}
            aria-hidden
            role="presentation"
          />

          {/* Sidebar (헤더 h-16 아래로 시작, 폭은 --sidebar-w 재사용) */}
          <motion.aside
            id="app-sidebar"
            initial={{ x: '-100%' }}
            animate={{ x: 0 }}
            exit={{ x: '-100%' }}
            transition={{ type: 'spring', damping: 20, stiffness: 300 }}
            className="fixed left-0 top-16 z-50 h-[calc(100vh-4rem)] w-[var(--sidebar-w)] border-r border-neutral-200 bg-white shadow-xl lg:shadow-none"
            aria-label="Primary"
          >

            {/* Navigation */}
            <nav className="p-4" aria-label="Sections">
              <ul className="space-y-1">
                {navItems.map((item) => {
                  const active = currentPage === item.id;
                  return (
                    <li key={item.id}>
                      <button
                        onClick={() => onNavigate(item.id)}
                        aria-current={active ? 'page' : undefined}
                        className={`w-full rounded-md px-3 py-2 text-left text-sm font-medium transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-neutral-300 ${
                          active
                            ? 'bg-neutral-100 text-neutral-900 shadow-sm'
                            : 'text-neutral-600 hover:bg-neutral-50 hover:text-neutral-900'
                        }`}
                      >
                        {item.label}
                      </button>
                    </li>
                  );
                })}
              </ul>
            </nav>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}