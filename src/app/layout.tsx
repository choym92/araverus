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
    default: "Araverus — Financial Intelligence",
    template: "%s | Araverus",
  },
  description: "Financial intelligence platform powered by AI, machine learning, and neural networks.",
  metadataBase: new URL("https://araverus.com"),
  openGraph: {
    type: "website",
    locale: "en_US",
    siteName: "Araverus",
    title: "Araverus — Financial Intelligence",
    description: "Financial intelligence platform powered by AI, machine learning, and neural networks.",
    url: "https://araverus.com",
    images: [{ url: "https://araverus.com/og-news-default.png", width: 1200, height: 630 }],
  },
  twitter: {
    card: "summary_large_image",
    title: "Araverus — Financial Intelligence",
    description: "Financial intelligence platform powered by AI, machine learning, and neural networks.",
    images: ["https://araverus.com/og-news-default.png"],
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
              name: 'Araverus — Financial Intelligence',
              url: 'https://araverus.com',
              description: 'Financial intelligence platform powered by AI, machine learning, and neural networks.',
            },
            {
              '@context': 'https://schema.org',
              '@type': 'Organization',
              name: 'Araverus',
              url: 'https://araverus.com',
            },
          ]) }}
        />
{children}
        <Analytics />
      </body>
    </html>
  );
}
