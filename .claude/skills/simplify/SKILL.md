---
name: simplify
description: Review changed code for reuse, quality, and efficiency, then fix any issues found
argument-hint: "[file-or-directory]"
---

Review and simplify the code in $ARGUMENTS (or recent changes if no argument):

1. **Find targets**: If no argument given, check `git diff --name-only` for recently changed files. Otherwise use the specified file/directory.

2. **Analyze each file** for:
   - Dead code (unused imports, unreachable branches, commented-out code)
   - Duplication (copy-pasted logic that should be a shared function)
   - Over-engineering (unnecessary abstractions, premature generalization)
   - Unnecessary complexity (nested ternaries, deep callback chains)
   - Missing early returns (deeply nested if/else → guard clauses)

3. **Apply fixes** directly — don't just report. For each fix:
   - Make the minimal change needed
   - Preserve existing behavior
   - Follow existing patterns in neighboring code

4. **Skip these** — don't touch:
   - Test files (unless specifically asked)
   - Generated files
   - Third-party code
   - Config files

5. **After fixing**: Run lint to verify no regressions.

Be aggressive about removing dead code but conservative about restructuring. When in doubt, leave it alone.
