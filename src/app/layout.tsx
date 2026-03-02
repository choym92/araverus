// src/app/layout.tsx
import type { Metadata, Viewport } from "next";
import { Inter, Geist_Mono, Playfair_Display } from "next/font/google";
import { Analytics } from "@vercel/analytics/react";
import { GoogleAnalytics } from "@next/third-parties/google";
import "./globals.css";

/* ---------- fonts ---------- */
const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  display: 'swap',
});
const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
  display: 'swap',
});
const playfair = Playfair_Display({
  variable: "--font-playfair",
  subsets: ["latin"],
  style: ["normal", "italic"],
  display: 'swap',
});


/* ---------- viewport (iOS safe area) ---------- */
export const viewport: Viewport = {
  viewportFit: 'cover',
};

/* ---------- <head> metadata ---------- */
export const metadata: Metadata = {
  title: {
    default: "Paul Cho — AI Projects on News and Finance",
    template: "%s | Paul Cho",
  },
  description: "Using agentic AI and neural networks to get insights on news and finance.",
  metadataBase: new URL("https://chopaul.com"),
  openGraph: {
    type: "website",
    locale: "en_US",
    siteName: "chopaul.com",
    title: "Paul Cho — AI Projects on News and Finance",
    description: "Using agentic AI and neural networks to get insights on news and finance.",
    url: "https://chopaul.com",
    images: [{ url: "https://chopaul.com/og-news-default.png", width: 1200, height: 630 }],
  },
  twitter: {
    card: "summary_large_image",
    title: "Paul Cho — AI Projects on News and Finance",
    description: "Using agentic AI and neural networks to get insights on news and finance.",
    images: ["https://chopaul.com/og-news-default.png"],
  },
  alternates: { types: { 'application/rss+xml': '/rss.xml' } },
};

/* ---------- root layout ---------- */
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <GoogleAnalytics gaId="G-3R2TBBK842" />
      <body
        className={`${inter.variable} ${geistMono.variable} ${playfair.variable} font-sans antialiased`}
      >
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify([
            {
              '@context': 'https://schema.org',
              '@type': 'WebSite',
              name: 'chopaul.com',
              url: 'https://chopaul.com',
              description: 'Using agentic AI and neural networks to get insights on news and finance.',
            },
            {
              '@context': 'https://schema.org',
              '@type': 'Person',
              name: 'Paul Cho',
              url: 'https://chopaul.com',
              sameAs: [
                'https://www.linkedin.com/in/ympcho/',
              ],
            },
          ]) }}
        />
{children}
        <Analytics />
      </body>
    </html>
  );
}
