'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

const links = [
  { href: '/about', label: 'About' },
  { href: '/contact', label: 'Contact' },
  { href: '/privacy', label: 'Privacy' },
  { href: '/terms', label: 'Terms' },
] as const;

export default function Footer() {
  const pathname = usePathname();
  const isNews = pathname.startsWith('/news');

  return (
    <>
      {isNews && <div className="h-16" />}
      <footer className="bg-[oklch(98.8%_0.003_106.5)] dark:bg-neutral-950">
        <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-2 px-6 py-6 text-sm text-gray-500 sm:flex-row dark:text-gray-400">
          <span>&copy; {new Date().getFullYear()} Araverus</span>
          <nav className="flex gap-4">
            {links.map(({ href, label }) => (
              <Link
                key={href}
                href={href}
                className="transition-colors hover:text-gray-900 dark:hover:text-gray-200"
              >
                {label}
              </Link>
            ))}
          </nav>
        </div>
      </footer>
    </>
  );
}
