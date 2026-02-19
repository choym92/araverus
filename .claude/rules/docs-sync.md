<!-- Created: 2026-02-19 -->
# Docs Sync

After every `src/` or `scripts/` code change that affects architecture, data flow, component props, or APIs:

1. **Immediately** append one line to `docs/cc/_pending-docs.md`
   - Example: `- ArticleCard: removed compact variant, added threadTimeline prop`
   - Example: `- news-service.ts: removed processed/relevance_flag filters from getNewsItems()`
2. **Before commit** — read `_pending-docs.md`, update the relevant doc(s) in one pass (see `docs-reference.md` for which doc to update), then delete `_pending-docs.md`.

### What NOT to log
- Changes to `CLAUDE.md`, `.claude/rules/`, or other dev-environment config — these are self-documenting
- Changes to `docs/` files themselves (that's the target, not the source)
