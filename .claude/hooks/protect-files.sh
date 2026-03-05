#!/bin/bash
# PreToolUse hook: Block edits to protected files
# exit 0 = allow, exit 2 = block

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

# Skip if no file path (e.g. Bash commands)
if [ -z "$FILE_PATH" ]; then
  exit 0
fi

# Protected patterns — never edit these automatically
PROTECTED=(
  ".env"
  ".env.local"
  ".env.production"
  "package-lock.json"
  "pnpm-lock.yaml"
  "yarn.lock"
  ".git/"
)

for pattern in "${PROTECTED[@]}"; do
  case "$FILE_PATH" in
    *"$pattern"*)
      echo "BLOCKED: Cannot edit protected file '$FILE_PATH' (matches '$pattern')" >&2
      exit 2
      ;;
  esac
done

exit 0
