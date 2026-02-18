<!-- Created: 2026-02-16 -->
# /worktree — Parallel Development with Git Worktrees

## Description
Manage git worktrees for running multiple Claude Code instances on the same project simultaneously.

## Usage
```
/worktree create [branch-name]   # Create new worktree + branch
/worktree list                   # Show active worktrees
/worktree remove [branch-name]   # Clean up worktree
```

## Instructions

You manage git worktrees for parallel development. Worktrees allow multiple Claude instances to work on different branches simultaneously without file conflicts.

### Worktree Location
All worktrees go in: `../.worktrees/araverus-{branch}/`

### Commands

#### `create [branch-name]`
```bash
# Create worktree with new branch
git worktree add ../.worktrees/araverus-{branch} -b {branch}
```
- Confirm the branch name doesn't already exist
- After creation, print the full path for the user to open in another terminal
- Remind: `cd ../.worktrees/araverus-{branch} && npm install`

#### `list`
```bash
git worktree list
```
- Show all active worktrees in a clean table format
- Indicate which is the main worktree

#### `remove [branch-name]`
```bash
git worktree remove ../.worktrees/araverus-{branch}
```
- Confirm with user before removing (check for uncommitted changes first)
- Optionally delete the branch too: `git branch -d {branch}`

### Rules
- Always use the `../.worktrees/araverus-{branch}/` path convention
- Never create worktrees inside the main project directory
- Warn if there are uncommitted changes before removing a worktree
- After creating, remind user to run `npm install` in the new worktree
