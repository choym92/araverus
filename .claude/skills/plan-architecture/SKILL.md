---
name: plan-architecture
description: Create a technical architecture decision document between PRD and task generation. Resolves technology choices, database changes, API design, and integration patterns before breaking into tasks.
user-invocable: true
argument-hint: docs/workflow/2-prds/[prd-file].md
model: sonnet
---

# Architecture Decision Document

Bridge the gap between PRD and task generation by making all technical decisions upfront.

## Process

1. **Read the PRD** at `$ARGUMENTS`
2. **Analyze Current Codebase:**
   - Read `docs/architecture.md` for project structure
   - Read `docs/schema.md` for database tables
   - Read `docs/architecture-finance-pipeline.md` if finance-related
   - Search for existing implementations related to the PRD requirements
3. **Identify Technical Decisions Needed:**
   - What existing code can be reused?
   - What new patterns or libraries are needed?
   - What database changes are required?
   - What API endpoints need creating/modifying?
   - What are the integration points?

4. **For Each Decision, Present Options:**

```markdown
# Architecture: [Feature Name]
<!-- Created: YYYY-MM-DD -->

## PRD Reference
`$ARGUMENTS` — [one-line summary]

## Existing Infrastructure
- What we already have that's relevant
- Files, components, services to leverage

## Technical Decisions

### TD-1: [Decision Title]
**Question:** How should we implement X?

| Option | Pros | Cons |
|--------|------|------|
| A: [approach] | Fast, simple | Limited scalability |
| B: [approach] | Scalable | More complex |

**Decision:** [A or B] — [reasoning]

### TD-2: [Decision Title]
...

## Database Changes
| Table | Change | Migration Notes |
|-------|--------|-----------------|
| `table_name` | Add column `x` | Default value, backward compatible |

## API Changes
| Endpoint | Method | Change |
|----------|--------|--------|
| `/api/x` | POST | New endpoint |

## File Impact Map
| File | Change Type | Depends On |
|------|-------------|------------|
| `src/...` | Modify | TD-1 |
| `src/...` | Create | TD-2 |

## Risks
- Risk 1 → Mitigation
- Risk 2 → Mitigation
```

5. **Save** to `docs/workflow/2-prds/arch-[feature-name].md`
6. **Wait for user approval** before proceeding to task generation
