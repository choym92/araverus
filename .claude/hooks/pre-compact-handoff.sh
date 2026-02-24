#!/bin/bash
# Hook: PreCompact — Remind Claude to save handoff and flush pending docs
# Fires before auto-compaction when context window is filling up

INPUT=$(cat)
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // "unknown"')
CWD=$(echo "$INPUT" | jq -r '.cwd // "."')
TODAY=$(date +%Y-%m-%d)

PENDING=""
if [ -f "$CWD/docs/cc/_pending-docs.md" ]; then
  PENDING=" PENDING DOCS: docs/cc/_pending-docs.md exists — flush these updates to the relevant docs before compacting."
fi

cat <<JSONEOF
{
  "hookSpecificOutput": {
    "hookEventName": "PreCompact",
    "additionalContext": "CONTEXT COMPRESSION IMMINENT: Your context is about to be compressed. Before proceeding: (1) Flush any pending doc updates (check docs/cc/_pending-docs.md). (2) Save a handoff document to docs/cc/${TODAY}-handoff.md with: what was accomplished, key decisions, remaining work, important file paths.${PENDING}"
  }
}
JSONEOF

exit 0
