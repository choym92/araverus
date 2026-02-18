#!/bin/bash
# Post-edit hook: auto-lint changed source files
# Only runs on src/ files (skips md, json, etc.)

FILE_PATH="$CLAUDE_FILE_PATH"

# Skip if no file path or not a src/ file
if [ -z "$FILE_PATH" ]; then
  exit 0
fi

# Only lint TypeScript/JavaScript source files
case "$FILE_PATH" in
  src/*.ts|src/*.tsx|src/*.js|src/*.jsx)
    ;;
  *)
    exit 0
    ;;
esac

# Run ESLint on the changed file (quiet mode, fast)
npx eslint --quiet "$FILE_PATH" 2>&1
LINT_EXIT=$?

if [ $LINT_EXIT -ne 0 ]; then
  echo "--- Lint errors found in $FILE_PATH — please fix above issues ---"
fi

exit 0
