---
name: review
description: Review current staged or unstaged changes for security, quality, and correctness. Runs in a forked context to preserve the main conversation.
user-invocable: true
argument-hint: [optional: staged|all|file path]
context: fork
model: sonnet
allowed-tools: Bash(git diff*), Bash(git log*), Bash(git status*), Bash(npm run lint*), Bash(npm run build*), Read, Glob, Grep, WebSearch
---

# Code Review

Review current changes in the working tree.

## Scope

- If `$ARGUMENTS` is "staged" or empty: review `git diff --staged`
- If `$ARGUMENTS` is "all": review `git diff` (all changes)
- If `$ARGUMENTS` is a file path: review only that file's changes

## Review Checklist

1. **Security**
   - No secrets, API keys, or credentials in code/comments
   - Input validation on user-facing surfaces
   - No XSS vectors (`dangerouslySetInnerHTML`, unsanitized URLs)
   - Auth guards on protected routes/APIs

2. **Next.js Patterns**
   - Server Components by default, `"use client"` only when needed
   - No client-side Supabase mutations
   - Proper cache/revalidation directives

3. **Code Quality**
   - TypeScript types (no `any` without justification)
   - Consistent error handling
   - Follows existing patterns in neighboring files

4. **Database**
   - Service layer used (not direct DB calls from components)
   - RLS/role checks for admin operations

5. **Accessibility**
   - No `alert()` — use accessible UI
   - ARIA attributes, focus management, color contrast

## Output Format

For each file changed:
```
### path/to/file.tsx
- L12-15: [Security] Direct user input without sanitization → add validation
- L23: [Quality] `any` type → use proper interface
- Overall: LGTM / Issues found
```

**Final Verdict:** LGTM or BLOCK with issue count

Also run `npm run lint` and `npm run build` to catch type/lint errors.
