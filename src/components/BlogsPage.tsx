/* src/components/BlogsPage.tsx */
'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Calendar, ChevronRight, Clock, Eye, Tag } from 'lucide-react';
import Link from 'next/link';
import type { BlogPostWithAuthor } from '@/lib/blog.types';

const filterTabs = ['All', 'Publication', 'Insight', 'Release', 'Tutorial'];

export default function BlogsPage() {
  const [posts, setPosts] = useState<BlogPostWithAuthor[]>([]);
  const [filteredPosts, setFilteredPosts] = useState<BlogPostWithAuthor[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('All');
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const limit = 10;

  // Fetch posts
  useEffect(() => {
    const fetchPosts = async () => {
      setLoading(true);
      try {
        const res = await fetch(`/api/blog?page=${page}&limit=${limit}`);
        if (res.ok) {
          const data = await res.json();
          if (page === 1) {
            setPosts(data.posts || []);
          } else {
            setPosts(prev => [...prev, ...(data.posts || [])]);
          }
          setTotal(data.total || 0);
        }
      } catch (error) {
        console.error('Failed to fetch posts:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchPosts();
  }, [page]);

  // Filter posts by tab
  useEffect(() => {
    let filtered = [...posts];

    if (activeTab !== 'All') {
      filtered = filtered.filter(post => {
        const postType = post.tags?.[0] || 'Publication';
        return postType.toLowerCase() === activeTab.toLowerCase();
      });
    }

    setFilteredPosts(filtered);
  }, [posts, activeTab]);

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric'
    });
  };

  const calculateReadTime = (content: string) => {
    const wordsPerMinute = 200;
    const words = content.split(/\s+/).length;
    const minutes = Math.ceil(words / wordsPerMinute);
    return `${minutes} min`;
  };

  // If no posts yet, show empty
  const displayPosts = filteredPosts;

  return (
    <section className="max-w-7xl mx-auto px-6 py-20">
      <motion.header
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="mb-12"
      >
        <h1 className="mb-6 text-5xl font-light tracking-[-0.02em] text-neutral-900">
          Blog
        </h1>

        {/* Tabs */}
        <div role="tablist" aria-label="Blog filters" className="flex items-center gap-2 border-b border-neutral-200/60">
          {filterTabs.map((tab) => (
            <button
              key={tab}
              role="tab"
              aria-selected={tab === activeTab}
              onClick={() => setActiveTab(tab)}
              className={`relative px-4 py-3 text-sm font-medium transition-colors ${
                tab === activeTab
                  ? 'text-neutral-900'
                  : 'text-neutral-500 hover:text-neutral-700'
              }`}
            >
              {tab}
              {tab === activeTab && (
                <motion.div
                  layoutId="activeTab"
                  className="absolute bottom-0 left-0 right-0 h-0.5 bg-neutral-900"
                />
              )}
            </button>
          ))}
        </div>
      </motion.header>

      {/* Loading State */}
      {loading && posts.length === 0 ? (
        <div className="flex justify-center py-20">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        </div>
      ) : displayPosts.length === 0 ? (
        <div className="text-center py-20">
          <p className="text-gray-500 text-lg">No posts found.</p>
        </div>
      ) : (
        <>
          {/* Posts List */}
          <div className="space-y-8">
            {displayPosts.map((post, idx) => (
              <motion.article
                key={post.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: idx * 0.08, duration: 0.5 }}
              >
                <Link href={`/blog/${post.slug}`} className="group block">
                  <div className="flex flex-col gap-6 border-b border-neutral-200/60 pb-8 lg:flex-row lg:items-start">
                    {/* Meta */}
                    <div className="flex-shrink-0 lg:w-48">
                      <div className="mb-2 flex items-center gap-3 text-sm text-neutral-500">
                        <span className="font-medium text-neutral-700">
                          {post.tags?.[0] || 'Publication'}
                        </span>
                      </div>
                      <div className="flex flex-col gap-1 text-sm text-neutral-500">
                        <span className="flex items-center gap-1">
                          <Calendar size={14} strokeWidth={1.5} />
                          {formatDate(post.published_at || post.created_at)}
                        </span>
                        <span className="flex items-center gap-1">
                          <Clock size={14} strokeWidth={1.5} />
                          {calculateReadTime(post.content)}
                        </span>
                        {post.view_count > 0 && (
                          <span className="flex items-center gap-1">
                            <Eye size={14} strokeWidth={1.5} />
                            {post.view_count} views
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Content */}
                    <div className="flex-1">
                      <h3 className="mb-3 text-2xl font-normal tracking-[-0.01em] text-neutral-900 transition-colors group-hover:text-neutral-700">
                        {post.title}
                      </h3>
                      {post.excerpt && (
                        <p className="leading-relaxed text-neutral-600 line-clamp-3">
                          {post.excerpt}
                        </p>
                      )}
                      {/* Tags */}
                      {post.tags && post.tags.length > 0 && (
                        <div className="mt-3 flex flex-wrap gap-2">
                          {(Array.isArray(post.tags) ? post.tags : []).slice(0, 3).map((tag, i) => (
                            <span
                              key={i}
                              className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium text-gray-600 bg-gray-100 rounded-md"
                            >
                              <Tag size={10} />
                              {tag}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>

                    {/* Arrow */}
                    <div className="flex items-center justify-end lg:w-12">
                      <ChevronRight
                        size={20}
                        strokeWidth={1.5}
                        className="text-neutral-400 transition-all group-hover:translate-x-1 group-hover:text-neutral-600"
                        aria-hidden
                      />
                    </div>
                  </div>
                </Link>
              </motion.article>
            ))}
          </div>

          {/* Load more */}
          {!loading && posts.length < total && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.5, duration: 0.4 }}
              className="mt-12 text-center"
            >
              <button
                type="button"
                onClick={() => setPage(p => p + 1)}
                className="text-[15px] font-medium text-neutral-600 transition-colors hover:text-neutral-900"
                disabled={loading}
              >
                {loading ? 'Loading...' : 'Load more articles'}
              </button>
            </motion.div>
          )}
        </>
      )}
    </section>
  );
}