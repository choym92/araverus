#!/bin/bash
set -euo pipefail

# ── Config ──────────────────────────────────────────────
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV="$PROJECT_DIR/.venv/bin/python"
SCRIPTS="$PROJECT_DIR/scripts"
DATE=$(date +%Y-%m-%d)
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/pipeline-$DATE.log"
BRIEFING_DIR="$HOME/Documents/Briefings"

mkdir -p "$LOG_DIR" "$SCRIPTS/output" "$BRIEFING_DIR"

# Redirect all output to log (and stdout for launchd)
exec > >(tee -a "$LOG_FILE") 2>&1

echo "============================================"
echo "Finance Pipeline — $DATE"
echo "Started: $(date)"
echo "============================================"

cd "$PROJECT_DIR"

# ── Load secrets from macOS Keychain ──────────────────
# Each key stored under service "araverus" in login keychain.
# This avoids storing secrets in a .env file on disk.
load_key() {
    local key_name="$1"
    local val
    val=$(security find-generic-password -a "$key_name" -s "araverus" -w 2>/dev/null) || {
        echo "WARN: Could not load $key_name from Keychain"
        return 1
    }
    export "$key_name=$val"
}

load_key "NEXT_PUBLIC_SUPABASE_URL"
load_key "SUPABASE_SERVICE_ROLE_KEY"
load_key "OPENAI_API_KEY"
load_key "GEMINI_API_KEY"
export GOOGLE_APPLICATION_CREDENTIALS="$HOME/credentials/araverus-tts-sa.json"

echo "Secrets loaded from Keychain"

# ── Phase 1: Ingest + Search ───────────────────────────
echo ""
echo ">>> Phase 1: Ingest + Search"
$VENV "$SCRIPTS/wsj_ingest.py" || { echo "FATAL: Ingest failed"; exit 1; }
$VENV "$SCRIPTS/wsj_ingest.py" --export || { echo "FATAL: Export failed"; exit 1; }
$VENV "$SCRIPTS/wsj_to_google_news.py" --delay-item 0.5 --delay-query 0.3 || echo "WARN: Google News search had errors (continuing)"

# ── Phase 2: Rank + Resolve ────────────────────────────
echo ""
echo ">>> Phase 2: Rank + Resolve"
$VENV "$SCRIPTS/embedding_rank.py" || { echo "ERROR: Embedding rank failed"; exit 1; }
$VENV "$SCRIPTS/resolve_ranked.py" --delay 0.5 --update-db || { echo "ERROR: Resolve failed"; exit 1; }
$VENV "$SCRIPTS/wsj_ingest.py" --mark-searched "$SCRIPTS/output/wsj_items.jsonl" || echo "WARN: mark-searched failed"

# ── Phase 3: Crawl ─────────────────────────────────────
echo ""
echo ">>> Phase 3: Crawl"
$VENV "$SCRIPTS/crawl_ranked.py" --delay 2 --update-db || echo "WARN: Crawl had errors (continuing)"

# ── Phase 4: Post-process ──────────────────────────────
echo ""
echo ">>> Phase 4: Post-process"
$VENV "$SCRIPTS/wsj_ingest.py" --mark-processed-from-db || echo "WARN: mark-processed failed"
$VENV "$SCRIPTS/wsj_ingest.py" --update-domain-status || echo "WARN: domain-status failed"

# ── Phase 5: Briefing ──────────────────────────────────
echo ""
echo ">>> Phase 5: Briefing"
$VENV "$SCRIPTS/generate_briefing.py" --output-dir "$BRIEFING_DIR" || echo "ERROR: Briefing generation failed"

# ── Done ────────────────────────────────────────────────
echo ""
echo "============================================"
echo "Pipeline complete — $(date)"
echo "============================================"
