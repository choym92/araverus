'use client';

import { useState } from 'react';
import { Share2, Twitter, Linkedin, Copy, Check } from 'lucide-react';

export default function ShareButtons({ title, url }: { title: string; url: string }) {
  const [copied, setCopied] = useState(false);

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
    // 모바일/지원 브라우저에서 네이티브 공유
    if (typeof navigator !== 'undefined' && navigator.share) {
      try {
        await navigator.share({ title, url });
      } catch (error) {
        // User cancelled or error
        console.error('Share failed:', error);
      }
    } else {
      copy(); // Fallback to copy
    }
  };

  return (
    <div className="flex items-center gap-2 ml-auto">
      <button 
        onClick={shareNative} 
        className="p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-full transition-colors" 
        aria-label="Share"
      >
        <Share2 size={18} />
      </button>
      
      <a
        href={`https://twitter.com/intent/tweet?text=${encodeURIComponent(title)}&url=${encodeURIComponent(url)}`}
        className="p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-full transition-colors"
        aria-label="Share on X"
        target="_blank"
        rel="noopener noreferrer"
      >
        <Twitter size={18} />
      </a>
      
      <a
        href={`https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(url)}`}
        className="p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-full transition-colors"
        aria-label="Share on LinkedIn"
        target="_blank"
        rel="noopener noreferrer"
      >
        <Linkedin size={18} />
      </a>
      
      <button 
        onClick={copy} 
        className="p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-full transition-colors" 
        aria-label="Copy link"
      >
        {copied ? <Check size={18} className="text-green-600" /> : <Copy size={18} />}
      </button>
    </div>
  );
}