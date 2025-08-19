'use client';

import { useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import Link from 'next/link';
import { ChevronRight } from 'lucide-react';

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
  onNavigate: (page: string) => void;
  currentPage: string;
}

// Nav Items
const navItems = [
  { id: 'home', label: 'Home', href: '/' },
  { id: 'blogs', label: 'Blog', href: '/blog' },
  { id: 'finance', label: 'Finance', href: '/finance' },
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
    // Only lock scroll on mobile
    if (!isOpen || window.innerWidth >= 1024) return;
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
            transition={{ 
              type: 'tween',
              duration: 0.3,
              ease: [0.25, 0.1, 0.25, 1]  // Custom cubic-bezier for smooth, non-bouncy animation
            }}
            className="fixed left-0 top-16 z-50 h-[calc(100vh-4rem)] w-[var(--sidebar-w)] border-r border-neutral-200 bg-white shadow-xl lg:shadow-none"
            aria-label="Primary"
          >

            {/* Navigation */}
            <nav className="p-6 pt-16" aria-label="Sections">
              <ul className="space-y-0.5">
                {navItems.map((item) => {
                  const active = currentPage === item.id;
                  return (
                    <li key={item.id}>
                      {item.href ? (
                        <Link
                          href={item.href}
                          className={`group flex items-center justify-between w-full rounded-md px-3 py-2.5 text-left text-base transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-neutral-300 ${
                            active
                              ? 'bg-neutral-100 text-neutral-900 shadow-sm'
                              : 'text-neutral-600 hover:bg-neutral-50 hover:text-neutral-900'
                          }`}
                        >
                          <span>{item.label}</span>
                          <ChevronRight 
                            className="w-4 h-4 opacity-0 -translate-x-2 group-hover:opacity-100 group-hover:translate-x-0 transition-all duration-200" 
                          />
                        </Link>
                      ) : (
                        <button
                          onClick={() => onNavigate(item.id)}
                          aria-current={active ? 'page' : undefined}
                          className={`group flex items-center justify-between w-full rounded-md px-3 py-2.5 text-left text-base transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-neutral-300 ${
                            active
                              ? 'bg-neutral-100 text-neutral-900 shadow-sm'
                              : 'text-neutral-600 hover:bg-neutral-50 hover:text-neutral-900'
                          }`}
                        >
                          <span>{item.label}</span>
                          <ChevronRight 
                            className="w-4 h-4 opacity-0 -translate-x-2 group-hover:opacity-100 group-hover:translate-x-0 transition-all duration-200" 
                          />
                        </button>
                      )}
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