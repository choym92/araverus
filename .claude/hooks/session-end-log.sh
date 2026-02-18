#!/bin/bash
# Hook: SessionEnd — Save basic git activity log (no LLM available at this point)
# This is a simple dump — for intelligent summaries, use /generate-status manually

INPUT=$(cat)
CWD=$(echo "$INPUT" | jq -r '.cwd // "."')
TODAY=$(date +%Y-%m-%d)
LOG_FILE="$CWD/docs/cc/${TODAY}.md"

# Only run if docs/cc/ exists
if [ -d "$CWD/docs/cc" ]; then
  # Get today's git commits
  COMMITS=$(cd "$CWD" && git log --since="midnight" --oneline 2>/dev/null)

  if [ -n "$COMMITS" ]; then
    # Append to today's log (don't overwrite)
    if [ ! -f "$LOG_FILE" ]; then
      echo "<!-- Created: ${TODAY} -->" > "$LOG_FILE"
      echo "# Session Log — ${TODAY}" >> "$LOG_FILE"
      echo "" >> "$LOG_FILE"
    fi

    # Skip if these commits are already logged (prevents duplicates from multiple instances)
    FIRST_HASH=$(echo "$COMMITS" | head -1 | cut -d' ' -f1)
    if grep -q "$FIRST_HASH" "$LOG_FILE" 2>/dev/null; then
      exit 0
    fi

    echo "" >> "$LOG_FILE"
    echo "---" >> "$LOG_FILE"
    echo "## Git Activity (auto-logged)" >> "$LOG_FILE"
    echo '```' >> "$LOG_FILE"
    echo "$COMMITS" >> "$LOG_FILE"
    echo '```' >> "$LOG_FILE"
  fi
fi

exit 0
