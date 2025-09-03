# Araverus Project Overview

## Purpose
Paul Cho's personal website and blog platform built with modern web technologies. Features a MDX-based blog system with zero runtime database dependencies and advanced Claude Code automation.

## Tech Stack
- **Framework**: Next.js 15 (App Router) + React 19 + TypeScript
- **Styling**: Tailwind CSS 4
- **Content**: MDX with static generation
- **Database**: Supabase (auth + admin features)
- **Automation**: Claude Code with PRP workflows
- **Validation**: Zod
- **Animations**: Framer Motion

## Key Principles
- Server-first approach (Server Components by default)
- Edit over create (prefer modifying existing files)
- No over-engineering
- Security-first with defensive programming
- All responses and code must be in English only

## Project Structure
- `src/app` — routes/layouts (server first)
- `src/components` — reusable UI (client only when needed)
- `src/hooks` — custom hooks (browser interactions)
- `src/lib` — services/utils/client generators
- `docs/` — architecture/schema/dev notes
- `content/blog/` — MDX blog posts