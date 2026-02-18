<!-- Created: 2026-02-17 -->
# Tool Usage Guidelines

### Code Reading Strategy
Choose the right tool based on file size and intent:

| Situation | Tool | Why |
|-----------|------|-----|
| File < 200 lines | `Read` | One call, full context, done |
| File > 200 lines, need overview | `Serena get_symbols_overview` | See structure without reading everything |
| File > 200 lines, need specific method | `Serena find_symbol` (include_body) | Read only what you need |
| Refactoring / rename | `Serena find_referencing_symbols` | Precise symbol-level impact analysis |
| Non-code files (.md, .json, .yaml) | `Read` | Serena only understands code symbols |
| Finding a file by name | `Glob` | Faster than Serena's find_file |
| Searching content across files | `Grep` | Faster than Serena's search_for_pattern |

**Rule of thumb**: If you'll need the whole file anyway, just `Read` it. Use Serena for surgical reads on large files.

### MCP Servers
- **Serena**: Code symbol analysis (global, loaded from `~/.claude/config.json`)
- **Context7**: Library docs lookup (project `.mcp.json`)
- **Supabase**: DB operations (project `.mcp.json`)
- **Playwright**: Browser testing (project `.mcp.json`)

Don't use MCP tools when a built-in tool does the job. MCP calls have higher latency.
