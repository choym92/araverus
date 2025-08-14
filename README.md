# Araverus

Paul Cho's personal website and blog platform built with Next.js 15, React 19, and TypeScript. Features a modern MDX-based blog system with zero runtime database dependencies and advanced Claude Code automation.

## Tech Stack

- **Framework**: Next.js 15 (App Router) + React 19 + TypeScript
- **Styling**: Tailwind CSS 4
- **Content**: MDX with static generation
- **Database**: Supabase (auth + admin features)
- **Automation**: Claude Code with PRP workflows

## Getting Started

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build
```

Open [http://localhost:3000](http://localhost:3000) to view the site.

## Environment Setup

Create `.env.local`:
```bash
NEXT_PUBLIC_SUPABASE_URL=your_supabase_url
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_supabase_anon_key
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key
NEXT_PUBLIC_SITE_URL=http://localhost:3000
```

## Blog Content

Posts are written in MDX format in `content/blog/`. Use `/new-post <slug>` command to create new posts with proper structure.

## Documentation

See `CLAUDE.md` for development guidelines and `docs/` for detailed documentation.