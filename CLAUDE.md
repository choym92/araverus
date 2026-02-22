# CLAUDE.md
<!-- Updated: 2026-02-22 -->

## Project
Next.js 15 personal site (blog, resume, 3D landing) with a Python news pipeline (news crawl → AI curation → briefing). Stack: TypeScript, Tailwind, Supabase, MDX. Deployed on Vercel (web) + Mac Mini (pipeline cron).

Project-specific rules live in `.claude/rules/`. Detailed docs in `docs/`.

**Before working on any feature area, check `.claude/rules/docs-reference.md` for which docs to read first.** Feature docs are prefixed by number (e.g., `4-news-backend.md`). Always read the relevant doc before making changes.

---

## Critical Behaviors
1) **Language**: All code, comments, and documentation must be in English. Explanations and conversational responses should be in Korean (한국어).
2) **Read before writing**: Read neighboring files and follow existing patterns before making changes.
3) **Server-first**: Next.js App Router uses Server Components by default; use `'use client'` only for interaction/state/DOM APIs.
4) **Edit over create**: Prefer modifying existing files over creating new ones. This includes idea/doc files — append to existing docs rather than creating new files for related topics.
5) **Verify deps**: Never assume a library exists; check `package.json` first.
6) **Date stamp**: When creating or modifying `.md` files, add/update `<!-- Created: YYYY-MM-DD -->` or `<!-- Updated: YYYY-MM-DD -->` at top.
7) **No broken contracts**: Never break public API routes, URL paths, or DB schema without explicit approval.
8) **Docs sync**: After every `src/` or `scripts/` code change that affects architecture, data flow, props, or APIs — **immediately** append one line to `docs/cc/_pending-docs.md`. Before commit, update the relevant `docs/` file(s) and delete `_pending-docs.md`. Do NOT log changes to `CLAUDE.md`, `.claude/rules/`, or `docs/` files themselves.

---

## Validation Loop — IMPORTANT
After every code change, you MUST verify your work. This is not optional.

```
Edit code → Run lint → Fix errors → Repeat until green
```

1) Run `npm run lint` — fix all lint errors before proceeding.
2) **NEVER run `npm run build` while the dev server is running.** Turbopack's `.next/` cache will corrupt and cause ENOENT 500 errors. The dev server handles type checking automatically via Turbopack.
3) Only run `npm run build` when the dev server is stopped (e.g., before deploy or final verification).
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

## Python Pipeline Rules
When writing or modifying `scripts/*.py` pipeline scripts:

1) **No unnecessary async**: Only use `async/await` if requests are genuinely concurrent. Sequential HTTP calls with delays → use sync `httpx.Client` + `time.sleep`.
2) **Lazy-load heavy deps**: Never load ML models or expensive clients at module level. Use a lazy singleton (`_get_model()` pattern) so `--help` and library imports stay fast.
3) **argparse, not sys.argv**: All CLI scripts must use `argparse`. No manual argv parsing.
4) **One Supabase client**: Use `domain_utils.require_supabase_client()` for CLI commands (fail-fast) or `domain_utils.get_supabase_client()` for optional DB access (returns None). Never duplicate the client creation code.
5) **Correct lifecycle names**: `searched` ≠ `processed` ≠ `briefed`. Use the right term for the pipeline stage. Check `docs/schema.md` for column meanings.
6) **Separation of concerns**: Each script owns one phase. Don't set downstream state (e.g., embedding_rank shouldn't set `crawl_status`).
7) **Step numbering**: Docstrings use `Phase N · Step M · Name` format when multiple scripts share a phase.
8) **Kill dead code**: Remove legacy flags, unused parameters, column-missing fallbacks for completed migrations. Don't keep code "just in case".

---

## Anti-Patterns
- Never break public API/URL/DB schema without asking first.
- Never create new files when a focused edit to an existing file suffices.
- Keep responses short: steps, diffs, exact commands. No long prose.
