<!-- Updated: 2026-02-17 -->
# Feature Development Workflow

### New Feature Flow
```
/plan [description]              → Explore + plan before coding (ALWAYS start here)
/generate-prd [idea file]       → PRD with codebase analysis
/plan-architecture [prd file]   → Technical decisions document
/generate-tasks [prd file]      → Task list with dependencies
/process-tasks [task file]      → Execute one sub-task at a time
```

**IMPORTANT**: Always start new features with `/plan`. Never jump straight into coding.

### Other Skills
- `/handoff` — Save session context for continuation
- `/review [staged|all]` — Code review (runs in forked context)
- `/research [topic]` — Read-only research (no file modifications)
- `/browse [url]` — Browser navigation and visual testing
- `/worktree create [branch]` — Parallel development with git worktrees
- `/update-rules [pattern]` — Add a new rule from experience
- `/generate-status` — Daily status board

### Directory Structure
- `docs/workflow/1-ideas/` — Raw idea files
- `docs/workflow/2-prds/` — PRDs and architecture decisions
- `docs/workflow/3-tasks/` — Task lists
- `docs/cc/` — Session logs, handoffs, status boards

