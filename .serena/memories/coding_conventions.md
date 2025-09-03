# Coding Conventions and Style Guide

## Code Style
- **Language**: All code, comments, and documentation must be in English only
- **TypeScript**: Strict typing, prefer explicit types over `any`
- **Server Components**: Default approach, use `'use client'` only when necessary
- **Tailwind CSS**: Only utility classes, avoid inline styles except for justified overrides
- **File naming**: kebab-case for files, PascalCase for components

## Architecture Patterns
- **Service Layer**: Use service classes (e.g., `BlogService`) for DB operations
- **Auth**: Protected routes must use `useAuth` or server-side session checks
- **Admin**: Use `user_profiles.role = 'admin'` for authorization, no hardcoded emails
- **Data Flow**: Server actions/API routes → Service Layer → Database

## Security & Quality
- **Secrets**: Live only in `.env*` files, never commit, mask in logs
- **A11y**: ARIA attributes, focus management, color contrast
- **Error Handling**: Accessible error UI, never use `alert()`
- **RLS**: Row Level Security policies enforced for data access

## Anti-Patterns to Avoid
- Over-engineering (unnecessary abstractions/dependencies/complexity)
- Breaking public contracts (keep API/URL/DB schema compatible)
- Creating new files when focused edits suffice
- Long prose responses (prefer steps, diffs, exact commands)