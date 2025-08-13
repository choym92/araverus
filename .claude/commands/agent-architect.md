# Command: Agent Architect
# Usage: /agent-architect <topic>
# Role: System/feature architect. Output file plan + SSR/CSR boundary.

## Behavior
- Read CLAUDE.md + docs/architecture.md.
- Propose:
  - File plan (create/modify), why each, and line-range targets
  - Data flow diagram (ascii), server/client boundaries
  - Risks & rollback
- Keep to minimal viable changes.