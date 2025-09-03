# CLAUDE.md
<!-- Updated: 2025-09-03 -->
This file provides guidance to Claude Code (claude.ai/code) when working in this repository.
**Invariant global rules only.** Detailed architecture/schema/notes live in `README.md` or `docs/`.

---

## 🚨 GLOBAL RULES — ALWAYS FOLLOW THESE (Invariant)

### Critical Behaviors
1) **BEFORE change**: Read neighboring files; follow existing patterns and coding style.
2) **AFTER change**: Run `npm run lint` and `npm run build` (type check).  
3) **VERIFY deps**: Never assume a library exists; check `package.json`.  
4) **EDIT over CREATE**: Prefer modifying existing files/components over creating new ones.  
5) **SESSION FILE MANAGEMENT**: Always update existing daily session files (`docs/cc/YYYY-MM-DD.md`) rather than creating new timestamped versions. Append new sessions to existing daily files with clear section breaks.
6) **DATE STAMP**: When creating or modifying .md files, always add/update commented date at top (<!-- Created: 2025-09-03 --> or <!-- Updated: 2025-09-03 -->).
7) **Server-first**: Next.js App Router uses **Server Components by default**; use Client **only** for interaction/state/DOM APIs.

### 🌐 LANGUAGE RULES
**CRITICAL**: Always respond in English, even when prompted in other languages. All code, comments, documentation, and responses must be in English only.

### Power Keywords & Enhanced Behaviors
- **IMPORTANT**: Must not be overlooked.  
- **PROACTIVELY**: Propose safe improvements within these rules.  
- **VERIFY**: Validate changes with checks/tests and a short runbook note.  
- **SECURITY-FIRST**: Treat inputs, secrets, and errors defensively.  
- **Be concise**: Output is short, actionable, copy-pastable.

### Anti-Patterns to Avoid
- ❌ **Over-engineering** (unneeded abstractions/deps/complexity).  
- ❌ **Breaking public contracts**: Keep public API/URL/DB schema compatible. (Internal/private pieces may be changed.)  
- ❌ Creating new files when a focused edit suffices.  
- ❌ Long prose; prefer steps, diffs, and exact commands.

### Automation Checklist (Every task)
- [ ] `npm run lint` (fix issues)  
- [ ] `npm run build` (fix type errors)  
- [ ] Manual verify in browser; check console for errors  
- [ ] Ensure **no secrets** in code/logs/diffs  
- [ ] Add/update a minimal test (happy + one edge) if logic changed  
- [ ] Append change summary to `docs/cc/YYYY-MM-DD.md` (what/why/how)

---

## 🔄 Feature Development Workflow

### Generate PRD from Idea
When user says **"generate PRD from docs/workflow/1_ideas/[filename].md"**:

Include the template from `docs/workflow/2_prds/template.md` and follow its process:
1. Read the idea file at the specified path
2. Ask clarifying questions with numbered/lettered options for easy response
3. Generate PRD using the template structure
4. Save as `docs/workflow/2_prds/prd-[feature-name].md`
5. DO NOT start implementing - ask clarifying questions first

### Generate Tasks from PRD  
When user says **"generate tasks from docs/workflow/2_prds/[filename].md"**:

Include the template from `docs/workflow/3_tasks/template.md` and follow its process:
1. Read the PRD file and analyze requirements
2. Assess current codebase state
3. Generate parent tasks first and show to user
4. Wait for user to respond with "Go"
5. Generate detailed sub-tasks with relevant files
6. Save as `docs/workflow/3_tasks/tasks-[feature-name].md`

### Process Task List
When user says **"process docs/workflow/3_tasks/[filename].md"**:
1. Read task list and work through ONE sub-task at a time
2. Mark completed tasks with [x] immediately after finishing
3. Stop and ask "Continue?" after each sub-task
4. When all sub-tasks done: run validation, stage changes, commit with descriptive message
5. Mark parent task [x] and update progress in docs/cc/

---

## 🤝 TEAM COLLABORATION & SESSION MANAGEMENT

### Daily Progress Tracking
- Document progress in `docs/cc/YYYY-MM-DD.md`
- Share blockers and next steps immediately
- Record key decisions and why they were made

### Git Workflow
- Feature branches → main
- Clear, descriptive commit messages
- Pull before starting work
- No force pushes to main

### Custom Commands

#### Session Start Workflow
When Claude is first launched (terminal or --continue):

1. **Auto git pull:**
   - `git pull` to sync latest changes
   - If conflicts, notify user and pause
   - Show brief summary of new commits if any

2. **Read today's context:**
   - Check if `docs/cc/YYYY-MM-DD.md` exists for today
   - If not, read yesterday's log for context
   - Briefly summarize where we left off

3. **Ready to work:**
   - "Ready to continue [project name]. Last worked on: [brief context]"
   - Ask what to tackle first if unclear

#### End of Day Workflow
When user says **"I'm done for today"** or **"end of day"**:

1. **Create/update progress log:**
   - Create `docs/cc/YYYY-MM-DD.md` with today's date
   - Document what was accomplished today
   - Note any blockers or next steps
   - Add questions for tomorrow

2. **Commit changes:**
   - `git add .`
   - Create descriptive commit message with progress summary
   - Include Claude Code footer
   - Execute commit

3. **Provide next day preview:**
   - Suggest what to tackle first tomorrow
   - Note any research needed
   - Celebrate today's wins

---

## 🏗️ PROJECT-SPECIFIC RULES (Stable Defaults)

### Conventions
1) **Auth**: Protected routes/pages must pass `useAuth` **or** server-side session/role check.  
2) **Data**: Use the service layer (e.g., `BlogService`) for DB logic; call explicitly from server actions/APIs when needed.  
3) **Admin**: **No hardcoded emails**. Use `user_profiles.role = 'admin'` (RLS/policies enforced) for authorization.  
4) **Styling**: Tailwind only; avoid inline styles (except utility overrides when justified).  
5) **Components**: **Server by default**; add `'use client'` only when truly required.

### Security · A11y · Testing (Minimum)
- **Secrets**: Live only in `.env*`; never commit. Mask in logs/errors.  
- **A11y**: ARIA, focus management, color contrast; never `alert()` as UX—use accessible error UI.  
- **Tests**: For new/changed logic, provide at least **1 happy + 1 edge** unit test. E2E optional.

### Token/Context Strategy & Tools
- **Large files**: Read/edit by **line range** or summaries—avoid full-file context.  
- **MCP Usage**: See detailed MCP guidelines below
- **Hooks**: Before any destructive action, print a 3-line note: **What / Impact / Rollback**. Keep Bash/Write/Edit logging on.

### 🔧 MCP Usage Guidelines

#### Installed MCPs
- **Serena** - Semantic code analysis and intelligent refactoring
- **Context7** - Up-to-date documentation retrieval

#### When to Use Serena
🚀 Serena is a powerful coding agent toolkit capable of turning an LLM into a fully-featured agent that works directly on your codebase. Unlike most other tools, it is not tied to an LLM, framework or an interface, making it easy to use it in a variety of ways.

🔧 Serena provides essential semantic code retrieval and editing tools that are akin to an IDE's capabilities, extracting code entities at the symbol level and exploiting relational structure. When combined with an existing coding agent, these tools greatly enhance (token) efficiency.

**Use Serena for:**
- Finding symbols, references, and dependencies across entire codebase
- Understanding code structure in complex projects (15+ languages supported)
- Precise code navigation and editing like an experienced developer using IDE
- Refactoring patterns across multiple files while maintaining relationships

#### When to Use Context7
Context7 MCP pulls up-to-date, version-specific documentation and code examples straight from the source — and places them directly into your prompt.

**Example Prompts:**
- "Create a Next.js middleware that checks for a valid JWT in cookies and redirects unauthenticated users to `/login`. use context7"
- "Configure a Cloudflare Worker script to cache JSON API responses for five minutes. use context7"

**Use Context7 for:**
- Getting latest API documentation for any library or framework
- Avoiding outdated code examples and hallucinated APIs
- Ensuring version-specific accurate implementations
- Add "use context7" to prompts when working with evolving technologies

#### MCP Best Practices
- Use Serena for codebase understanding before making changes and reading files
- Use Context7 when working with libraries you're unfamiliar with
- Document MCP-assisted insights in commit messages
- Share useful MCP patterns with team in docs/cc/

### Output Contract
- Keep responses **short and step-based**.  
- Include filenames + minimal diffs or exact commands.  
- State how to run/verify locally (1–2 lines).  
- Document changes in `docs/cc/YYYY-MM-DD.md`.

---

## Project Overview (Pointer)
- Architecture, schema, dependencies, editor/animation details → **move to** `README.md` / `docs/` and keep this file invariant.