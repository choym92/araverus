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
});
const playfair = Playfair_Display({
  variable: "--font-playfair",
  subsets: ["latin"],
  style: ["normal", "italic"],
});


/* ---------- viewport (iOS safe area) ---------- */
export const viewport: Viewport = {
  viewportFit: 'cover',
};

/* ---------- <head> metadata ---------- */
export const metadata: Metadata = {
  title: "Paul Cho - Personal Website",
  description: "Paul Cho's personal website - showcasing projects, insights, and professional journey",
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
{children}
        <Analytics />
      </body>
    </html>
  );
}
