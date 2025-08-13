# Command: Generate PR
# Usage: /gen-pr "<scope or title hint>"
# Goal: Create Conventional Commit title+body+test plan from current branch diff.

## Behavior
- Read: `git status`, `git diff --staged` (fallback: last commit).
- Output:
  - Title (conventional): e.g., feat(admin): tags CRUD
  - Body: what/why/how, screenshots TODO, risk/rollback, test plan
  - gh CLI commands (optional) to open PR

## Example gh
```bash
# gh pr create -t "<title>" -b "<body>" -l "area:admin,kind:feature"
```