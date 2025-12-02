'use client';

import Link from 'next/link';
import { motion, useReducedMotion } from 'framer-motion';
import ParticleBackground from './ParticleBackground';

export default function Hero() {
  const reduceMotion = useReducedMotion();

  return (
    <section className="relative min-h-screen flex items-start pt-20 md:pt-24 bg-white">
      {/* Particle Background - visible on right side, hidden on mobile */}
      {!reduceMotion && (
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 z-0 hidden md:block"
        >
          <ParticleBackground className="absolute inset-0 w-full h-full" />
          {/* Gradient mask to fade particles on left side (keep text area clean) */}
          <div className="absolute inset-0 bg-gradient-to-r from-white via-white/80 to-transparent" />
        </div>
      )}

      <div className="relative z-10 w-full px-6 md:px-10 lg:px-16">
        {/* Content - left aligned */}
        <div className="max-w-2xl">
            <motion.h1
              initial={reduceMotion ? false : { opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2, duration: 0.6 }}
              className="mb-6 text-5xl md:text-7xl font-light leading-[1.1] text-neutral-900"
            >
              Continual Learning
            </motion.h1>

            <motion.p
              initial={reduceMotion ? false : { opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3, duration: 0.6 }}
              className="mb-10 max-w-xl text-lg leading-relaxed text-neutral-500 md:text-xl"
            >
              Building AI systems, financial tools, and lifelong learning projects.
            </motion.p>

            {/* CTAs */}
            <motion.div
              initial={reduceMotion ? false : { opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.4, duration: 0.6 }}
              className="flex flex-wrap gap-4"
            >
              <Link
                href="/resume"
                aria-label="View resume"
                className="inline-flex items-center justify-center rounded-full bg-neutral-900 px-8 py-3 text-sm font-medium text-white
                         transition hover:bg-neutral-800 active:scale-[0.98]
                         focus:outline-none focus-visible:ring-2 focus-visible:ring-neutral-900 focus-visible:ring-offset-2"
              >
                MyResume
              </Link>
              <Link
                href="/finance"
                aria-label="Open finance tools"
                className="inline-flex items-center justify-center rounded-full border border-neutral-300 bg-white px-8 py-3 text-sm font-medium text-neutral-900
                         transition hover:bg-neutral-50 active:scale-[0.98]
                         focus:outline-none focus-visible:ring-2 focus-visible:ring-neutral-900 focus-visible:ring-offset-2"
              >
                View Finance Tool
              </Link>
            </motion.div>
          </div>
      </div>
    </section>
  );
}
