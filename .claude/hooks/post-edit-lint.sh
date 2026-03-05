#!/bin/bash
# Post-edit hook: auto-format + lint changed source files
# Runs prettier (fix) then eslint (fix) on src/ files

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

# Skip if no file path
if [ -z "$FILE_PATH" ]; then
  exit 0
fi

# TypeScript/JavaScript source files → prettier + eslint --fix
case "$FILE_PATH" in
  src/*.ts|src/*.tsx|src/*.js|src/*.jsx)
    # Auto-format with prettier (silent on success)
    npx prettier --write "$FILE_PATH" 2>/dev/null

    # Auto-fix lint issues, report remaining errors
    npx eslint --fix --quiet "$FILE_PATH" 2>&1
    LINT_EXIT=$?

    if [ $LINT_EXIT -ne 0 ]; then
      echo "--- Lint errors in $FILE_PATH — fix above issues ---"
    fi
    ;;
  scripts/*.py)
    # Auto-fix Python with ruff
    ruff check --fix --quiet "$FILE_PATH" 2>/dev/null
    ruff format --quiet "$FILE_PATH" 2>/dev/null
    RUFF_EXIT=$(ruff check --quiet "$FILE_PATH" 2>&1)
    if [ -n "$RUFF_EXIT" ]; then
      echo "$RUFF_EXIT"
      echo "--- Ruff errors in $FILE_PATH — fix above issues ---"
    fi
    ;;
esac

exit 0
