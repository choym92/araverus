# CLAUDE.md
<!-- Updated: 2026-02-17 -->

## Project
Next.js 15 personal site (blog, resume, 3D landing) with a Python news pipeline (news crawl → AI curation → briefing). Stack: TypeScript, Tailwind, Supabase, MDX. Deployed on Vercel (web) + Mac Mini (pipeline cron).

Project-specific rules live in `.claude/rules/`. Detailed docs in `docs/`.

**Before working on any feature area, check `.claude/rules/docs-reference.md` for which docs to read first.** Feature docs are prefixed by number (e.g., `4-news-backend.md`). Always read the relevant doc before making changes.

---

## Critical Behaviors
1) **Language**: All code, comments, and documentation must be in English. Explanations and conversational responses should be in Korean (한국어).
2) **Read before writing**: Read neighboring files and follow existing patterns before making changes.
3) **Server-first**: Next.js App Router uses Server Components by default; use `'use client'` only for interaction/state/DOM APIs.
4) **Edit over create**: Prefer modifying existing files over creating new ones.
5) **Verify deps**: Never assume a library exists; check `package.json` first.
6) **Date stamp**: When creating or modifying `.md` files, add/update `<!-- Created: YYYY-MM-DD -->` or `<!-- Updated: YYYY-MM-DD -->` at top.
7) **No broken contracts**: Never break public API routes, URL paths, or DB schema without explicit approval.

---

## Validation Loop — IMPORTANT
After every code change, you MUST verify your work. This is not optional.

```
Edit code → Run lint → Run build → Fix errors → Repeat until green
```

1) Run `npm run lint` — fix all lint errors before proceeding.
2) Run `npm run build` — fix all type errors before proceeding.
3) If either fails, fix immediately and re-run. **Never proceed with a failing build.**
4) Run `npm run lint:py` if Python scripts changed — fix all ruff errors.
5) Run `npm run lint:secrets` before committing — ensure no secrets leaked.
6) Run `npm run test` if logic changed — ensure tests pass.

---

## Git Conventions
- Branch naming: `feature/short-description`, `fix/short-description`
- Commit messages: imperative mood, concise ("add nav links", not "added nav links")
- Always review staged changes before committing — check for debug code, TODOs, secrets
- Do not push to `main` directly; use feature branches

---

## Anti-Patterns
- Never break public API/URL/DB schema without asking first.
- Never create new files when a focused edit to an existing file suffices.
- Keep responses short: steps, diffs, exact commands. No long prose.
