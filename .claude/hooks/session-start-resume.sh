#!/bin/bash
# Hook: SessionStart — Auto-load latest handoff document
# Finds the most recent docs/cc/*.md file and injects it into Claude's context

INPUT=$(cat)
CWD=$(echo "$INPUT" | jq -r '.cwd // "."')
CC_DIR="$CWD/docs/cc"

# Check if docs/cc/ exists
if [ ! -d "$CC_DIR" ]; then
  exit 0
fi

# Find the most recent .md file (by filename, YYYY-MM-DD sorts naturally)
LATEST=$(ls "$CC_DIR"/*.md 2>/dev/null | sort -r | head -1)

if [ -z "$LATEST" ] || [ ! -f "$LATEST" ]; then
  exit 0
fi

FILENAME=$(basename "$LATEST")
CONTENT=$(cat "$LATEST" | head -100 | jq -Rs .)

cat <<JSONEOF
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": "PREVIOUS SESSION HANDOFF (${FILENAME}): Read docs/cc/${FILENAME} to continue where we left off. Here is a preview:\n${CONTENT}"
  }
}
JSONEOF

exit 0
