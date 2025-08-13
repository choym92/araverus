# Command: Review Diff (staged)
# Usage: /review-diff
# Goal: Review staged git changes and propose safe fixes.

## Behavior
- Run: `git diff --staged` (or equivalent tool) and summarize by file.
- For each file: risks → exact lines → minimal patch suggestion.
- End with: "Apply?" checkpoint. On approval, create patch via mini edits.