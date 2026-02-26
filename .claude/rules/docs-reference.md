<!-- Updated: 2026-02-25 -->
# Docs Reference

### Project Documentation Map

**General**
| Doc | Content |
|-----|---------|
| `docs/architecture.md` | Project overview, tech stack, folder structure (sync target — see `docs-sync.md`) |
| `docs/schema.md` | All database tables, columns, RLS policies (sync target — see `docs-sync.md`) |
| `docs/roadmap.md` | Project direction — 3-phase priorities |

**News Backend (1.x)**
| Doc | Content |
|-----|---------|
| `docs/1-news-backend.md` | Pipeline scripts, crawling, briefing generation |
| `docs/1.1-news-google-search.md` | Google News search flow, domain blocking layers, -site: logic |
| `docs/1.2-news-threading.md` | Thread grouping algorithm, scoring |
| `docs/1.2.1-reranker-causal-test.md` | Cross-encoder reranker experiment for threading + causal detection |
| `docs/1.3-embedding-ab-test.md` | Embedding model A/B test results |
| `docs/1.4-news-scoring-tuning.md` | Scoring pipeline thresholds, tuning infrastructure |
| `docs/pipeline-audit/` | Per-script audit docs (8 files) |

**News Frontend (2.x)**
| Doc | Content |
|-----|---------|
| `docs/2-news-frontend.md` | `/news` page components, data flow, BriefingPlayer |

**Blog (3.x)**
| Doc | Content |
|-----|---------|
| `docs/3-blog-writing-guide.md` | MDX blog authoring guide |

**Tooling**
| Doc | Content |
|-----|---------|
| `docs/claude-code-setup.md` | Skills, agents, hooks, automation reference |
| `.claude/rules/tool-usage.md` | When to use Serena vs Read vs Grep |

### Context References
Before working on a specific area, READ the relevant doc first:

| Area | Must-read | Why |
|------|-----------|-----|
| Pipeline scripts / crawling | `docs/1-news-backend.md` | Script flags, crawl logic, cost |
| Google News search / domain blocking | `docs/1.1-news-google-search.md` | Search flow, -site: logic, filtering layers |
| News threading | `docs/1.2-news-threading.md` | Algorithm, scoring constants |
| Reranker / causal threading | `docs/1.2.1-reranker-causal-test.md` | Cross-encoder experiment, causal labeling, go/no-go |
| Embedding models | `docs/1.3-embedding-ab-test.md` | Model comparison, 3-zone gate |
| Scoring thresholds / weight tuning | `docs/1.4-news-scoring-tuning.md` | All thresholds, scoring flow, tuning approach |
| News frontend / components | `docs/2-news-frontend.md` | Component props, data flow, known hacks |
| DB schema changes | `docs/schema.md` | Column types, relationships, lifecycle |
