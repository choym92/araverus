---
name: generate-status
description: Generate a daily status board from git commits and session logs
user-invocable: true
---

# Generate Daily Status Board

## Process

1. **Read Existing Status Board:** Check if `docs/cc/status-board.md` exists to preserve history.
2. **Gather Today's Data:**
   - Git commits from today (`git log --since="midnight"`)
   - Current session file (`docs/cc/YYYY-MM-DD.md`)
   - Task files in `docs/workflow/3-tasks/`
3. **Generate Today's Status Section:**
   - **Done Today:** Completed items from git commits and session logs
   - **In Progress:** Current tasks being worked on
   - **Next Up:** Immediate upcoming tasks
4. **Update Status Board:** Prepend new section with today's date. Keep all history below.

## Output Format

```markdown
# Araverus Status Board
<!-- Updated: YYYY-MM-DD -->

## YYYY-MM-DD
Done Today:
- Brief description [commit-hash]

In Progress:
- Current task

Next Up:
- Next priority task

---

## Previous Date
[Previous entries...]
```

## Guidelines
- Each bullet = one line, no explanations
- Max ~10 lines per day
- Git commits = strongest signal for "Done"
- NEVER delete old entries, always prepend
