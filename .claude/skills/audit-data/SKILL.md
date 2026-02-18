---
name: audit-data
description: Audit Supabase tables — statistics, anomalies, and cleanup proposals
user-invocable: true
argument-hint: [table prefix, e.g. "wsj_" or "all"]
---

# Supabase Data Audit

Audit tables matching prefix `$ARGUMENTS` (default: "wsj_").

## Tool
Run SQL via: `python scripts/utils/db_query.py "<SQL>"` (read-only)
For JSON output: `python scripts/utils/db_query.py --json "<SQL>"`

## Phase 1: Discovery
- List all tables matching the prefix:
  ```sql
  SELECT table_name FROM information_schema.tables
  WHERE table_schema = 'public' AND table_name LIKE '<prefix>%'
  ORDER BY table_name
  ```
- For each table: row count, column count, oldest/newest row (by created_at if exists)
- Present summary table to user
- **STOP** — ask user which tables to deep-dive or whether to proceed with all

## Phase 2: Deep Dive (per table)
For each table, dynamically investigate:
- NULL ratios per column
- Value distributions for categorical columns (enum-like: status, type, flag columns)
- Orphan rows (FK references to non-existent parents)
- Stale data (old pending/unprocessed records)
- Duplicates on unique-ish columns (title, url, etc.)
- Outliers (abnormally large/small numeric values)

**Key behavior**: After each query result, THINK about what's unusual and formulate the next query. Don't run a static checklist — adapt based on findings.

## Phase 3: Findings Report
Summarize all findings grouped by severity:
- **Critical**: data integrity issues (orphans, broken FKs)
- **Warning**: stale data, high null rates, suspicious patterns
- **Info**: normal distributions, healthy metrics

## Phase 4: Cleanup Proposals
For each issue found, propose:
- **What**: the cleanup action
- **SQL**: the exact query
- **Impact**: estimated row count (run COUNT first)
- **Reversibility**: can it be undone?

**NEVER execute writes without explicit user approval.**
When approved, use: `python scripts/utils/db_query.py --allow-write "<SQL>"`
Always run `--dry-run` first, show affected count, then ask again before real execution.

## Rules
- Default to read-only queries
- Always show the SQL query before running it
- Present results in markdown tables
- If a table has >100k rows, use sampling (TABLESAMPLE or LIMIT with ORDER BY RANDOM())
- Stop between phases to let user redirect or skip
- Use `--json` when you need to parse results programmatically
- Use `--limit` to cap large result sets
