#!/bin/bash
# Hook: PreToolUse (Bash) — Auto-review before git commit
# Detects git commit commands and injects review context into Claude

INPUT=$(cat)
CMD=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

# Only trigger on git commit commands
if echo "$CMD" | grep -qE '^git commit'; then
  CWD=$(echo "$INPUT" | jq -r '.cwd')
  STAGED=$(cd "$CWD" && git diff --staged --stat 2>/dev/null)

  if [ -n "$STAGED" ]; then
    # Escape for JSON
    STAGED_ESCAPED=$(echo "$STAGED" | jq -Rs .)

    cat <<JSONEOF
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "additionalContext": "PRE-COMMIT REVIEW: Before committing, verify these staged changes are clean:\n${STAGED_ESCAPED}\n\nCheck for: (1) secrets/API keys (2) console.log/debug code (3) TODO/FIXME left behind (4) type errors. If issues found, fix before committing."
  }
}
JSONEOF
  fi
fi

exit 0
