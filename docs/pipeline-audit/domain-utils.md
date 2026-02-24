<!-- Created: 2026-02-22 -->
# Audit: domain_utils.py

Shared Utility · Domain & Lifecycle — 756 LOC (post-refactor, minimal changes)

---

## Why This Script Exists

Dual-purpose: **library** (imported by 7 scripts) + **CLI tool** (7 subcommands).

**Library role:** Provides the canonical Supabase client, blocked domain queries, and Wilson score calculation. Every pipeline script that touches the DB imports from here.

**CLI role:** Pipeline lifecycle operations — marking items searched/processed, updating domain status scores, retrying low-relevance items.

**Why not split?** The library functions and CLI commands share the same internal helpers (Supabase client, domain queries). Splitting would create circular dependencies or duplicate code.

---

## CLI Commands (7)

| Command | Pipeline Phase | What It Does |
|---------|---------------|--------------|
| `--mark-searched FILE` | Phase 2 | Mark WSJ items in JSONL as searched |
| `--mark-processed FILE` | Phase 4 | Mark items in JSONL as processed |
| `--mark-processed-from-db` | Phase 4 | Query crawl_results → mark items with good crawls as processed |
| `--update-domain-status` | Phase 4 | Aggregate crawl results → Wilson score → auto-block bad domains |
| `--retry-low-relevance` | Manual | Reactivate skipped backups for items with only low-relevance crawls |
| `--stats` | Manual | Show database statistics |
| `--seed-blocked-from-json` | One-time | Migrate blocked_domains.json to DB |

**Pipeline calls** (`run_pipeline.sh`):
```bash
L62: $VENV "$SCRIPTS/domain_utils.py" --mark-searched "$SCRIPTS/output/wsj_items.jsonl"
L72: $VENV "$SCRIPTS/domain_utils.py" --mark-processed-from-db
L73: $VENV "$SCRIPTS/domain_utils.py" --update-domain-status
```

Non-fatal (WARN) — pipeline continues if these fail.

---

## Library Exports (imported by other scripts)

| Function | Consumers | Purpose |
|----------|-----------|---------|
| `get_supabase_client()` | wsj_to_google_news, resolve_ranked | Optional client (returns None if no creds) |
| `require_supabase_client()` | wsj_preprocess | CLI fail-fast (sys.exit if no creds) |
| `load_blocked_domains()` | wsj_to_google_news, crawl_ranked, crawl_article, ab_test_pipeline | Set of blocked domain strings from DB |
| `is_blocked_domain()` | crawl_article, ab_test_pipeline | Substring matching (catches subdomains) |
| `wilson_lower_bound()` | (internal) | Wilson score 95% CI for auto-blocking |

---

## Key Logic: Auto-Blocking (`cmd_update_domain_status`)

1. Fetch all `wsj_crawl_results` (paginated, 1000-row batches)
2. Aggregate by domain: success vs failure counts
3. Normalize historical error strings to natural language keys
4. Exclude content mismatch reasons ("low relevance", "llm rejected") from blocking — not the domain's fault
5. Calculate Wilson lower bound on blockable-only failures
6. Auto-block if: `wilson < 0.15` AND `blockable_total >= 5`
7. Upsert to `wsj_domain_status` with per-reason `fail_counts` JSONB

---

## Data Flow

```
[Library role]
Other scripts ──import──→ get_supabase_client(), load_blocked_domains(), etc.

[CLI role: Phase 2]
wsj_items.jsonl ──mark-searched──→ wsj_items.searched = true

[CLI role: Phase 4]
wsj_crawl_results ──mark-processed-from-db──→ wsj_items.processed = true
wsj_crawl_results ──update-domain-status──→ wsj_domain_status (wilson scores)
```

---

## Shared Dependencies

| Module | What's Used | Why |
|--------|-------------|-----|
| `supabase` | `create_client` | DB operations (lazy import) |
| `dotenv` | `load_dotenv` | Standalone dev testing (.env.local) |

---

## Refactoring Notes

### Done (this session)
- Manual `sys.argv` dispatch → `argparse` with `mutually_exclusive_group`
- Fixed Phase label: "Phase 4" → "Shared Utility" (used in Phase 2 and Phase 4)
- Updated library exports documentation in docstring

### Not Changed
| Pattern | Why Kept |
|---------|----------|
| `load_dotenv()` on every `get_supabase_client()` call | Idempotent, needed for standalone dev testing |
| `is_blocked_domain()` substring matching | Intentional — catches subdomains (m.wsj.com → wsj.com) |
| N+1 Supabase inserts/updates | Working pattern, within acceptable scale |
| `cmd_seed_blocked_from_json` | One-time migration, `blocked_domains.json` still exists. Keep until confirmed run |
| Dual library+CLI pattern | Functions and commands share helpers; splitting creates circular deps |
| `sys.path.insert(0, ...)` not present | This file IS the shared module others import from |

### Questions
| Item | Question |
|------|----------|
| `--seed-blocked-from-json` | Has this migration been run? If so, safe to remove function + data file |
