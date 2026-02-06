---
name: generate-prd
description: Generate a Product Requirements Document from an idea file. Analyzes the codebase first to understand existing infrastructure, then asks clarifying questions before writing.
user-invocable: true
argument-hint: docs/workflow/1-ideas/[filename].md
model: sonnet
---

# Generate PRD from Idea

## Process

### Phase 1 — Context Gathering
1. **Read Idea File** at `$ARGUMENTS`
2. **Analyze Existing Codebase:**
   - Read `docs/architecture.md` for project structure and tech stack
   - Read `docs/schema.md` for database tables
   - Search for existing code related to the idea (components, services, APIs)
   - Identify reusable patterns, components, and services
3. **Summarize What Exists:**
   - "We already have X, Y, Z that can be leveraged"
   - "Database tables A, B are relevant"
   - "Existing component C can be extended"

### Phase 2 — Clarifying Questions
Ask 5-8 focused questions with lettered options for easy response:
- **Problem/Goal:** "What problem does this solve?"
- **Target User:** "Who is the primary user?"
- **Core Functionality:** "What key actions should be available?"
- **Scope:** "What should it NOT do?"
- **Technical:** "Given we already have [X], should we extend it or build new?"
- **Data:** "What data is needed? Should we use existing tables or new ones?"
- **Design:** "Any UI/UX preferences?"
- **Edge Cases:** "What error scenarios should we handle?"

### Phase 3 — Generate PRD
Use the template at `docs/workflow/2-prds/template.md` and produce:

```markdown
<!-- Created: YYYY-MM-DD -->
# PRD: [Feature Name]

## 1. Overview
Brief description of the feature and the problem it solves.

## 2. Goals
- G1: Specific measurable objective
- G2: Another objective

## 3. User Stories
- US-1: As a [user], I want to [action] so that [benefit]
- US-2: ...

## 4. Functional Requirements
### 4.1 [Subsystem/Area]
- FR-4.1.1: The system must...
- FR-4.1.2: The system must...
### 4.2 [Subsystem/Area]
- FR-4.2.1: ...

## 5. Acceptance Criteria
- AC-1: [Testable condition] — maps to FR-4.1.1
- AC-2: [Testable condition] — maps to FR-4.1.2

## 6. Existing Infrastructure (Auto-generated)
### Can Reuse
- `path/to/existing/file` — [what it provides]
### Needs Modification
- `path/to/file` — [what needs changing]
### New Required
- [New component/service needed]

## 7. Non-Goals (Out of Scope)
- What this will NOT include

## 8. Technical Considerations
- Known constraints and dependencies
- Integration points with existing systems

## 9. Open Questions
- Remaining items needing clarification
```

### Phase 4 — Save
Save as `docs/workflow/2-prds/prd-[feature-name].md`

**DO NOT start implementing.** Wait for user to review and approve the PRD.
