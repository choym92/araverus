<!-- Created: 2026-02-06 -->
# Claude Code Setup — Araverus

Complete reference for the `.claude/` configuration, skills, agents, and automation.

---

## Directory Structure

```
.claude/
├── settings.json              # Model, hooks, attribution (checked into git)
├── settings.local.json        # Permissions, MCP servers (gitignored)
├── hooks/                     # Automation shell scripts
│   ├── pre-commit-review.sh   # Injects review context before git commit
│   ├── pre-compact-handoff.sh # Reminds to save handoff before compression
│   └── session-end-log.sh     # Appends git log to docs/cc/ on session end
├── agents/                    # 6 custom subagents
│   ├── principal-code-architect.md   # Full-stack architecture review (sonnet)
│   ├── frontend-code-reviewer.md     # Staff+ React/Next.js review (sonnet)
│   ├── backend-code-reviewer.md      # Backend/API/DB review (sonnet)
│   ├── staged-diff-reviewer.md       # Quick staged diff review (haiku)
│   ├── prompt-refiner.md             # Prompt sanitization (haiku)
│   └── claude-cli-optimizer.md       # CLI config optimization (sonnet)
└── skills/                    # 10 slash command skills
    ├── generate-prd/          # /generate-prd [idea file]
    ├── generate-tasks/        # /generate-tasks [prd file]
    ├── process-tasks/         # /process-tasks [task file]
    ├── generate-status/       # /generate-status
    ├── plan-architecture/     # /plan-architecture [prd file]
    ├── handoff/               # /handoff [optional note]
    ├── plan/                  # /plan [description]
    ├── review/                # /review [staged|all|file]
    ├── research/              # /research [topic]
    └── pipeline-check/        # /pipeline-check
```

---

## Skills Reference

### Development Workflow (Idea → Production)

```
docs/workflow/1-ideas/        Write idea
        ↓
/generate-prd [idea file]     Codebase analysis → questions → PRD
        ↓
/plan-architecture [prd]      Technical decisions (DB, API, patterns)
        ↓
/generate-tasks [prd]         Dependency graph + parallel markers + file map
        ↓
/process-tasks [tasks]        Execute one sub-task at a time → approve → commit
        ↓
/handoff                      Save session context → docs/cc/
```

### All Skills

| Skill | Description | Model | Forked? | Read-only? |
|-------|-------------|-------|---------|------------|
| `/generate-prd` | Generate PRD from idea with codebase analysis | sonnet | no | no |
| `/plan-architecture` | Technical architecture decisions between PRD and tasks | sonnet | no | no |
| `/generate-tasks` | Task list with dependency graph and file impact map | sonnet | no | no |
| `/process-tasks` | Execute tasks one at a time with approval gates | sonnet | no | no |
| `/plan` | Implementation plan before writing code | sonnet | no | no |
| `/review` | Code review of staged/unstaged changes | sonnet | **yes** | effectively |
| `/research` | Web + codebase research without file modifications | sonnet | **yes** | **yes** |
| `/pipeline-check` | Finance pipeline health check | haiku | **yes** | effectively |
| `/handoff` | Context handoff document for session continuation | haiku | no | no |
| `/generate-status` | Daily status board from git commits | haiku | no | no |

**Forked** = runs in separate context (doesn't consume main conversation tokens)
**Read-only** = `allowed-tools` blocks file creation/editing

---

## Agents Reference

| Agent | Purpose | Model | Auto-triggered? |
|-------|---------|-------|-----------------|
| `principal-code-architect` | Full-stack architectural review | sonnet | no |
| `frontend-code-reviewer` | React/Next.js/TypeScript review | sonnet | no |
| `backend-code-reviewer` | API/DB/security review | sonnet | no |
| `staged-diff-reviewer` | Quick staged diff check | haiku | no |
| `prompt-refiner` | Prompt sanitization and routing | haiku | no |
| `claude-cli-optimizer` | CLI configuration optimization | sonnet | no |

---

## Automation (Hooks)

### Active Hooks

| Hook | Event | Script | What it does |
|------|-------|--------|-------------|
| Pre-commit review | `PreToolUse` (Bash) | `.claude/hooks/pre-commit-review.sh` | Detects `git commit` → injects staged diff review context into Claude |
| File modification reminder | `PostToolUse` (Write\|Edit) | inline | Reminds to run lint/build after file changes |
| Pre-compact handoff | `PreCompact` | `.claude/hooks/pre-compact-handoff.sh` | Reminds Claude to save handoff before context compression |
| Session end git log | `SessionEnd` | `.claude/hooks/session-end-log.sh` | Appends today's git commits to `docs/cc/YYYY-MM-DD.md` |
| Completion sound | `Stop` (global) | inline | Plays Glass.aiff when Claude finishes responding |

### How Each Automation Works

**Pre-commit review** (fully automatic):
```
User asks to commit → Claude runs git commit →
  Hook intercepts → reads git diff --staged →
  Injects file list + review checklist into Claude's context →
  Claude sees the review context and checks before committing
```

**Pre-compact handoff** (reminder-based):
```
Context window fills up → auto-compaction triggered →
  Hook fires → injects message: "save a handoff to docs/cc/" →
  Claude sees the reminder and creates handoff document →
  Compaction proceeds
```

**Session end git log** (basic, no LLM):
```
Claude session ends → hook runs shell script →
  Runs git log --since=midnight →
  Appends commits to docs/cc/YYYY-MM-DD.md →
  Note: This is a raw dump, NOT intelligent summarization.
  For intelligent summaries, use /generate-status manually.
```

### Limitations

- Skills (all 10) still require manual `/slash-command` invocation
- `SessionEnd` hook cannot use LLM — Claude is already gone at that point
- `PreCompact` hook can only remind, not guarantee Claude will act on it

---

## Settings

### settings.json (project, checked into git)
```json
{
  "$schema": "https://json.schemastore.org/claude-code-settings.json",
  "model": "claude-opus-4-6",
  "hooks": {
    "PreToolUse": [{ "matcher": "Bash", "hooks": [{ "type": "command", "command": ".claude/hooks/pre-commit-review.sh" }] }],
    "PostToolUse": [{ "matcher": "Write|Edit", "hooks": [{ "type": "command", "command": "echo 'File modified — remember to run lint/build'" }] }],
    "PreCompact": [{ "hooks": [{ "type": "command", "command": ".claude/hooks/pre-compact-handoff.sh" }] }],
    "SessionEnd": [{ "hooks": [{ "type": "command", "command": ".claude/hooks/session-end-log.sh" }] }]
  },
  "attribution": {
    "commit": "Co-Authored-By: Claude <noreply@anthropic.com>",
    "pr": "Generated with [Claude Code](https://claude.ai/claude-code)"
  }
}
```

### settings.local.json (local, gitignored)
- Permissions: npm, git, gh, mkdir/cp/rm/mv, WebSearch, MCP tools
- Deny: `.env` file reads
- MCP servers: serena, context7

### Global user settings (~/.claude/settings.json)
- `alwaysThinkingEnabled: true`
- Custom status line (project label, git branch, model)
- Stop hook: completion sound

---

## Workflow Directory Structure

```
docs/
├── workflow/
│   ├── 1-ideas/            # Raw idea files (input for /generate-prd)
│   ├── 2-prds/             # PRDs and architecture decisions
│   │   └── template.md     # PRD template
│   └── 3-tasks/            # Task lists
│       └── template.md     # Task template
├── cc/                     # Session logs (/handoff output, /generate-status)
├── architecture.md         # Project overview
├── architecture-finance-pipeline.md  # Finance pipeline deep dive
├── schema.md               # Database tables
├── project-history.md      # Project evolution timeline
├── claude-code-setup.md    # This file
├── 1-news-backend.md       # Pipeline scripts, crawling, briefing
├── 1.1-news-google-search.md  # Search flow, domain blocking
├── 1.2-news-threading.md   # Thread grouping algorithm
├── 1.3-embedding-ab-test.md   # Embedding model comparison
├── 2-news-frontend.md      # /news page components
├── 3-blog-writing-guide.md # MDX blog authoring
└── pipeline-audit/         # Per-script audit docs
```

---

## MCP Servers

| Server | Purpose | When to use |
|--------|---------|-------------|
| **Serena** | Semantic code analysis, symbol search, refactoring | Understanding codebase, finding references, editing symbols |
| **Context7** | Up-to-date library documentation | Working with libraries, checking latest APIs ("use context7") |
