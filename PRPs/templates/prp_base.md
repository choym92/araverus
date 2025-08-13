# PRP: <Feature Title>

## Objective
- Short 1–2 lines describing the feature and user impact.

## Scope
- In-scope:
- Out-of-scope:

## Constraints & Global Rules
- Follow `CLAUDE.md` (server-first, role-based admin, minimal edits).
- Use existing patterns (services, hooks, folder conv).
- No secrets in code; no destructive DB ops.

## Codebase References (exact)
- <path>:Lx–Ly — why relevant
- <path>:Lx–Ly — pattern to mirror
- (Prefer **small line ranges**, not whole files.)

## External References (URLs)
- Next.js doc (section): <url>
- Supabase doc (section): <url>
- TipTap/Zod/etc: <url>

## Implementation Blueprint
- **Pseudocode** of the flow (SSR/CSR boundaries clear)
- **File plan** (create/modify):
  - Create: `src/app/.../page.tsx` (server component)
  - Modify: `src/lib/...service.ts` (add method X)
- **Error handling** (what to show, where to log)
- **Security/A11y** notes (role checks, aria/focus)

## Ordered Task List
1) Update/create files: [...]
2) Add service method(s): [...]
3) Add route/API (if needed): [...]
4) Wire UI → service → API
5) Tests (unit + optional E2E)
6) Docs: `docs/cc/YYYY-MM-DD.md` entry

## Validation Gates (must run)
- Syntax/Style: `npm run lint`
- Type Check: `npm run build`
- Unit tests (if present): `npm run test -s`
- Route smoke (if any):
  - `curl -I https://localhost:3000/api/...`
- Manual: open `/path`, try happy + edge

## Rollback Plan
- `git restore -SW <files>` or revert commit
- Feature-flag or route-level guard off (if applicable)

## Risks & Gotchas
- RLS/role interactions
- Server/Client boundary
- Large payloads/tokens: prefer line-range reads

## Definition of Done
- All gates pass
- Minimal edits only; server-first respected
- Docs updated (`docs/cc/…` 5-line summary)

## Confidence
- Score (1–10): X
- Why: (2–3 bullets)