---
name: plan
description: Create an implementation plan before writing code. Analyzes the codebase, identifies affected files, proposes approach, and waits for approval. Use when starting any non-trivial feature or change.
user-invocable: true
argument-hint: [feature or task description]
model: sonnet
---

# Implementation Plan

Create a detailed implementation plan before writing any code.

## Process

1. **Understand the Request:**
   - Parse `$ARGUMENTS` for the feature/task description
   - If unclear, ask clarifying questions

2. **Analyze Codebase:**
   - Read `docs/architecture.md` for project structure
   - Read `docs/schema.md` for database context
   - Search for related existing code (components, services, utils)
   - Identify patterns and conventions in use

3. **Produce Plan:**

```markdown
# Plan: [Feature Name]

## Goal
One sentence describing what we're building and why.

## Current State
- What exists today that's relevant
- Existing files/components we'll modify or extend

## Proposed Approach
### Option A (Recommended)
- Step-by-step implementation
- Why this approach

### Option B (Alternative)
- Different approach
- Trade-offs

## Files to Change
| File | Action | Description |
|------|--------|-------------|
| `src/...` | Modify | Add X to Y |
| `src/...` | Create | New component for Z |

## Database Changes
- Any new tables/columns needed (or "None")

## Risks & Considerations
- What could go wrong
- Performance implications
- Security considerations

## Open Questions
- Anything needing user input before proceeding
```

4. **Wait for Approval:**
   - Present the plan
   - Do NOT implement until user says "go" or "approved"
