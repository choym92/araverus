<!-- Updated: 2026-02-23 -->
# Docs Sync

After every `src/` or `scripts/` code change that affects architecture, data flow, component props, or APIs:

1. **Immediately** append one line to `docs/cc/_pending-docs.md`
   - Example: `- ArticleCard: removed compact variant, added threadTimeline prop`
   - Example: `- news-service.ts: removed processed/relevance_flag filters from getNewsItems()`
2. **Before commit** — read `_pending-docs.md`, update the relevant doc(s) in one pass (see `docs-reference.md` for which doc to update), then delete `_pending-docs.md`.

### Sync Targets

Feature docs (`1-news-backend.md`, `2-news-frontend.md`, etc.) are updated per the `_pending-docs.md` workflow above.

**`docs/architecture.md`** — update when:
- Tech stack changes (new library, framework upgrade, provider swap)
- New top-level feature area added or removed
- Folder structure changes significantly
- Environment variables added or removed

**`docs/schema.md`** — update when:
- Columns added, removed, or type-changed
- New tables created or tables dropped
- RLS policies added or modified
- Lifecycle states change (e.g. new status value in `searched`/`processed`/`briefed`)
- Indexes or constraints added

Check `docs-reference.md` for the full doc map.

### What NOT to log
- Changes to `CLAUDE.md`, `.claude/rules/`, or other dev-environment config — these are self-documenting
- Changes to `docs/` files themselves (that's the target, not the source)
