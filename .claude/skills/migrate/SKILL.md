---
name: migrate
description: Batch migrate code patterns across files
argument-hint: "<from-pattern> <to-pattern> [directory]"
---

Migrate code from old pattern to new pattern across the codebase:

**Arguments**: `$ARGUMENTS` should be in format: `"old-pattern" "new-pattern" [directory]`

1. **Scan**: Find all files matching the old pattern in the target directory (default: `src/`)
2. **Plan**: List all files and changes needed. Show count and preview 3 examples.
3. **Confirm**: Ask the user to approve before making changes.
4. **Execute**: Apply changes file by file. After each file:
   - Run lint/format
   - Verify no type errors introduced
5. **Report**: Summary of changes made, files modified, any files skipped.

**Examples**:
- `/migrate "require(" "import" src/` — CommonJS to ESM
- `/migrate "getServerSideProps" "generateMetadata" src/app/` — Next.js migration
- `/migrate "styled." "className=" src/components/` — styled-components to Tailwind

**Safety rules**:
- Never modify test files unless explicitly included
- Create a git checkpoint (stash or commit) before starting
- Stop and ask if a file has ambiguous cases
