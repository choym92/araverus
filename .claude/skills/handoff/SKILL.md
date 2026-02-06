---
name: handoff
description: Generate a context handoff document before ending a session or when context is getting long. Saves progress, decisions, and next steps to docs/cc/ for seamless continuation.
user-invocable: true
argument-hint: [optional summary note]
model: haiku
---

# Context Handoff

Generate a handoff document so the next session can continue seamlessly.

## Process

1. **Analyze Current Session:**
   - What was the original goal/task?
   - What was accomplished?
   - What approaches were tried (including failed ones)?
   - What files were created/modified?
   - What decisions were made and why?

2. **Identify Remaining Work:**
   - What's left to do?
   - What blockers exist?
   - What questions need answering?

3. **Capture Context:**
   - Key file paths that matter
   - Important patterns or conventions discovered
   - Any gotchas or tricky parts found

4. **Save to `docs/cc/YYYY-MM-DD.md`:**
   - If file exists, append a new section with `---` separator
   - If not, create it

## Output Format

```markdown
<!-- Updated: YYYY-MM-DD -->
# Session Handoff — YYYY-MM-DD

## What Was Done
- Bullet points of completed work

## Key Decisions
- Decision: [what] — Reason: [why]

## Files Changed
- `path/to/file` — what changed

## Remaining Work
- [ ] Next task 1
- [ ] Next task 2

## Blockers / Questions
- Any open issues

## Context for Next Session
- Important notes, patterns, gotchas
```

If the user provides `$ARGUMENTS`, include it as a summary note at the top.
