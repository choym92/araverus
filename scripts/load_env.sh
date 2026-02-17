#!/bin/bash
# Source this to load secrets from macOS Keychain into env vars.
# Usage: source scripts/load_env.sh

load_key() {
    local val
    val=$(security find-generic-password -a "$1" -s "araverus" -w 2>/dev/null) || {
        echo "WARN: Could not load $1 from Keychain" >&2
        return 1
    }
    export "$1=$val"
}

load_key "NEXT_PUBLIC_SUPABASE_URL"
load_key "SUPABASE_SERVICE_ROLE_KEY"
load_key "OPENAI_API_KEY"
load_key "GEMINI_API_KEY"
export GOOGLE_APPLICATION_CREDENTIALS="$HOME/credentials/araverus-tts-sa.json"
echo "Env loaded from Keychain"
