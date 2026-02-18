<!-- Created: 2026-02-17 -->
# Docs Reference

### Project Documentation Map

**General**
| Doc | Content |
|-----|---------|
| `docs/architecture.md` | Project overview, tech stack, folder structure |
| `docs/schema.md` | All database tables (blog + finance) |

**Blog (3-)**
| Doc | Content |
|-----|---------|
| `docs/blog-writing-guide.md` | MDX blog authoring guide |

**News Platform (4-)**
| Doc | Content |
|-----|---------|
| `docs/4-news-backend.md` | Pipeline scripts, GitHub Actions, crawling, briefing generation |
| `docs/4-news-frontend.md` | `/news` page components, data flow, BriefingPlayer |

**Tooling**
| Doc | Content |
|-----|---------|
| `docs/claude-code-setup.md` | Skills, agents, hooks, automation reference |
| `.claude/rules/tool-usage.md` | When to use Serena vs Read vs Grep |

### Context References
Before working on a specific area, READ the relevant doc first:

| Area | Must-read | Why |
|------|-----------|-----|
| Pipeline scripts / crawling | `docs/4-news-backend.md` | Script flags, crawl logic, cost |
| News frontend / components | `docs/4-news-frontend.md` | Component props, data flow, known hacks |
| DB schema changes | `docs/schema.md` | Column types, relationships, lifecycle |
