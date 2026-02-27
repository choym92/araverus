'use client';

import { useState } from 'react';
import { Share2, Twitter, Linkedin, Copy, Check } from 'lucide-react';

interface ShareBarProps {
  title: string;
  url: string;
  /** Color palette: 'gray' for blog, 'neutral' for news */
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
        <Twitter size={16} />
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
