---
name: generate-tasks
description: Generate a detailed task list from a PRD with dependency analysis, parallel execution markers, and file impact mapping.
user-invocable: true
argument-hint: docs/workflow/2-prds/[filename].md
model: sonnet
---

# Generate Tasks from PRD

## Process

### Phase 1 — Analysis
1. **Read PRD** at `$ARGUMENTS`
2. **Read Architecture Decision Doc** if exists (`docs/workflow/2-prds/arch-*.md`)
3. **Assess Current Codebase:**
   - Review existing files related to the PRD
   - Identify patterns, conventions, test approaches
   - Map existing components that can be extended
4. **Identify All Work Items:**
   - New files to create
   - Existing files to modify
   - Database migrations needed
   - Tests to write

### Phase 2 — Generate Parent Tasks
Present high-level tasks to user:
```
1.0 [Parent Task] — [brief description]
2.0 [Parent Task] — [brief description]
...
```
Say: "High-level tasks ready. Respond with 'Go' to generate sub-tasks."
**Wait for user confirmation.**

### Phase 3 — Generate Full Task List

```markdown
<!-- Created: YYYY-MM-DD -->
# Tasks: [Feature Name]
PRD: `$ARGUMENTS`

## File Impact Map
| File | Action | Task | Description |
|------|--------|------|-------------|
| `src/components/X.tsx` | Create | 2.1 | New component |
| `src/lib/service.ts` | Modify | 1.2 | Add method |
| `supabase/migrations/...` | Create | 1.1 | New table |

## Dependency Graph
```
1.0 Database Setup
 └── 2.0 Backend API (blocked by 1.0)
      ├── 3.0 Frontend Components (blocked by 2.0) ──┐
      └── 4.0 Tests (blocked by 2.0) ────────────────┤
                                                       └── 5.0 Integration (blocked by 3.0, 4.0)
```

## Tasks

### 1.0 [Parent Task] `[SEQUENTIAL]`
> Depends on: none | Blocks: 2.0
> PRD refs: FR-4.1.1, FR-4.1.2

- [ ] 1.1 [Sub-task with specific instructions]
  - Files: `path/to/file`
  - What: Exact description of changes
- [ ] 1.2 [Sub-task]
  - Files: `path/to/file`
  - What: Exact description

### 2.0 [Parent Task] `[PARALLEL with 3.0]`
> Depends on: 1.0 | Blocks: 4.0
> PRD refs: FR-4.2.1

- [ ] 2.1 [Sub-task]
  - Files: `path/to/file`
  - What: Exact description
```

### Markers
- `[SEQUENTIAL]` — must be done in order
- `[PARALLEL with X.0]` — can be done simultaneously with task X
- `[BLOCKED by X.0]` — cannot start until X.0 is complete

## Save
Save as `docs/workflow/3-tasks/tasks-[feature-name].md` using template at `docs/workflow/3-tasks/template.md`.
