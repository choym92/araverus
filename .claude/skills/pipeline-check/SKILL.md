---
name: pipeline-check
description: Check the status of the Python finance pipeline — scripts health, GitHub Actions status, database state, and recent run results.
user-invocable: true
context: fork
model: haiku
allowed-tools: Bash(gh *), Bash(python3 *), Bash(git log*), Read, Glob, Grep
---

# Pipeline Status Check

Analyze the current state of the finance data pipeline.

## Checks

1. **GitHub Actions Status:**
   ```bash
   gh run list --workflow=finance-pipeline.yml --limit=5
   ```
   - Last 5 runs: success/failure
   - Any currently running jobs

2. **Script Health:**
   - Check all scripts in `scripts/` exist and have no syntax errors
   - Verify `scripts/requirements.txt` dependencies
   - Check for any TODO/FIXME/HACK comments

3. **Recent Git Activity:**
   - Last commits touching `scripts/` or `.github/workflows/`
   - Any pending changes to pipeline files

4. **Architecture Reference:**
   - Read `docs/architecture-finance-pipeline.md` for expected behavior
   - Compare current state against documented pipeline

## Output Format

```markdown
# Pipeline Status — YYYY-MM-DD

## GitHub Actions
| Run | Date | Status | Duration |
|-----|------|--------|----------|
| #123 | 2026-02-06 | Success | 4m 32s |

## Scripts Health
- wsj_ingest.py: OK
- crawl_ranked.py: OK / WARNING: [issue]

## Recent Changes
- [date] commit message affecting pipeline

## Issues Found
- Any problems detected

## Recommendations
- Suggested actions if any
```
