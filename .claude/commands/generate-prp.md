# Command: Create PRP
# Usage: /generate-prp <path/to/INITIAL.md>
# Goal: Read the feature brief (INITIAL.md), research codebase + docs, and produce a single, executable PRP that enables one-pass implementation.

## Behavior
1) **Plan-only phase (no writes):**
   - Read the feature file at `$ARGUMENTS`.
   - Summarize the goal, constraints, and success criteria.
   - List **codebase references** likely needed (files, symbols, patterns) using *relative paths + line ranges*.
   - List **external references** (exact docs URLs/sections).
   - Stop and print a short plan. **Ask for approval** to generate the PRP.

2) **PRP generation (on approval):**
   - Use `PRPs/templates/prp_base.md` as the skeleton.
   - Fill in *codebase references* with real snippets (small, line-ranged).
   - Include *external references* (URLs to specific sections).
   - Include *Implementation Blueprint* (pseudocode + file plan + error handling).
   - Include *Validation Gates* tailored to this repo (see below).
   - Include *Rollback Plan* and *Risks/Gotchas*.
   - **Save as**: `PRPs/<feature-slug>.md` (slug from feature title or INITIAL filename).
   - Print the output path and confidence score (1–10).

## Research Process
### Codebase Analysis
- Search for similar patterns/components/services/hooks.
- Identify target files to modify vs create.
- Respect **Global Rules** in `CLAUDE.md` (server-first, role-based admin, minimal edits).
- Prefer service layer (e.g., BlogService) and server actions/APIs.

### External Research
- Official docs URLs (Next.js, Supabase, Tailwind, TipTap, Zod, etc.) with anchors.
- 1–2 credible implementation examples (blog/GitHub) if helpful.
- Note common pitfalls (RLS, SSR/client boundaries, auth flows).

### Clarifications (optional)
- If requirement is ambiguous, propose 2–3 precise assumptions and proceed.

## Validation Gates (this repo)
- **Syntax/Style**: `npm run lint`
- **Type Check**: `npm run build` (no emit)
- **Unit Tests (if present)**: `npm run test -s` or `vitest run`
- **Route Smoke** (if routes added): list `curl` examples for new API endpoints
- **A11y minimal**: basic keyboard/focus/aria notes if UI is added

## Output
- Save to `PRPs/<feature-slug>.md`
- Echo:
  - Saved path
  - Files to touch (create/modify)
  - Validation commands
  - Confidence (1–10)

## Quality Checklist
- All necessary **context** (internal + external) included
- **Validation gates** are executable here
- References **existing patterns** in this repo
- **Clear file plan** (minimal edits, server-first)
- **Error handling** and **rollback** documented