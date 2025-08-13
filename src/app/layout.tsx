// src/app/layout.tsx
import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

/* ---------- fonts ---------- */
const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
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
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
{children}
      </body>
    </html>
  );
}
