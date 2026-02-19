<!-- Created: 2026-02-18 -->
# Docs Sync

When code changes affect architecture, data flow, component props, or APIs:

1. **Log each change immediately** — append one line to `docs/cc/_pending-docs.md`
   - Example: `- ArticleCard: removed compact variant, added threadTimeline prop`
   - Example: `- news-service.ts: removed processed/relevance_flag filters from getNewsItems()`
2. **Before commit** — read `_pending-docs.md`, update the relevant doc(s) in one pass (see `docs-reference.md` for which doc to update), then delete `_pending-docs.md`.

### Why this pattern
- Survives context compaction (changes are persisted to disk, not just in memory)
- Avoids repeated doc read/write cycles during active coding
- Keeps docs accurate without wasting context on mid-session updates
