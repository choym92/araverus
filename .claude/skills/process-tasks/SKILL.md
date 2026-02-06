---
name: process-tasks
description: Work through a task list one sub-task at a time
user-invocable: true
argument-hint: docs/workflow/3-tasks/[filename].md
---

# Process Task List

Read the task list file at `$ARGUMENTS` and work through it.

## Rules

1. **One sub-task at a time:** Do NOT start the next sub-task until the user says "yes" or "y".
2. **Completion protocol:**
   - When you finish a sub-task, immediately mark it `[x]`.
   - If ALL subtasks under a parent are `[x]`:
     1. Run the test suite (`npm test` or similar)
     2. Only if tests pass: stage changes (`git add` specific files)
     3. Clean up any temporary files/code
     4. Commit with conventional format:
        ```
        git commit -m "feat: summary of parent task" -m "- Detail 1" -m "- Detail 2"
        ```
     5. Mark the parent task `[x]`.
3. **Stop and wait** after each sub-task for user approval.

## Task List Maintenance

- Mark tasks `[x]` as they're completed.
- Add new tasks as they emerge.
- Keep the "Relevant Files" section up to date.
