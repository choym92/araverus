/* src/components/BlogsPage.tsx */
'use client';

import { motion } from 'framer-motion';
import { Calendar, ChevronRight } from 'lucide-react';

const blogItems = [
  {
    id: 1,
    type: 'Publication',
    title: 'GPT-5 System Card',
    date: 'Aug 7, 2025',
    description:
      'This GPT-5 system card explains how a unified model routing system powers fast and smart responses using gpt-5-main, gpt-5-thinking, and lightweight versions like gpt-5-thinking-nano.',
  },
  {
    id: 2,
    type: 'Release',
    title: 'Introducing GPT-5',
    date: 'Aug 7, 2025',
    description:
      'We are introducing GPT-5, our best AI system yet. GPT-5 is a significant leap in intelligence over all our previous models, featuring state-of-the-art performance across coding, math, writing, health.',
  },
  {
    id: 3,
    type: 'Insight',
    title: 'From hard refusals to safe-completions',
    date: 'Aug 7, 2025',
    description:
      "OpenAI's output-centric safety training improves both safety and helpfulness in AI responses—moving beyond hard refusals to nuanced, safe-completions.",
  },
  {
    id: 4,
    type: 'Release',
    title: 'Introducing gpt-oss',
    date: 'Aug 5, 2025',
    description:
      'We are releasing gpt-oss-120b and gpt-oss-20b—two open-weight models with strong real-world performance at low cost, under a flexible license.',
  },
];

const filterTabs = ['All', 'Publication', 'Insight', 'Release'];

export default function BlogsPage() {
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

        {/* Tabs (static UI for now) */}
        <div role="tablist" aria-label="Blog filters" className="flex items-center gap-2 border-b border-neutral-200/60">
          {filterTabs.map((tab) => (
            <button
              key={tab}
              role="tab"
              aria-selected={tab === 'All'}
              className={`relative px-4 py-3 text-sm font-medium transition-colors ${
                tab === 'All'
                  ? 'text-neutral-900'
                  : 'text-neutral-500 hover:text-neutral-700'
              }`}
            >
              {tab}
              {tab === 'All' && (
                <motion.div
                  layoutId="activeTab"
                  className="absolute bottom-0 left-0 right-0 h-0.5 bg-neutral-900"
                />
              )}
            </button>
          ))}
        </div>
      </motion.header>

      {/* List */}
      <div className="space-y-8">
        {blogItems.map((item, idx) => (
          <motion.article
            key={item.id}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: idx * 0.08, duration: 0.5 }}
            className="group cursor-pointer"
          >
            <div className="flex flex-col gap-6 border-b border-neutral-200/60 pb-8 lg:flex-row lg:items-start">
              {/* Meta */}
              <div className="flex-shrink-0 lg:w-48">
                <div className="mb-2 flex items-center gap-3 text-sm text-neutral-500">
                  <span className="font-medium text-neutral-700">{item.type}</span>
                </div>
                <div className="flex items-center gap-2 text-sm text-neutral-500">
                  <Calendar size={14} strokeWidth={1.5} />
                  <span>{item.date}</span>
                </div>
              </div>

              {/* Content */}
              <div className="flex-1">
                <h3 className="mb-3 text-2xl font-normal tracking-[-0.01em] text-neutral-900 transition-colors group-hover:text-neutral-700">
                  {item.title}
                </h3>
                <p className="leading-relaxed text-neutral-600 line-clamp-3">
                  {item.description}
                </p>
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
          </motion.article>
        ))}
      </div>

      {/* Load more */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.5, duration: 0.4 }}
        className="mt-12 text-center"
      >
        <button
          type="button"
          className="text-[15px] font-medium text-neutral-600 transition-colors hover:text-neutral-900"
        >
          Load more articles
        </button>
      </motion.div>
    </section>
  );
}