'use client'

import AppShell from '@/components/AppShell'

export default function NewsShell({ children }: { children: React.ReactNode }) {
  return <AppShell currentPage="news">{children}</AppShell>
}
