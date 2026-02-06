# CLAUDE.md
<!-- Updated: 2026-02-06 -->
This file provides guidance to Claude Code (claude.ai/code) when working in this repository.
**Invariant global rules only.** Detailed architecture/schema/notes live in `docs/`.

---

## GLOBAL RULES — ALWAYS FOLLOW THESE

### Critical Behaviors
1) **BEFORE change**: Read neighboring files; follow existing patterns and coding style.
2) **AFTER change**: Run `npm run lint` and `npm run build` (type check).
3) **VERIFY deps**: Never assume a library exists; check `package.json`.
4) **EDIT over CREATE**: Prefer modifying existing files/components over creating new ones.
5) **DATE STAMP**: When creating or modifying .md files, always add/update commented date at top (`<!-- Created: YYYY-MM-DD -->` or `<!-- Updated: YYYY-MM-DD -->`).
6) **Server-first**: Next.js App Router uses **Server Components by default**; use Client **only** for interaction/state/DOM APIs.

### Language Rules
**CRITICAL**: Always respond in English, even when prompted in other languages. All code, comments, documentation, and responses must be in English only.

### Power Keywords
- **IMPORTANT**: Must not be overlooked.
- **PROACTIVELY**: Propose safe improvements within these rules.
- **VERIFY**: Validate changes with checks/tests and a short runbook note.
- **SECURITY-FIRST**: Treat inputs, secrets, and errors defensively.
- **Be concise**: Output is short, actionable, copy-pastable.

### Anti-Patterns to Avoid
- Over-engineering (unneeded abstractions/deps/complexity).
- Breaking public contracts: Keep public API/URL/DB schema compatible.
- Creating new files when a focused edit suffices.
- Long prose; prefer steps, diffs, and exact commands.

### Automation Checklist (Every task)
- [ ] `npm run lint` (fix issues)
- [ ] `npm run build` (fix type errors)
- [ ] Manual verify in browser; check console for errors
- [ ] Ensure **no secrets** in code/logs/diffs
- [ ] Add/update a minimal test (happy + one edge) if logic changed

---

## PROJECT-SPECIFIC RULES

### Conventions
1) **Auth**: Protected routes/pages must pass `useAuth` **or** server-side session/role check.
2) **Data**: Use the service layer (e.g., `BlogService`) for DB logic; call explicitly from server actions/APIs when needed.
3) **Admin**: **No hardcoded emails**. Use `user_profiles.role = 'admin'` (RLS/policies enforced) for authorization.
4) **Styling**: Tailwind only; avoid inline styles (except utility overrides when justified).
5) **Components**: **Server by default**; add `'use client'` only when truly required.

### Security / A11y / Testing (Minimum)
- **Secrets**: Live only in `.env*`; never commit. Mask in logs/errors.
- **A11y**: ARIA, focus management, color contrast; never `alert()` as UX—use accessible error UI.
- **Tests**: For new/changed logic, provide at least **1 happy + 1 edge** unit test. E2E optional.

### Token/Context Strategy
- **Large files**: Read/edit by **line range** or summaries—avoid full-file context.
- **MCP**: Use Serena for codebase understanding; Context7 for latest library docs (add "use context7" to prompts).
- **Hooks**: Before any destructive action, print a 3-line note: **What / Impact / Rollback**.

### Output Contract
- Keep responses **short and step-based**.
- Include filenames + minimal diffs or exact commands.
- State how to run/verify locally (1-2 lines).

---

## FEATURE DEVELOPMENT WORKFLOW

```
/generate-prd [idea file]     → PRD with codebase analysis
/plan-architecture [prd file] → Technical decisions document
/generate-tasks [prd file]    → Task list with dependencies
/process-tasks [task file]    → Execute one sub-task at a time
```

**Directory structure:**
- `docs/workflow/1-ideas/` — Raw idea files
- `docs/workflow/2-prds/` — PRDs and architecture decisions
- `docs/workflow/3-tasks/` — Task lists
- `docs/cc/` — Daily session logs and status board

**Other skills:**
- `/handoff` — Save session context for continuation
- `/plan [description]` — Implementation plan before coding
- `/review [staged|all]` — Code review (runs in forked context)
- `/research [topic]` — Read-only research (no file modifications)
- `/pipeline-check` — Finance pipeline health status
- `/generate-status` — Daily status board

---

## DOCS REFERENCE

| Doc | Content |
|-----|---------|
| `docs/architecture.md` | Project overview, tech stack, folder structure |
| `docs/architecture-finance-pipeline.md` | Finance pipeline deep dive (all scripts, DB, workflow) |
| `docs/schema.md` | All database tables (blog + finance) |
| `docs/project-history.md` | Project evolution timeline |
| `docs/auth-migration-guide.md` | Auth migration reference |
| `docs/blog-writing-guide.md` | MDX blog authoring guide |
| `docs/claude-code-setup.md` | Skills, agents, hooks, automation reference |
