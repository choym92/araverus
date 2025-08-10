'use client';

import { motion, useReducedMotion } from 'framer-motion';

export default function Hero() {
  const reduceMotion = useReducedMotion();

  return (
    <section className="container py-14 sm:py-24">
      <motion.div
        initial={reduceMotion ? false : { opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: 'easeOut' }}
        className="mx-auto w-full max-w-6xl"
      >
        {/* Hero Card */}
        <div className="relative overflow-hidden rounded-3xl bg-white border border-neutral-200/60 p-12 md:p-20 shadow-[0_8px_30px_rgba(0,0,0,.06)] min-h-[70vh] flex items-center">
          {/* Decorative gradient layers (no hit-testing / no a11y exposure) */}
          <div aria-hidden className="pointer-events-none absolute inset-0">
            <div className="absolute inset-0 bg-gradient-to-br from-pink-100 via-purple-50 to-blue-100" />

            <motion.div
              animate={reduceMotion ? {} : { x: [0, 30, 0], y: [0, -30, 0] }}
              transition={reduceMotion ? {} : { duration: 20, repeat: Infinity, ease: 'linear' }}
              className="absolute top-0 left-1/4 h-96 w-96 rounded-full blur-3xl
                         bg-gradient-to-br from-pink-300/40 via-purple-300/40 to-transparent"
            />
            <motion.div
              animate={reduceMotion ? {} : { x: [0, -30, 0], y: [0, 30, 0] }}
              transition={reduceMotion ? {} : { duration: 25, repeat: Infinity, ease: 'linear' }}
              className="absolute bottom-0 right-1/4 h-96 w-96 rounded-full blur-3xl
                         bg-gradient-to-tr from-blue-300/40 via-indigo-300/40 to-transparent"
            />
            <motion.div
              animate={reduceMotion ? {} : { scale: [1, 1.2, 1], opacity: [0.3, 0.5, 0.3] }}
              transition={reduceMotion ? {} : { duration: 15, repeat: Infinity, ease: 'linear' }}
              className="absolute left-1/2 top-1/2 h-[600px] w-[600px] -translate-x-1/2 -translate-y-1/2
                         rounded-full blur-3xl bg-gradient-to-br from-orange-200/30 via-pink-200/30 to-transparent"
            />
          </div>

          {/* Content */}
          <div className="relative z-10 mx-auto text-center">
            <motion.h1
              initial={reduceMotion ? false : { opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2, duration: 0.6 }}
              className="mb-6 text-5xl font-light text-neutral-900 md:text-7xl"
            >
              Introducing GPT-5
            </motion.h1>

            <motion.p
              initial={reduceMotion ? false : { opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3, duration: 0.6 }}
              className="mx-auto mb-10 max-w-3xl text-lg leading-relaxed text-neutral-600 md:text-xl"
            >
              Our smartest, fastest, most useful model yet, with built-in thinking
              that puts expert-level intelligence in everyone&apos;s hands.
            </motion.p>

            {/* CTA */}
            <motion.div
              initial={reduceMotion ? false : { opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.4, duration: 0.6 }}
              className="flex flex-col items-center justify-center gap-4 sm:flex-row"
            >
              <a
                href="#learn-more"
                className="rounded-full bg-neutral-900 px-8 py-3 text-sm font-medium text-white transition
                           hover:bg-neutral-800 active:scale-[0.99]"
              >
                Learn more
              </a>
              <button
                type="button"
                className="rounded-full border border-neutral-300 bg-white px-8 py-3 text-sm font-medium text-neutral-900
                           transition hover:bg-neutral-50 active:scale-[0.99]"
              >
                Get started
              </button>
            </motion.div>
          </div>
        </div>
      </motion.div>
    </section>
  );
}