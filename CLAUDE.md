# CLAUDE.md
This file provides guidance to Claude Code (claude.ai/code) when working in this repository.
**Invariant global rules only.** Detailed architecture/schema/notes live in `README.md` or `docs/`.

---

## 🚨 GLOBAL RULES — ALWAYS FOLLOW THESE (Invariant)

### Critical Behaviors
1) **BEFORE change**: Read neighboring files; follow existing patterns.  
2) **AFTER change**: Run `npm run lint` and `npm run build` (type check).  
3) **VERIFY deps**: Never assume a library exists; check `package.json`.  
4) **EDIT over CREATE**: Prefer modifying existing files/components.  
5) **Server-first**: Next.js App Router uses **Server Components by default**; use Client **only** for interaction/state/DOM APIs.

### Power Keywords & Enhanced Behaviors
- **IMPORTANT**: Must not be overlooked.  
- **PROACTIVELY**: Propose safe improvements within these rules.  
- **VERIFY**: Validate changes with checks/tests and a short runbook note.  
- **SECURITY-FIRST**: Treat inputs, secrets, and errors defensively.  
- **Be concise**: Output is short, actionable, copy-pastable.

### Anti-Patterns to Avoid
- ❌ **Over-engineering** (unneeded abstractions/deps/complexity).  
- ❌ **Breaking public contracts**: Keep public API/URL/DB schema compatible. (Internal/private pieces may be changed.)  
- ❌ Creating new files when a focused edit suffices.  
- ❌ Long prose; prefer steps, diffs, and exact commands.

### Automation Checklist (Every task)
- [ ] `npm run lint` (fix issues)  
- [ ] `npm run build` (fix type errors)  
- [ ] Manual verify in browser; check console for errors  
- [ ] Ensure **no secrets** in code/logs/diffs  
- [ ] Add/update a minimal test (happy + one edge) if logic changed  
- [ ] Append change summary to `docs/cc/YYYY-MM-DD.md` (what/why/how)

---

## 🏗️ PROJECT-SPECIFIC RULES (Stable Defaults)

### Conventions
1) **Auth**: Protected routes/pages must pass `useAuth` **or** server-side session/role check.  
2) **Data**: Use the service layer (e.g., `BlogService`) for DB logic; call explicitly from server actions/APIs when needed.  
3) **Admin**: **No hardcoded emails**. Use `user_profiles.role = 'admin'` (RLS/policies enforced) for authorization.  
4) **Styling**: Tailwind only; avoid inline styles (except utility overrides when justified).  
5) **Components**: **Server by default**; add `'use client'` only when truly required.

### Security · A11y · Testing (Minimum)
- **Secrets**: Live only in `.env*`; never commit. Mask in logs/errors.  
- **A11y**: ARIA, focus management, color contrast; never `alert()` as UX—use accessible error UI.  
- **Tests**: For new/changed logic, provide at least **1 happy + 1 edge** unit test. E2E optional.

### Token/Context Strategy & Tools
- **Large files**: Read/edit by **line range** or summaries—avoid full-file context.  
- **MCP**:  
  - **Serena** for semantic code search/refactors/cross-refs.  
  - **Context7** for "latest official docs" — explicitly say **"use context7"** when needed.  
- **Hooks**: Before any destructive action, print a 3-line note: **What / Impact / Rollback**. Keep Bash/Write/Edit logging on.

### Output Contract
- Keep responses **short and step-based**.  
- Include filenames + minimal diffs or exact commands.  
- State how to run/verify locally (1–2 lines).  
- Document changes in `docs/cc/YYYY-MM-DD.md`.

---

## Project Overview (Pointer)
- Architecture, schema, dependencies, editor/animation details → **move to** `README.md` / `docs/` and keep this file invariant.