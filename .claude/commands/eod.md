# Command: End-of-Day Log
# Usage: /eod
# Goal: Prepend 5-line summary to docs/cc/YYYY-MM-DD.md (create if missing).

## Behavior
- Compute today (YYYY-MM-DD). Create docs/cc/ if needed.
- Gather:
  - Changed files (last 24h): `git log --since="24 hours ago" --name-only --pretty="" | sort -u`
  - Last 30 lines from .claude/logs/bash.log if present
- Prepend block:

```markdown
## Summary (HH:MM)
- **What**: <short>
- **Why**: <intent>
- **Impact**: <scope/user-visible or none>
- **Verify**: <lint/build/tests/route-smoke status>
- **Next**: <follow-up or NONE>
```

- Save, stage, and suggest commit.