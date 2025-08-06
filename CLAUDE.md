# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Araverus is an AI-powered SEC filing screener and market dashboard - a financial intelligence platform that democratizes institutional-grade analysis through AI-powered SEC filing interpretation. The platform combines a sophisticated stock screener with natural language processing of regulatory documents.

## Common Development Commands

- **Development server**: `npm run dev` (starts Next.js dev server on http://localhost:3000)
- **Build project**: `npm run build` (creates production build)
- **Start production**: `npm start` (starts production server)  
- **Lint code**: `npm run lint` (runs ESLint with Next.js config)

## Architecture & Tech Stack

### Frontend Architecture
- **Framework**: Next.js 15 with App Router
- **UI**: React 19 + TypeScript 5
- **Styling**: Tailwind CSS 4 with custom theme system
- **Fonts**: Geist Sans & Geist Mono (optimized with next/font)

### Planned Architecture (from project documentation)
- **Backend**: Supabase (BaaS) for database, auth, storage
- **AI Processing**: Python FastAPI microservice with LangChain + OpenAI
- **External APIs**: SEC EDGAR API, Alpha Vantage for market data
- **Deployment**: Vercel (frontend) + containerized AI service

### Key Configuration
- **TypeScript**: Strict mode enabled with path aliases (`@/*` → `./src/*`)
- **ESLint**: Uses Next.js core-web-vitals and TypeScript configs
- **CSS**: Tailwind with CSS custom properties for theming (supports dark mode)

## Code Conventions

### File Structure
- `src/app/` - Next.js App Router pages and layouts
- `src/app/globals.css` - Global styles with Tailwind imports and custom CSS variables
- Public assets in `public/` directory

### Styling Approach
- Uses Tailwind CSS 4 with `@theme inline` configuration
- Custom CSS variables for theming (`--background`, `--foreground`, etc.)
- Built-in dark mode support via `prefers-color-scheme`
- Geist font variables available as `--font-geist-sans` and `--font-geist-mono`

### Component Patterns
- TypeScript interfaces for props with `Readonly<>` wrapper for children
- Metadata exports for SEO in page components
- CSS custom properties integrated with Tailwind theme system

## Development Notes

### Current State
- Early scaffold phase with basic Next.js setup
- Homepage displays project branding with Tailwind styling
- Supabase dependencies installed but not yet integrated
- Project follows phased development approach (MVP → Fast Follow → Monetization)

### Key Dependencies
- **Frontend**: Next.js 15, React 19, TypeScript 5, Tailwind CSS 4
- **Database**: Supabase packages (@supabase/ssr, @supabase/supabase-js)
- **Development**: ESLint with Next.js configs

### Planned Features (from project docs)
- SEC filing analysis with AI-powered summaries
- Stock screener with advanced filtering
- User authentication via Supabase Auth
- Watchlists and notification system
- Real-time market data integration