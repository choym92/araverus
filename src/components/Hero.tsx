'use client';

import Link from 'next/link';
import { motion, useReducedMotion } from 'framer-motion';
import ParticleBackground from './ParticleBackground';

export default function Hero() {
  const reduceMotion = useReducedMotion();

  return (
    <section className="px-6 py-14 sm:py-24">
      <motion.div
        initial={reduceMotion ? false : { opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: 'easeOut' }}
        className="mx-auto w-full max-w-6xl"
      >
        {/* Hero Card */}
        <div className="relative overflow-hidden rounded-3xl bg-white border border-neutral-200/60 p-12 md:p-20 shadow-[0_8px_30px_rgba(0,0,0,.06)] min-h-[70vh] flex items-center">
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

          {/* Content - left aligned */}
          <div className="relative z-10 max-w-2xl">
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
                Resume
              </Link>
              <Link
                href="/finance"
                aria-label="Open finance tools"
                className="inline-flex items-center justify-center rounded-full border border-neutral-300 bg-white px-8 py-3 text-sm font-medium text-neutral-900
                         transition hover:bg-neutral-50 active:scale-[0.98]
                         focus:outline-none focus-visible:ring-2 focus-visible:ring-neutral-900 focus-visible:ring-offset-2"
              >
                Finance
              </Link>
            </motion.div>
          </div>
        </div>
      </motion.div>
    </section>
  );
}
