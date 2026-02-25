import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  images: {
    remotePatterns: [
      // TODO: Replace https wildcard with image proxy API to prevent open proxy abuse
      {
        protocol: 'https',
        hostname: '**',
      },
      {
        protocol: 'https',
        hostname: 'lh3.googleusercontent.com',
      },
      {
        protocol: 'https',
        hostname: 'obqjrbwguutgtsjaivrh.supabase.co',
      },
    ],
  },
};

export default nextConfig;
