'use client';

import { useState } from 'react';
import { Share2, Linkedin, Copy, Check } from 'lucide-react';

function XIcon({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
    </svg>
  );
}

interface ShareBarProps {
  title: string;
  url: string;
  palette?: 'gray' | 'neutral';
}

export default function ShareBar({ title, url, palette = 'gray' }: ShareBarProps) {
  const [copied, setCopied] = useState(false);

  const colors = palette === 'neutral'
    ? { bg: 'bg-neutral-100', text: 'text-neutral-500', hover: 'hover:bg-neutral-200 hover:text-neutral-700' }
    : { bg: 'bg-gray-100', text: 'text-gray-500', hover: 'hover:bg-gray-200 hover:text-gray-700' };

  const btnClass = `p-2.5 rounded-full ${colors.bg} ${colors.text} ${colors.hover} transition-colors`;

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch (error) {
      console.error('Failed to copy:', error);
    }
  };

  const shareNative = async () => {
    if (typeof navigator !== 'undefined' && navigator.share) {
      try {
        await navigator.share({ title, url });
      } catch {
        // User cancelled
      }
    } else {
      copy();
    }
  };

  return (
    <div className="flex items-center gap-3">
      <button onClick={copy} className={btnClass} aria-label="Copy link">
        {copied ? <Check size={16} className="text-green-600" /> : <Copy size={16} />}
      </button>

      <a
        href={`https://twitter.com/intent/tweet?text=${encodeURIComponent(title)}&url=${encodeURIComponent(url)}`}
        className={btnClass}
        aria-label="Share on X"
        target="_blank"
        rel="noopener noreferrer"
      >
        <XIcon size={16} />
      </a>

      <a
        href={`https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(url)}`}
        className={btnClass}
        aria-label="Share on LinkedIn"
        target="_blank"
        rel="noopener noreferrer"
      >
        <Linkedin size={16} />
      </a>

      <button onClick={shareNative} className={btnClass} aria-label="Share">
        <Share2 size={16} />
      </button>
    </div>
  );
}
