<!-- Created: 2026-02-16 -->
# /update-rules — Add Rules from Experience

## Description
Add a "never/always" rule to the appropriate rules file when Claude makes a recurring mistake or when you want to enforce a pattern.

## Usage
```
/update-rules "always use named exports for components"
/update-rules "never use inline styles, use Tailwind classes"
/update-rules "always check auth before DB queries"
```

## Instructions

You add project rules based on patterns the user wants to enforce. This is a first-class workflow for improving Claude's behavior over time.

### Steps

1. **Parse** the user's description of the pattern to remember

2. **Determine target file** based on the rule's category:
   | Category | File |
   |----------|------|
   | General behavior, anti-patterns | `CLAUDE.md` |
   | Code style, components, data, auth | `.claude/rules/conventions.md` |
   | Security, accessibility, testing | `.claude/rules/security-testing.md` |
   | Token strategy, output format | `.claude/rules/context-output.md` |
   | Workflow, skills, automation | `.claude/rules/workflow.md` |

3. **Read** the target file to understand existing rules and formatting

4. **Draft** a concise rule entry:
   - Use "never/always" framing when possible
   - Include a short code example if applicable (GOOD/BAD pattern)
   - Keep it to 2-4 lines max
   - Match the existing formatting style of the file

5. **Show the draft** to the user for approval before writing

6. **Add** the rule to the appropriate section of the target file
   - Update the `<!-- Updated: YYYY-MM-DD -->` date stamp

7. **Confirm** what was added and where

### Rules
- Always show the draft before writing — never auto-commit rules
- Keep rules concise and actionable
- Avoid duplicating existing rules — check first
- Use code examples when the rule is about code patterns
- One rule per invocation; don't batch multiple unrelated rules
