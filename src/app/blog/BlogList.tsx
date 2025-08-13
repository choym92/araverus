'use client';

import { useState, useEffect, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Calendar, ChevronRight, Filter, Grid3x3, List, Search, X, Tag, Clock } from 'lucide-react';
import Link from 'next/link';
import type { Post } from '@/lib/mdx';
import Sidebar from '@/components/Sidebar';
import Header from '@/components/Header';
import { useAuth } from '@/hooks/useAuth';

// Filter tabs
const filterTabs = ['All', 'Publication', 'Insight', 'Release', 'Tutorial'];

// Sort options
const sortOptions = [
  { value: 'newest', label: 'Newest First' },
  { value: 'oldest', label: 'Oldest First' },
  { value: 'popular', label: 'Most Popular' },
  { value: 'title', label: 'Title A-Z' },
];

interface BlogPageProps {
  initialPosts: Post[];
  initialCategory?: string;
}

export default function BlogPage({ initialPosts, initialCategory }: BlogPageProps) {
  const { user } = useAuth();
  const [posts] = useState<Post[]>(initialPosts);
  const [filteredPosts, setFilteredPosts] = useState<Post[]>([]);
  const [loading] = useState(false);
  const [activeTab, setActiveTab] = useState(initialCategory || 'All');
  const [sortBy, setSortBy] = useState('newest');
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('list');
  const [searchQuery, setSearchQuery] = useState('');
  const [showFilters, setShowFilters] = useState(false);
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [mounted, setMounted] = useState(false);
  const [isAdmin, setIsAdmin] = useState(false);

  // Check if user is admin (only choym92@gmail.com)
  useEffect(() => {
    if (user?.email === 'choym92@gmail.com') {
      setIsAdmin(true);
    } else {
      setIsAdmin(false);
    }
  }, [user]);

  useEffect(() => {
    setMounted(true);
    // Check saved preference
    const saved = localStorage.getItem('sidebar-open');
    if (saved !== null) {
      setSidebarOpen(saved === 'true');
    }
  }, []);

  useEffect(() => {
    if (mounted) {
      localStorage.setItem('sidebar-open', String(sidebarOpen));
    }
  }, [sidebarOpen, mounted]);

  const handleNavigation = (page: string) => {
    // Handle navigation
    if (window.innerWidth < 768) {
      setSidebarOpen(false);
    }
  };


  // Filter and sort posts
  useEffect(() => {
    let filtered = [...posts];

    // Filter by tab (category)
    if (activeTab !== 'All') {
      filtered = filtered.filter(post => {
        return post.frontmatter.category === activeTab;
      });
    }

    // Filter by search
    if (searchQuery) {
      filtered = filtered.filter(post =>
        post.frontmatter.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        post.frontmatter.excerpt?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        post.content.toLowerCase().includes(searchQuery.toLowerCase())
      );
    }

    // Filter by selected tags
    if (selectedTags.length > 0) {
      filtered = filtered.filter(post => {
        const postTags = post.frontmatter.tags || [];
        return selectedTags.some(tag => postTags.includes(tag));
      });
    }

    // Sort
    filtered.sort((a, b) => {
      switch (sortBy) {
        case 'oldest':
          return new Date(a.frontmatter.date).getTime() - new Date(b.frontmatter.date).getTime();
        case 'popular':
          // For now, sort by date for popular (can add view count later)
          return new Date(b.frontmatter.date).getTime() - new Date(a.frontmatter.date).getTime();
        case 'title':
          return a.frontmatter.title.localeCompare(b.frontmatter.title);
        case 'newest':
        default:
          return new Date(b.frontmatter.date).getTime() - new Date(a.frontmatter.date).getTime();
      }
    });

    setFilteredPosts(filtered);
  }, [posts, activeTab, sortBy, searchQuery, selectedTags]);

  // Get all unique tags
  const allTags = useMemo(() => 
    Array.from(new Set(posts.flatMap(post => 
      post.frontmatter.tags || []
    ))), [posts]);

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

  if (!mounted) return null;

  return (
    <div 
      className="min-h-screen bg-white relative overflow-hidden"
      style={{ '--sidebar-w': '16rem' } as React.CSSProperties}
    >
      {/* Animated background gradient */}
      <div className="fixed inset-0 bg-gradient-to-br from-blue-50/30 via-white to-purple-50/30 pointer-events-none" />
      
      {/* Sidebar */}
      <Sidebar 
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        onNavigate={handleNavigation}
        currentPage="blogs"
      />
      
      {/* Main Content */}
      <div
        className={`relative transition-[margin] duration-300 ease-out pt-16 ${
          sidebarOpen ? 'lg:ml-[var(--sidebar-w)]' : 'lg:ml-0'
        }`}
      >
        {/* Header */}
        <Header 
          sidebarOpen={sidebarOpen}
          onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
        />

      {/* Blog Content */}
      <div className="border-b border-gray-200 sticky top-16 bg-white/95 backdrop-blur-sm z-20">
        <div className="max-w-7xl mx-auto px-6 py-6">
          <div className="flex items-center justify-between mb-6">
            <h1 className="text-4xl font-light tracking-[-0.02em] text-neutral-900">
              Research
            </h1>
            
            {/* Controls */}
            <div className="flex items-center gap-3">
              {/* Write Button for Admin - Modern minimal style */}
              {isAdmin && (
                <Link
                  href="/admin/blog/write"
                  className="px-4 py-2 text-sm font-medium border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors flex items-center h-[38px]"
                >
                  Write
                </Link>
              )}
              
              {/* Search */}
              <div className="relative">
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search..."
                  className="pl-10 pr-4 py-2 w-64 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
                <Search className="absolute left-3 top-2.5 h-4 w-4 text-gray-400" />
                {searchQuery && (
                  <button
                    onClick={() => setSearchQuery('')}
                    className="absolute right-3 top-2.5 text-gray-400 hover:text-gray-600"
                  >
                    <X size={16} />
                  </button>
                )}
              </div>

              {/* Filter Button */}
              <button
                onClick={() => setShowFilters(!showFilters)}
                className={`flex items-center gap-2 px-4 py-2 text-sm font-medium border rounded-lg transition-colors ${
                  showFilters ? 'bg-gray-100 border-gray-300' : 'border-gray-200 hover:bg-gray-50'
                }`}
              >
                <Filter size={16} />
                Filter
              </button>

              {/* Sort Dropdown */}
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
                className="px-4 py-2 text-sm font-medium border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {sortOptions.map(option => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>

              {/* View Mode Toggle */}
              <div className="flex items-center border border-gray-200 rounded-lg">
                <button
                  onClick={() => setViewMode('list')}
                  className={`p-2 ${viewMode === 'list' ? 'bg-gray-100' : 'hover:bg-gray-50'}`}
                  aria-label="List view"
                >
                  <List size={18} />
                </button>
                <button
                  onClick={() => setViewMode('grid')}
                  className={`p-2 ${viewMode === 'grid' ? 'bg-gray-100' : 'hover:bg-gray-50'}`}
                  aria-label="Grid view"
                >
                  <Grid3x3 size={18} />
                </button>
              </div>
            </div>
          </div>

          {/* Filter Tabs */}
          <div className="flex items-center gap-2 border-b border-neutral-200/60">
            {filterTabs.map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`relative px-4 py-3 text-sm font-medium transition-colors ${
                  activeTab === tab
                    ? 'text-neutral-900'
                    : 'text-neutral-500 hover:text-neutral-700'
                }`}
              >
                {tab}
                {activeTab === tab && (
                  <motion.div
                    layoutId="activeTab"
                    className="absolute bottom-0 left-0 right-0 h-0.5 bg-neutral-900"
                  />
                )}
              </button>
            ))}
          </div>
        </div>

        {/* Filter Panel */}
        <AnimatePresence>
          {showFilters && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="border-t border-gray-200 overflow-hidden"
            >
              <div className="max-w-7xl mx-auto px-6 py-4">
                <div className="flex items-center gap-4">
                  <span className="text-sm font-medium text-gray-700">Tags:</span>
                  <div className="flex flex-wrap gap-2">
                    {allTags.map(tag => (
                      <button
                        key={tag}
                        onClick={() => {
                          setSelectedTags(prev =>
                            prev.includes(tag)
                              ? prev.filter(t => t !== tag)
                              : [...prev, tag]
                          );
                        }}
                        className={`px-3 py-1 text-xs font-medium rounded-full transition-colors ${
                          selectedTags.includes(tag)
                            ? 'bg-blue-100 text-blue-700'
                            : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                        }`}
                      >
                        {tag}
                      </button>
                    ))}
                  </div>
                  {selectedTags.length > 0 && (
                    <button
                      onClick={() => setSelectedTags([])}
                      className="text-sm text-blue-600 hover:text-blue-700"
                    >
                      Clear all
                    </button>
                  )}
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Content */}
      <div className="max-w-7xl mx-auto px-6 py-12">
        {loading ? (
          <div className="flex justify-center py-20">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
          </div>
        ) : filteredPosts.length === 0 ? (
          <div className="text-center py-20">
            <p className="text-gray-500 text-lg">No posts found.</p>
            {(searchQuery || selectedTags.length > 0) && (
              <button
                onClick={() => {
                  setSearchQuery('');
                  setSelectedTags([]);
                }}
                className="mt-4 text-blue-600 hover:text-blue-700 text-sm"
              >
                Clear filters
              </button>
            )}
          </div>
        ) : viewMode === 'list' ? (
          /* List View */
          <div className="space-y-8">
            {filteredPosts.map((post, idx) => (
              <motion.article
                key={post.slug}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: idx * 0.08, duration: 0.5 }}
                className="group cursor-pointer"
              >
                <Link href={`/blog/${post.slug}`}>
                  <div className="flex flex-col gap-6 border-b border-neutral-200/60 pb-8 lg:flex-row lg:items-start">
                    {/* Meta */}
                    <div className="flex-shrink-0 lg:w-48">
                      <div className="mb-2 flex items-center gap-3 text-sm text-neutral-500">
                        <span className="font-medium text-neutral-700">
                          {post.frontmatter.category}
                        </span>
                      </div>
                      <div className="flex items-center gap-4 text-sm text-neutral-500">
                        <span className="flex items-center gap-1">
                          <Calendar size={14} />
                          {formatDate(post.frontmatter.date)}
                        </span>
                        <span className="flex items-center gap-1">
                          <Clock size={14} />
                          {calculateReadTime(post.content)}
                        </span>
                      </div>
                    </div>

                    {/* Content */}
                    <div className="flex-1">
                      <h3 className="mb-3 text-2xl font-normal tracking-[-0.01em] text-neutral-900 transition-colors group-hover:text-neutral-700">
                        {post.frontmatter.title}
                      </h3>
                      {post.frontmatter.excerpt && (
                        <p className="leading-relaxed text-neutral-600 line-clamp-3">
                          {post.frontmatter.excerpt}
                        </p>
                      )}
                      {/* Tags */}
                      {post.frontmatter.tags && post.frontmatter.tags.length > 0 && (
                        <div className="mt-4 flex flex-wrap gap-2">
                          {(Array.isArray(post.frontmatter.tags) ? post.frontmatter.tags : []).map((tag, i) => (
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
                        className="text-neutral-400 transition-all group-hover:translate-x-1 group-hover:text-neutral-600"
                      />
                    </div>
                  </div>
                </Link>
              </motion.article>
            ))}
          </div>
        ) : (
          /* Grid View */
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredPosts.map((post, idx) => (
              <motion.article
                key={post.slug}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: idx * 0.08, duration: 0.5 }}
                className="group"
              >
                <Link href={`/blog/${post.slug}`}>
                  <div className="h-full bg-white border border-gray-200 rounded-lg overflow-hidden hover:shadow-lg transition-shadow">
                    {/* Featured Image */}
                    {post.frontmatter.coverImage ? (
                      <div className="h-48 bg-gray-200 overflow-hidden">
                        <img
                          src={post.frontmatter.coverImage}
                          alt={post.frontmatter.title}
                          className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                        />
                      </div>
                    ) : (
                      <div className="h-48 bg-gradient-to-br from-blue-100 to-purple-100" />
                    )}

                    <div className="p-6">
                      {/* Type & Date */}
                      <div className="flex items-center justify-between mb-3 text-sm text-gray-500">
                        <span className="font-medium">
                          {post.frontmatter.category}
                        </span>
                        <span>{formatDate(post.frontmatter.date)}</span>
                      </div>

                      {/* Title */}
                      <h3 className="mb-2 text-lg font-semibold text-gray-900 line-clamp-2 group-hover:text-blue-600 transition-colors">
                        {post.frontmatter.title}
                      </h3>

                      {/* Excerpt */}
                      {post.frontmatter.excerpt && (
                        <p className="text-sm text-gray-600 line-clamp-3 mb-4">
                          {post.frontmatter.excerpt}
                        </p>
                      )}

                      {/* Footer */}
                      <div className="flex items-center justify-between text-xs text-gray-500">
                        <div className="flex items-center gap-3">
                          <span className="flex items-center gap-1">
                            <Clock size={12} />
                            {calculateReadTime(post.content)}
                          </span>
                        </div>
                        <ChevronRight
                          size={16}
                          className="text-gray-400 group-hover:text-blue-600 transition-colors"
                        />
                      </div>
                    </div>
                  </div>
                </Link>
              </motion.article>
            ))}
          </div>
        )}

      </div>
      </div>
    </div>
  );
}