// src/app/layout.tsx
import type { Metadata } from "next";
import { Inter, Geist_Mono } from "next/font/google";
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
      <body
        className={`${inter.variable} ${geistMono.variable} font-sans antialiased`}
      >
{children}
      </body>
    </html>
  );
}
