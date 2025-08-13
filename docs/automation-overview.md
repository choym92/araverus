# Claude Code Automation Map (araverus)

This document shows, at a glance, **what runs automatically and when** in the araverus repo.  
(Commands · Agents · MCP · Hooks included)

---

## 0) Big Picture (Flow)

Idea → (optional) /agent-architect → INITIAL.md → /generate-prp → /execute-prp
│ │
└─ Serena/Context7 ├─ Validate (lint/build/tests)
├─ Auto Review (/agent-reviewer "staged")
├─ PR Draft (/gen-pr)
└─ EoD Log (/eod)

---

## 1) PRP Pipeline Automation

| Stage | What I do | What happens (auto/semi-auto) | Files |
|---|---|---|---|
| A | (Optional) Architecture snapshot | `/agent-architect "<topic>"` outputs file plan, SSR/CSR boundary, risks (plan-only, no writes) | `.claude/commands/agent-architect.md`, `CLAUDE.md`, `docs/architecture.md` |
| B | Write a brief | Create `INITIAL.md` using a simple template | `PRPs/inbox/*.initial.md` |
| C | Generate plan | `/generate-prp <INITIAL>` researches codebase + external docs → **executable PRP** | `.claude/commands/generate-prp.md`, `PRPs/<feature>.md` |
| D | Execute | `/execute-prp <PRP>` → **Plan → Execute → Validate → Auto Review & PR → EoD** | `.claude/commands/execute-prp.md` |

> **Serena MCP** = symbol find/replace inside the codebase  
> **Context7 MCP** = cite/link official docs and examples  
> Both are leveraged during PRP generation/execution when needed.

---

## 2) Hooks — “Run things automatically at key moments”

### 2.1 Workflow event hooks (`.claude/settings.json`)
| Event | Trigger | Auto action | Purpose |
|---|---|---|---|
| **UserPromptSubmit** | Right after you submit a prompt | `prompt-refiner` agent | Tighten/clarify prompts |
| **AfterEdit** | Right after a file is edited | `npm run lint` (lightweight) | Catch small mistakes early |
| **AfterMultiEdit** | After large multi-file edits | `principal-code-architect` | Architecture/SSR-CSR review |
| **BeforeCommit** | **Just before commit** | `npm run build` → `backend-code-reviewer` (API/lib) → `frontend-code-reviewer` (app/components) → *(optional)* `staged-diff-reviewer` | Build gate + targeted reviews + final staged diff review |

> Use `trigger_on` patterns to auto-run the right reviewer based on changed paths.

### 2.2 Tool pre/post hooks (`.claude/settings.local.json`)
| Where | Trigger | Auto action | Purpose |
|---|---|---|---|
| **PreToolUse: Write/Edit** | Before any file write/edit | `scripts/cc_guard.py` | **Block sensitive paths** (`.env*`, `.git`, `supabase/*.key`, etc.) |
| **PreToolUse: Write/Edit** | Same | “PreChange …” message | Show change summary + rollback hint |
| **PreToolUse: Bash** | On Bash run | Append to `./.claude/logs/bash.log` | Execution auditing |
| **PostToolUse: Write/Edit** | After a write/edit | `npm run -s lint` (quiet) | Re-lint once more after changes |

---

## 3) Commands (buttons you press)

| Command | Role | When to use |
|---|---|---|
| **/agent-architect** | Plan-only design (file plan, SSR/CSR boundary, risks) | Before big/ambiguous work or to slim down a wide plan |
| **/generate-prp** | INITIAL → executable PRP | After you write a brief |
| **/execute-prp** | Implement PRP + Validate + **Auto Review/PR/EoD** | After plan is approved |
| **/agent-reviewer "staged"** | Stage-based line-range review (patch suggestions) | Right before commit or as part of Execute PRP ending |
| **/review-diff** | Summarize staged diff & propose small patches | When you want quick fix suggestions |
| **/gen-pr** | Create Conventional Commit PR title/body/test plan | Before opening a PR |
| **/eod** | Prepend 5-line daily summary into `docs/cc/YYYY-MM-DD.md` | End-of-day or after feature completion |

*(Optional)* **/auto-prp** can turn a short free-form request into `INITIAL.md` and run `/generate-prp` in one go.

---

## 4) Agents (role specialists)

| Agent | Role | Key checks (araverus) |
|---|---|---|
| **prompt-refiner** | Improve prompts | Clarify goals/constraints/missing info |
| **principal-code-architect** | Review wide changes | File plan, SSR/CSR boundaries, minimal edits |
| **backend-code-reviewer** | API/server security review | `requireAdmin/ensureAdminOrThrow`, use `BlogService` for writes, no secret/log leaks |
| **frontend-code-reviewer** | UI/a11y review | Server-first, client components only for interaction, ARIA/focus instead of `alert()` |
| **agent-reviewer** | Line-range reviewer (general) | Risk summary → `path:Lx-Ly` notes → minimal unified diffs |
| *(Optional)* **staged-diff-reviewer** | Final review of staged changes | Risk/line notes/patches → “LGTM/Block” verdict |

---

## 5) What’s “automatic” now? (TL;DR)

- **Right after a prompt** → Prompt Refinement runs automatically  
- **Right after file edits** → Lint runs automatically  
- **After large multi-file edits** → Architecture review runs automatically  
- **Just before commit** → Build → backend review → frontend review → *(optional)* staged-diff review run automatically  
- **At the end of Execute PRP** → you’re guided to **/agent-reviewer → /gen-pr → /eod** in sequence (semi-automatic with checkpoints)  
- **Always** → Sensitive writes are blocked; Bash runs are logged

---

## 6) 2-minute self-check

- [ ] Edit one line in `src/lib/...` → **AfterEdit lint** fires  
- [ ] Try to Write `.env.local` via Claude Code → **blocked**  
- [ ] Before commit → **build → backend review → frontend review → (opt) staged-diff review** fire in order  
- [ ] End of `/execute-prp …` → guidance for **/agent-reviewer → /gen-pr → /eod** appears  
- [ ] `docs/cc/YYYY-MM-DD.md` gets **EoD** prepended

---

## 7) FAQ

- **Does PRP automatically run code review?**  
  → At the end of Execute PRP, you’re **prompted** to run `/agent-reviewer "staged"` (semi-automatic). You also have auto reviews **before commit** via hooks.

- **How are MCPs used?**  
  → `/generate-prp` and `/execute-prp` use **Serena** for symbol search/replace and **Context7** for citing official docs when needed.

- **It feels slow—what can I tune?**  
  → Keep `BeforeCommit` as-is (final safety). Optimize `AfterEdit` using ESLint cache or narrower `trigger_on` patterns.

---

## 8) Tuning / disabling

- Temporarily disable a hook: comment/remove that block in `.claude/settings.json`  
- Add more protected paths: update regexes in `scripts/cc_guard.py`  
- Narrow review scope: refine `trigger_on` patterns

---

## 9) Blog Workflow (MDX-based)

- **Source**: `content/blog/<slug>/index.mdx` (Git + Obsidian authoring)
- **Assets**: `public/blog/<slug>/` (images, covers)
- **Deploy**: Push to Git → Next.js SSG → Vercel auto-deploy

---