<!-- Updated: 2026-02-16 -->
# Context & Output

### MCP Usage
- **Context7**: Latest library docs — add "use context7" when asking about a library.
- Be mindful of MCP token cost — only use when needed.

### Destructive Actions
Before any destructive action (delete files, drop tables, force push), print:
- **What**: What you're about to do
- **Impact**: What it affects
- **Rollback**: How to undo it

### Output Format
- Short, step-based responses. No long prose.
- Include filenames + minimal diffs or exact commands.
- State how to verify locally (1-2 lines).
