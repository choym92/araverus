#!/bin/bash
# Hook: PreCompact — Remind Claude to save handoff before context compression
# Fires before auto-compaction when context window is filling up

INPUT=$(cat)
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // "unknown"')
CWD=$(echo "$INPUT" | jq -r '.cwd // "."')
TODAY=$(date +%Y-%m-%d)

cat <<JSONEOF
{
  "hookSpecificOutput": {
    "hookEventName": "PreCompact",
    "additionalContext": "CONTEXT COMPRESSION IMMINENT: Your context is about to be compressed. Before proceeding, save a handoff document to docs/cc/${TODAY}.md with: (1) what was accomplished (2) key decisions made (3) remaining work (4) important file paths. This ensures continuity after compression."
  }
}
JSONEOF

exit 0
