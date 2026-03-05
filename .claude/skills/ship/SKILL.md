---
name: ship
description: Docs-sync, lint, then git add + commit + push. Ensures docs are updated before any code leaves the working tree.
user-invocable: true
argument-hint: <commit message> [--no-push]
model: sonnet
---

# /ship — Commit & Push with Docs Gate

Ship current changes: sync docs, lint, commit, push.

## Arguments

- `$ARGUMENTS` must contain a commit message (imperative mood, e.g. "fix thread sorting")
- If `--no-push` is present, skip the push step
- If no message provided, ask the user for one

## Process

### 1. Pre-flight

- Run `git status` and `git branch --show-current`
- If branch is `main` → **STOP**. Tell user to create a feature branch.
- If working tree is clean → **STOP**. Nothing to ship.

### 2. Docs Sync

Only when `src/` or `scripts/` files are changed:

1. Run `git diff --name-only` to list changed files
2. If no `src/` or `scripts/` changes → skip to step 3
3. Read the diffs for `src/` and `scripts/` files
4. Decide: do these changes affect architecture, data flow, component props, or APIs?
   - **Yes** → read `docs-reference.md` to find the right doc, update it, and note what you changed
   - **No** (CSS-only, typos, formatting) → skip, print "Docs sync: skipped (no API/architecture changes)"
5. If `docs/cc/_pending-docs.md` exists → process it too (update relevant docs, then delete it)

### 3. Lint Gate

Run these checks:

```bash
npm run lint
npm run lint:secrets
```

If `scripts/` files changed, also run:
```bash
npm run lint:py
```

- If lint fails → attempt auto-fix (`npm run lint -- --fix`), re-run
- If still failing → **STOP**. Show errors. Do not commit.

### 4. Stage & Commit

```bash
git add .
git diff --staged --stat
git commit -m "<commit message>"
```

Show the `--stat` output so the user sees what's being committed.

### 5. Push

- If `--no-push` was passed → stop here, print "Committed. Skipped push."
- Otherwise → ask user: "Push to origin/<branch>?"
- On approval → `git push origin <branch>`

## Rules

- Never push to `main`
- Never skip the lint gate
- Commit message must be imperative mood (project convention)
- If docs were updated, they are included in the same commit
