# Rule: Generating Daily Status Board
<!-- Created: 2025-09-03 -->

## Goal

To create a brief, JIRA-style status board that provides a quick snapshot of project progress. The status board maintains a cumulative history with newest entries on top, enabling team collaboration and progress tracking without reading lengthy session logs.

## Process

1. **Read Existing Status Board:** Check if `docs/cc/status-board.md` exists to preserve history
2. **Gather Today's Data:**
   - Git commits from today (`git log --since="midnight"`)
   - Current session file (`docs/cc/YYYY-MM-DD.md`)
   - Task files to identify in-progress and upcoming work
   - Recent PRDs and ideas for context
3. **Generate Today's Status Section:**
   - **Done Today:** Completed items from git commits and session logs
   - **In Progress:** Current tasks being worked on
   - **Next Up:** Immediate upcoming tasks
4. **Update Status Board:**
   - Prepend new section with today's date
   - Keep all historical entries below
   - Use horizontal rule (`---`) to separate days

## Output Format

```markdown
# TWPWAS Status Board
<!-- Updated: YYYY-MM-DD -->

## YYYY-MM-DD
✅ **Done Today**
- Brief description [commit-hash if applicable]
- Another completed item
- Max 5 items, most important only

🔄 **In Progress**
- Current task (Task X.Y)
- Another active item
- Max 3 items

📋 **Next Up**
- Next priority task
- Another upcoming item
- Max 3 items

---

## Previous Date
[Previous status entries...]
```

## Guidelines

1. **Brevity is Key:**
   - Each bullet point should be one line
   - No explanations or details
   - Focus on WHAT was done, not HOW

2. **Data Sources Priority:**
   - Git commits = strongest signal for "Done"
   - Task files with `[x]` = completed
   - Task files with `[ ]` = in progress or upcoming
   - Session files = context and details

3. **Maintain History:**
   - NEVER delete old entries
   - Always prepend new content
   - Keep chronological order (newest first)

4. **Daily Execution:**
   - Run at end of each work day
   - Or when requested by user with "generate status"

## File Management

- **Location:** `docs/cc/status-board.md`
- **Update Method:** EDIT to prepend (never overwrite completely)
- **Date Format:** YYYY-MM-DD for consistency
- **Line Limit:** ~10 lines per day maximum

## Target Audience

Team members who need quick project status updates without reading detailed logs. Useful for:
- Daily standups
- Quick progress checks
- Understanding project velocity
- Historical progress tracking

## Example Command Usage

When user says "generate status" or "update status board":
1. AI reads current status board
2. Gathers today's progress data
3. Prepends today's status section
4. Saves updated file

This creates a concise, scannable document showing project evolution over time.