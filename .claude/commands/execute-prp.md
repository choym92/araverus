# Command: Execute PRP
# Usage: /execute-prp <path/to/PRPs/feature.md>
# Goal: Implement the feature described in the PRP with minimal, safe edits and pass all validation gates.

## Ground Rules
- Respect `CLAUDE.md` invariants (server-first, role-based admin, minimal edits, no secrets).
- Prefer editing existing files over creating new ones. Use **line-range** edits.
- **No destructive DB ops** (DROP/MIGRATE) unless PRP explicitly says so and user approves.
- Keep changes small, reviewable, and documented in `docs/cc/YYYY-MM-DD.md`.

## Phases

### Phase 0 — Plan-Only (no writes)
1. Read the PRP file at `$ARGUMENTS`.
2. Summarize:
   - Objective / Scope / Risks
   - **Ordered Task List** (from PRP) → render as a numbered checklist
   - **File plan** (create/modify with relative paths; for modify list line-ranges if known)
   - **Validation Gates** to run (lint/build/tests/route smoke)
3. Print **Plan** and **Diff Preview candidates** (which files/sections will change).
4. **Stop and wait for approval**: `Approve`, `Enhance` (with diffs), or `Block`.

### Phase 1 — Execute (safe, minimal)
_On approval:_
1. For each task in **Ordered Task List**:
   - If **modify**: open file, change only required lines (small patch). Show mini-diff preview.  
   - If **create**: create the minimal file with comments and TODOs from PRP.
   - Use Serena MCP for symbol find/replace if helpful (name_path + relative_path).  
   - Use Context7 MCP only when latest docs required (cite specific URLs in comments).
2. After each logical group (e.g., service → API → UI), **pause for approval** or offer **Apply All**.
3. Keep a running list of changed files.

### Phase 2 — Validate
Run gates in order (stop on failure, suggest fixes, then retry):
- Syntax/Style: `npm run lint`
- Type Check: `npm run build`
- Unit Tests (if present): `npm run test -s` or `vitest run`
- Route Smoke (if PRP adds routes): print ready-to-run `curl` snippets from PRP
- Minimal a11y: keyboard/focus/aria notes if UI added

### Phase 3 — Auto Review & PR
- Run staged diff review (no huge dumps; line-ranged notes only):
  - **/agent-reviewer "staged"**
  - **/review-diff** (optional) to propose minimal patches
- If clean, generate PR text:
  - **/gen-pr "auto from current staged diff"**
- Show exact `git add/commit` and (optional) `gh pr create` commands.

### Phase 4 — EoD Log
- Prepend 5-line summary to `docs/cc/YYYY-MM-DD.md`:
```markdown
## Summary (HH:MM)
- **What**: <short>
- **Why**: <intent>
- **Impact**: <scope/user-visible or none>
- **Verify**: <lint/build/tests/route status>
- **Next**: <follow-up or NONE>
```
- Print changed files list.

## Error Handling & Rollback
- On error, print: failing step, suggested fix, and how to revert:
  - `git restore -SW <files>` or `git reset --hard HEAD~1` (if committed)
- If changes balloon, propose a **smaller first slice** and pause.

## Output Contract
- Do not paste full large files; show small diffs and the exact lines changed.
- Always include: how to run locally, how to test, and any follow-up TODOs.

## Approvals
- Use the reviewer rubric:
  - **Approve** — execute next step or finish
  - **Enhance** — adjust per notes then continue
  - **Block** — stop and print rollback instructions