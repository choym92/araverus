<!-- Updated: 2026-02-18 -->
# PRD: Full Finance Pipeline on Mac Mini (launchd)

## Overview

Migrate the **entire** finance pipeline — from RSS ingest through briefing generation — off GitHub Actions and onto the Mac Mini, orchestrated by **launchd**. One machine, one scheduler, one `.env`, no split-brain.

## Why Move Everything to Mac Mini

| Concern | GitHub Actions | Mac Mini |
|---|---|---|
| **Credentials** | Secrets per workflow, base64 hacks for JSON keys | Single `.env` + JSON key on disk |
| **Artifact passing** | Upload/download between jobs, 7-day retention | Local filesystem, persistent |
| **Debugging** | Re-run entire workflow, read logs in browser | SSH in, `tail -f`, re-run one script |
| **Cost** | ~2,000 min/month free tier, crawl job eats ~90 min | Already running, $0 marginal |
| **Security** | Secrets in GitHub, visible to repo admins | Keys on local disk, no exposure |
| **Playwright** | Install chromium every run (~2 min) | Installed once, cached |
| **HuggingFace models** | Cache action, still slow first run | Downloaded once, persistent (bge-base-en-v1.5 for threading) |
| **State** | Ephemeral runners, no memory between runs | Persistent disk, logs, outputs |
| **Future AI agents** | N/A | Docker isolation for untrusted agents (see Security) |

---

## Architecture

```
Mac Mini (launchd)
│
├── 6:00 AM ET ─── run_pipeline.sh ───────────────────────────────┐
│                  │                                               │
│                  ├── Phase 1: Ingest + Search        (~5 min)    │
│                  │   ├── wsj_ingest.py                           │
│                  │   ├── wsj_ingest.py --export                  │
│                  │   └── wsj_to_google_news.py                   │
│                  │                                               │
│                  ├── Phase 2: Rank + Resolve          (~3 min)   │
│                  │   ├── embedding_rank.py                       │
│                  │   ├── resolve_ranked.py --update-db            │
│                  │   └── wsj_ingest.py --mark-searched            │
│                  │                                               │
│                  ├── Phase 3: Crawl                  (~30 min)   │
│                  │   └── crawl_ranked.py --update-db              │
│                  │                                               │
│                  ├── Phase 4: Post-process            (~1 min)   │
│                  │   ├── wsj_ingest.py --mark-processed-from-db   │
│                  │   └── wsj_ingest.py --update-domain-status     │
│                  │                                               │
│                  ├── Phase 4.5: Embed + Thread        (~2 min)   │
│                  │   └── embed_and_thread.py                      │
│                  │       ├── Embed articles (BAAI/bge-base-en-v1.5)│
│                  │       ├── Match to existing threads (centroid) │
│                  │       ├── LLM group unmatched (Gemini Flash)   │
│                  │       └── Create/merge/deactivate threads      │
│                  │                                               │
│                  ├── Phase 5: Briefing               (~5 min)    │
│                  │   └── generate_briefing.py                    │
│                  │       ├── LLM curation + briefing gen (EN/KO) │
│                  │       ├── [CHAPTER:] marker extraction → JSON │
│                  │       ├── TTS audio (Chirp HD + Gemini TTS)   │
│                  │       ├── Whisper sentence alignment → JSON    │
│                  │       ├── Save text + chapters + sentences → DB│
│                  │       └── Upload latest audio → Supabase Storage│
│                  │                                               │
│                  └── Log summary + exit code                     │
│                                                                  │
├── logs/pipeline-YYYY-MM-DD.log                                   │
├── scripts/output/          (JSONL intermediates)                 │
└── scripts/output/briefings/ (text + audio)                       │
```

**Total runtime**: ~50 min end-to-end (crawl is the bottleneck).

---

## Wrapper Script: `scripts/run_pipeline.sh`

Single entrypoint that launchd calls. Runs all 5 phases sequentially. Any phase failure logs the error and continues to the next phase (except Phase 1 failure = abort, nothing to process).

```bash
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

# ── Phase 4.5: Embed + Thread ────────────────────────
echo ""
echo ">>> Phase 4.5: Embed + Thread"
$VENV "$SCRIPTS/embed_and_thread.py" || echo "WARN: Embed/thread had errors (continuing)"

# ── Phase 5: Briefing ──────────────────────────────────
echo ""
echo ">>> Phase 5: Briefing"
$VENV "$SCRIPTS/generate_briefing.py" --output-dir "$BRIEFING_DIR" || echo "ERROR: Briefing generation failed"

# ── Done ────────────────────────────────────────────────
echo ""
echo "============================================"
echo "Pipeline complete — $(date)"
echo "============================================"
```

**Key design decisions**:
- `set -euo pipefail` for strict error handling
- Secrets loaded from macOS Keychain (no `.env` file on disk) via `security find-generic-password`
- Phase 1 failure = hard abort (no articles = nothing to do)
- Phase 3 (crawl), Phase 4.5 (threading), and Phase 5 (briefing) failures = log warning but don't kill the pipeline
- `tee -a` writes to both log file and stdout (launchd captures stdout)
- Date-stamped log files — one per day, easy to grep
- Briefing output dir is `~/Documents/Briefings` (outside repo, persistent archive)

---

## Prerequisites

### 1. System Dependencies

```bash
# Check / install
brew install python@3.11 ffmpeg

# Playwright (for crawling)
pip install playwright
playwright install chromium

# Verify
python3 --version   # 3.11+
ffmpeg -version      # any recent version
```

### 2. Repository + Python Environment

```bash
cd ~/Project
git clone git@github.com:choym92/araverus.git
cd araverus
git checkout feature/news-frontend  # or main after merge

python3 -m venv .venv
source .venv/bin/activate
pip install -r scripts/requirements.txt
playwright install chromium
```

### 3. Environment Variables (macOS Keychain)

Secrets are stored in the macOS login Keychain under service name `araverus`. No `.env` file on disk for production pipeline.

```bash
# Store each key in Keychain (run once per Mac)
security add-generic-password -a "NEXT_PUBLIC_SUPABASE_URL" -s "araverus" -w "https://xxxx.supabase.co"
security add-generic-password -a "SUPABASE_SERVICE_ROLE_KEY" -s "araverus" -w "eyJhbGci..."
security add-generic-password -a "GEMINI_API_KEY" -s "araverus" -w "AIza..."
```

Google Cloud service account JSON is stored on disk (outside repo):
```bash
# Place at:
~/credentials/araverus-tts-sa.json
```

**Where to get each**:

| Key | Source |
|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase Dashboard → Settings → API → Project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase Dashboard → Settings → API → service_role (secret) |
| `GEMINI_API_KEY` | aistudio.google.com → API Keys |
| `GOOGLE_APPLICATION_CREDENTIALS` | Google Cloud Console → IAM → Service Accounts → Create Key (JSON). Enable `Cloud Text-to-Speech API` on the project. |

**For local development** (not Mac Mini): use `scripts/load_env.sh` which reads the same Keychain keys, or create `.env.local` at the project root.

### 4. Verify Each Phase Manually

```bash
source .venv/bin/activate

# Phase 1
python scripts/wsj_ingest.py
python scripts/wsj_ingest.py --export

# Phase 2 (needs Phase 1 output)
python scripts/embedding_rank.py

# Phase 5 only (skip others — uses existing DB data)
python scripts/generate_briefing.py --dry-run
python scripts/generate_briefing.py --skip-tts --skip-db
python scripts/generate_briefing.py
```

---

## launchd Setup

### Plist File

Create `~/Library/LaunchAgents/com.araverus.pipeline.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.araverus.pipeline</string>

    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>/Users/USER/Project/araverus/scripts/run_pipeline.sh</string>
    </array>

    <key>WorkingDirectory</key>
    <string>/Users/USER/Project/araverus</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>

    <!-- 6 AM ET = 11:00 UTC (EST, Nov-Mar) or 10:00 UTC (EDT, Mar-Nov) -->
    <!-- Start with EST; see DST Handling section below -->
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>11</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>

    <key>StandardOutPath</key>
    <string>/Users/USER/Project/araverus/logs/launchd-stdout.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/USER/Project/araverus/logs/launchd-stderr.log</string>

    <!-- Mac Mini is always-on; no sleep/wake handling needed -->
</dict>
</plist>
```

### launchd Commands

```bash
# Make the wrapper script executable
chmod +x ~/Project/araverus/scripts/run_pipeline.sh

# Create logs directory
mkdir -p ~/Project/araverus/logs

# Load
launchctl load ~/Library/LaunchAgents/com.araverus.pipeline.plist

# Verify
launchctl list | grep araverus

# Manual trigger (test)
launchctl start com.araverus.pipeline

# Watch logs
tail -f ~/Project/araverus/logs/pipeline-$(date +%Y-%m-%d).log

# Unload (to edit plist)
launchctl unload ~/Library/LaunchAgents/com.araverus.pipeline.plist
```

### DST Handling

launchd uses **system local time** (not UTC) if the Mac's timezone is set to US Eastern. Verify:

```bash
sudo systemsetup -gettimezone
# Should show: America/New_York
```

If the Mac Mini is set to `America/New_York`, just use `Hour=6, Minute=0` and launchd handles DST automatically:

```xml
<key>StartCalendarInterval</key>
<dict>
    <key>Hour</key>
    <integer>6</integer>
    <key>Minute</key>
    <integer>0</integer>
</dict>
```

If the Mac is set to a different timezone, use the UTC offsets from the plist above and swap manually in March/November.

---

## Audio Storage Strategy

Audio files are large (~3-5MB each) and the frontend needs to stream them. Strategy: **Supabase Storage for latest only, Mac Mini for full history.**

```
generate_briefing.py (Phase 5):
  TTS 생성
    → audio-en-YYYY-MM-DD.mp3  로컬 저장 (히스토리, Mac Mini)
    → audio-ko-YYYY-MM-DD.mp3  로컬 저장
    → briefing-en-latest.mp3   Supabase Storage 업로드 (덮어쓰기)
    → briefing-ko-latest.mp3   Supabase Storage 업로드 (덮어쓰기)
    → wsj_briefings.audio_url = Supabase Storage public URL
```

### Why this approach

| Concern | Solution |
|---|---|
| Frontend needs audio | Supabase Storage public URL → CDN-backed, fast globally |
| Storage cost | Only 2 files on Supabase at any time (~10MB total). Well within free tier |
| History | Full archive on Mac Mini local disk. Free, unlimited |
| Reliability | If Supabase Storage is down, audio unavailable but text still works |

### Supabase Storage setup

```sql
-- Create storage bucket (run once in Supabase SQL editor)
INSERT INTO storage.buckets (id, name, public) VALUES ('briefings', 'briefings', true);
```

Script uploads with fixed filenames — each day's upload overwrites the previous:
- `briefings/briefing-en-latest.mp3`
- `briefings/briefing-ko-latest.mp3`

Frontend reads `audio_url` from `wsj_briefings` table. URL is stable (same filename every day).

---

## Data Storage Summary

| Data | Where | Why |
|---|---|---|
| Briefing text (`briefing_text`) | Supabase `wsj_briefings` | Frontend queries it |
| Chapters JSON (`chapters`) | Supabase `wsj_briefings` | Frontend renders chapter navigation |
| Sentences JSON (`sentences`) | Supabase `wsj_briefings` | Frontend renders synced transcript with highlighting |
| Audio URL (`audio_url`) | Supabase `wsj_briefings` | Frontend reads URL |
| Audio file (MP3) | Supabase Storage (latest) + Mac Mini (history) | CDN for speed, local for archive |
| Pipeline metadata (junction, briefed flags) | Supabase | Pipeline logic depends on it |
| Category | `'EN'` or `'KO'` per row (NOT `'ALL'`) | One briefing per language per day |

---

## DB Schema Changes

### `wsj_briefings` — add `chapters` column

```sql
ALTER TABLE wsj_briefings ADD COLUMN chapters jsonb;
ALTER TABLE wsj_briefings ADD COLUMN sentences jsonb;
```

### Category convention

Each briefing is stored with `category = 'EN'` or `category = 'KO'`. The unique constraint is `(date, category)`, so one EN and one KO briefing per day.

Frontend queries both:
```sql
SELECT * FROM wsj_briefings WHERE date = '2026-02-17' AND category IN ('EN', 'KO');
```

---

## generate_briefing.py Changes (Phase 5)

### Chapter marker system

1. **Prompt**: Instruct LLM to insert `[CHAPTER: title]` markers at topic transitions
2. **Extract**: Regex parses markers → `chapters` JSON array with title + character position
3. **Clean**: Remove markers from text before sending to TTS (prevents TTS reading "CHAPTER")
4. **Save**: `chapters` JSON to `wsj_briefings.chapters` column

### Whisper sentence alignment

After TTS, before DB save:
1. Run Whisper (`base` model) on the generated MP3
2. Merge segments into full sentences (split on `.!?` and CJK equivalents)
3. Store as `sentences` JSONB in `wsj_briefings` — `[{text, start, end}]`
4. Frontend uses sentence timestamps for synced transcript highlighting during playback
5. Graceful fallback: if `whisper` is not installed, skip without error

### Supabase Storage upload

After TTS generation:
1. Save MP3 locally to `~/Documents/Briefings/YYYY-MM-DD/audio-{lang}-{date}.mp3`
2. Upload to Supabase Storage as `briefing-{lang}-latest.mp3` (overwrite)
3. Save public URL to `wsj_briefings.audio_url`

---

## Frontend Changes

Current `page.tsx` reads local files via `fs/promises` (temporary hack for prototyping). Must be replaced with Supabase queries for production.

### Remove
```typescript
// DELETE — local file reads
import { readFile } from 'fs/promises'
const text = await readFile('public/audio/...', 'utf-8')
```

### Replace with
```typescript
// Fetch from Supabase
const { data: briefings } = await supabase
  .from('wsj_briefings')
  .select('briefing_text, chapters, audio_url, date, category')
  .eq('date', targetDate)
  .in('category', ['EN', 'KO'])

// EN briefing
const enBriefing = briefings.find(b => b.category === 'EN')
// KO briefing
const koBriefing = briefings.find(b => b.category === 'KO')

// Audio player: <audio src={enBriefing.audio_url} />
// Chapters: enBriefing.chapters (JSON array)
// Text: enBriefing.briefing_text
```

### `news-service.ts` fix
Change `getLatestBriefing()` from `.eq('category', 'ALL')` to `.in('category', ['EN', 'KO'])` to match the script's storage convention.

---

## GitHub Actions: Decommission Plan

Once the Mac Mini pipeline is verified (3+ successful days):

1. **Disable** the workflow: GitHub repo → Actions → Finance Pipeline → `...` → Disable workflow
2. **Don't delete** the YAML yet — keep as reference/fallback for 30 days
3. **After 30 days**: Delete `.github/workflows/finance-pipeline.yml` and remove GitHub Secrets

**Fallback**: If Mac Mini has issues, re-enable the GitHub Actions workflow. Jobs 1-4 work immediately. Only Job 5 (briefing) needs separate handling.

---

## Output Files

```
scripts/output/
  wsj_items.jsonl                      # Phase 1: exported articles
  wsj_google_news_results.jsonl        # Phase 1: search results
  wsj_ranked_results.jsonl             # Phase 2: ranked candidates
  articles/                            # Phase 3: crawled content (debug)

~/Documents/Briefings/                 # Phase 5: briefing outputs (outside repo)
  YYYY-MM-DD/
    articles-input-YYYY-MM-DD.txt      # assembled articles (debug/audit)
    briefing-en-YYYY-MM-DD.txt         # EN briefing text
    briefing-ko-YYYY-MM-DD.txt         # KO briefing text
    chapters-en-YYYY-MM-DD.json        # EN chapter markers (title + position)
    chapters-ko-YYYY-MM-DD.json        # KO chapter markers
    audio-en-YYYY-MM-DD.mp3            # EN audio (local archive)
    audio-ko-YYYY-MM-DD.mp3            # KO audio (local archive)

Supabase Storage (briefings bucket):     # Latest audio only (overwritten daily)
  briefing-en-latest.mp3               # EN audio (CDN-backed, frontend uses this)
  briefing-ko-latest.mp3               # KO audio

logs/
  pipeline-YYYY-MM-DD.log             # Full pipeline log per day
  launchd-stdout.log                   # launchd stdout (small)
  launchd-stderr.log                   # launchd stderr (errors only)
```

---

## Monitoring & Troubleshooting

### Quick Health Check

```bash
# Did today's pipeline run?
ls -la ~/Project/araverus/logs/pipeline-$(date +%Y-%m-%d).log

# Did briefing generate?
ls -la ~/Project/araverus/scripts/output/briefings/$(date +%Y-%m-%d)/

# Any errors?
grep -E "FATAL|ERROR|WARN" ~/Project/araverus/logs/pipeline-$(date +%Y-%m-%d).log
```

### Common Failures

| Symptom | Cause | Fix |
|---|---|---|
| No log file for today | launchd didn't fire | `launchctl list \| grep araverus` — check if loaded. Check Mac wasn't asleep all day |
| `ModuleNotFoundError` | venv not found | Verify `$VENV` path in `run_pipeline.sh` |
| `FATAL: Ingest failed` | Supabase unreachable or RSS feeds down | Check internet, Supabase status, retry manually |
| `WARN: Google News search had errors` | Rate limiting or network | Normal — continues with whatever results were found |
| `ERROR: Embedding rank failed` | No search results from Phase 1 | Check if `wsj_google_news_results.jsonl` is empty |
| `WARN: Crawl had errors` | Some sites blocked, timeouts | Normal — partial crawl is fine, retryable next day |
| `WARN: Embed/thread had errors` | Embedding model download or Gemini API error | Check internet, verify `GEMINI_API_KEY` in Keychain. Thread failures are non-blocking |
| `ERROR: Briefing generation failed` | Gemini API error or 0 articles | Check `GEMINI_API_KEY`, check `wsj_items.briefed` filter |
| `Could not load X from Keychain` | Key not stored or wrong service name | Run `security add-generic-password -a "KEY_NAME" -s "araverus" -w "value"` |
| `ffmpeg: command not found` | PATH not set in launchd | Add `/opt/homebrew/bin` to PATH in plist |
| Playwright error | Browser not installed | Run `playwright install chromium` in venv |

### Log Rotation

Add a second launchd job or a simple weekly cleanup:

```bash
# In crontab (log cleanup doesn't need the full pipeline venv)
0 0 * * 0 find ~/Project/araverus/logs -name "pipeline-*.log" -mtime +30 -delete
```

---

## Cost Per Day

| Component | Provider | Estimate |
|---|---|---|
| RSS Ingest | Free (WSJ RSS) | $0 |
| Google News Search | Free (RSS scrape) | $0 |
| Embedding Ranking | Local (all-MiniLM-L6-v2) | $0 |
| URL Resolution | Free (HTTP redirects) | $0 |
| Crawling | Free (Playwright + newspaper4k) | $0 |
| LLM Analysis per crawl | Gemini 2.5 Flash | ~$0.005 |
| Thread LLM grouping | Gemini 2.5 Flash | ~$0.003 |
| Briefing Curation | Gemini 2.5 Pro | ~$0.006 |
| EN Briefing | Gemini 2.5 Pro | ~$0.051 |
| KO Briefing | Gemini 2.5 Pro | ~$0.063 |
| EN TTS | Google Chirp 3 HD | ~$0.144 |
| KO TTS | Gemini TTS Preview | ~$0.060 |
| **Total per day** | | **~$0.33** |
| **Monthly (daily)** | | **~$10.00** |

---

## Security

### Credential Isolation

```
macOS Keychain (service: "araverus")  # Pipeline keys (Supabase, Gemini)
~/credentials/araverus-tts-sa.json    # Google Cloud service account (outside repo)
.env.local                            # Local dev only (gitignored)
```

- Pipeline keys stored in macOS Keychain — no plaintext files on disk
- `SUPABASE_SERVICE_ROLE_KEY` has full DB access — treat as root password
- Service account JSON stored **outside the repo directory**
- `.env.local` exists for local dev convenience but is gitignored

### Future AI Agent Isolation (Open Claw, etc.)

If running untrusted AI agents on the same Mac Mini:

- Run agents inside **Docker containers** with no host filesystem access
- **Never** mount `~/Project/araverus/` or `~/credentials/` into agent containers
- Create **separate API keys** with minimal scopes for each agent project
- The araverus pipeline runs natively (trusted code); agents run containerized (untrusted code)

---

## Implementation Checklist

### Phase A: DB + Schema (safe, non-breaking)
- [x] Run migration: `ALTER TABLE wsj_briefings ADD COLUMN chapters jsonb`
- [ ] Run migration: `ALTER TABLE wsj_briefings ADD COLUMN sentences jsonb`
- [ ] Create Supabase Storage bucket: `INSERT INTO storage.buckets (id, name, public) VALUES ('briefings', 'briefings', true)`

### Phase B: Mac Mini Environment Setup
- [ ] `git pull` (or clone) + checkout branch
- [ ] `brew install python@3.11 ffmpeg`
- [ ] `python3 -m venv .venv && source .venv/bin/activate`
- [ ] `pip install -r scripts/requirements.txt`
- [ ] `playwright install chromium`
- [ ] Store 3 keys in macOS Keychain (`NEXT_PUBLIC_SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `GEMINI_API_KEY`)
- [ ] Place Google Cloud service account JSON at `~/credentials/araverus-tts-sa.json`
- [ ] Verify Keychain: `source scripts/load_env.sh` should print "Env loaded from Keychain"

### Phase C: Script Changes (`generate_briefing.py`)
- [x] Add `[CHAPTER:]` marker instructions to EN/KO prompts
- [x] Add chapter extraction logic (regex → JSON)
- [x] Add marker removal before TTS
- [x] Add `chapters` JSON to DB save
- [x] Add Supabase Storage upload (latest audio overwrite)
- [x] Add `audio_url` to DB save
- [x] Add Whisper sentence alignment after TTS (graceful fallback if whisper not installed)
- [x] Add `sentences` JSON to DB save

### Phase C.5: Verify Embed + Thread
- [ ] `python scripts/embed_and_thread.py` (daily mode — threads today's articles)
- [ ] Check thread quality: `SELECT title, member_count FROM wsj_story_threads WHERE active=true ORDER BY member_count DESC LIMIT 10`

### Phase D: Verify Pipeline
- [ ] `python scripts/generate_briefing.py --dry-run` (Phase 5 only)
- [ ] `python scripts/generate_briefing.py --skip-tts --skip-db` (text only)
- [ ] `python scripts/generate_briefing.py --output-dir ~/Documents/Briefings` (full run)
- [ ] `bash scripts/run_pipeline.sh` (full pipeline, manual)

### Phase E: launchd Setup
- [ ] `chmod +x scripts/run_pipeline.sh`
- [ ] `mkdir -p logs` + add `logs/` to `.gitignore`
- [ ] Create plist at `~/Library/LaunchAgents/com.araverus.pipeline.plist`
- [ ] `launchctl load` + `launchctl start` (manual test)
- [ ] Verify next morning's automatic run

### Phase F: Frontend
- [x] Fix `news-service.ts`: `.eq('category', 'ALL')` → `.in('category', ['EN', 'KO'])`
- [x] Remove `fs/promises` local file reads from `page.tsx`
- [x] Replace with Supabase queries (`briefing_text`, `chapters`, `sentences`, `audio_url`)
- [x] Pass `sentences` to BriefingPlayer for synced transcript highlighting
- [x] Fix download filename `.wav` → `.mp3`

### Phase G: Decommission GitHub Actions
- [ ] After 3 successful Mac Mini days: disable GitHub Actions workflow
- [ ] After 30 days: delete workflow YAML + remove GitHub Secrets

## Audio Debugging: Local File Fallback

Until the full pipeline (Phase 5 → Supabase Storage upload) is running on Mac Mini, the frontend falls back to local files for audio, chapters, sentences, and transcripts because `wsj_briefings.audio_url` is `null` and `sentences` column doesn't exist yet in DB.

### Problem
- DB `wsj_briefings` has no `audio_url`, no `sentences` column, and `chapters` is null
- Without fallback, player renders with no `<audio>` source (silent), no chapter navigation, no transcript highlighting

### Local files used for testing

**Audio** (served from `public/`):
```
public/audio/chirp3-en-pro-friendly-2026-02-16.wav   # EN TTS
public/audio/gemini-tts-ko-kore-2026-02-16.wav       # KO TTS
public/audio/gemini-tts-ko-kore-2026-02-15.mp3       # KO TTS (older)
```

**Chapters, sentences, transcripts** (read server-side from `notebooks/tts_outputs/text/`):
```
notebooks/tts_outputs/text/chapters-en-2026-02-16.json    # 6 EN chapters (position 0.0–1.0)
notebooks/tts_outputs/text/chapters-ko-2026-02-16.json    # KO chapters
notebooks/tts_outputs/text/sentences-en-2026-02-16.json   # Whisper-aligned EN sentences ({text, start, end})
notebooks/tts_outputs/text/sentences-ko-2026-02-16.json   # Whisper-aligned KO sentences
notebooks/tts_outputs/text/briefing-pro-friendly-2026-02-16.txt  # EN transcript text
notebooks/tts_outputs/text/briefing-ko-pro-2026-02-16.txt        # KO transcript text
```

### Current implementation in `page.tsx`

`page.tsx` is a Server Component. It reads local JSON/text files via `fs/promises` and passes them as fallbacks when DB values are null:

```typescript
import { readFile } from 'fs/promises'
import path from 'path'

// Read local fallback data (server-side only)
const ttsDir = path.join(process.cwd(), 'notebooks/tts_outputs/text')
const [localChaptersEn, localChaptersKo, localSentencesEn, localSentencesKo, localTranscriptEn, localTranscriptKo] = await Promise.all([
  readFile(path.join(ttsDir, 'chapters-en-2026-02-16.json'), 'utf-8').then(JSON.parse).catch(() => undefined),
  readFile(path.join(ttsDir, 'chapters-ko-2026-02-16.json'), 'utf-8').then(JSON.parse).catch(() => undefined),
  readFile(path.join(ttsDir, 'sentences-en-2026-02-16.json'), 'utf-8').then(JSON.parse).catch(() => undefined),
  readFile(path.join(ttsDir, 'sentences-ko-2026-02-16.json'), 'utf-8').then(JSON.parse).catch(() => undefined),
  readFile(path.join(ttsDir, 'briefing-pro-friendly-2026-02-16.txt'), 'utf-8').catch(() => undefined),
  readFile(path.join(ttsDir, 'briefing-ko-pro-2026-02-16.txt'), 'utf-8').catch(() => undefined),
])

// BriefingPlayer props — DB first, local fallback second
en={{
  audioUrl: enBriefing?.audio_url || '/audio/chirp3-en-pro-friendly-2026-02-16.wav',
  chapters: enBriefing?.chapters ?? localChaptersEn,
  transcript: enBriefing?.briefing_text || localTranscriptEn,
  sentences: enBriefing?.sentences ?? localSentencesEn,
}}
ko={{
  audioUrl: koBriefing?.audio_url || '/audio/gemini-tts-ko-kore-2026-02-16.wav',
  chapters: koBriefing?.chapters ?? localChaptersKo,
  transcript: koBriefing?.briefing_text || localTranscriptKo,
  sentences: koBriefing?.sentences ?? localSentencesKo,
}}
```

### Features enabled by local fallback
- **Chapter navigation**: pill buttons on progress bar + clickable chapter list
- **Sentence-level transcript highlighting**: Whisper timestamps sync with audio playback
- **EN/KO toggle**: both languages have full data
- **Resume position**: saved to localStorage per audio URL

### Revert when pipeline is live
Once `generate_briefing.py` uploads to Supabase Storage and saves `audio_url`, `chapters`, and `sentences` to DB:
1. Remove `fs/promises` and `path` imports from `page.tsx`
2. Remove local file reading block
3. Revert to DB-only props (original condition: `enBriefing?.audio_url ? {...} : undefined`)
4. Run migration: `ALTER TABLE wsj_briefings ADD COLUMN sentences jsonb`

---

## Open Questions

- **Notification on failure?** Simple options: macOS Notification Center via `osascript`, or a Discord/Slack webhook curl at the end of `run_pipeline.sh`.
- **Auto-update?** Could add `git pull origin main` at the start of `run_pipeline.sh` to always run latest code. Risk: untested changes break the pipeline. Safer to deploy manually.
- **Historical audio access?** Currently only latest audio on Supabase. If we need to serve past briefings, options: (a) keep N days on Supabase Storage, (b) Cloudflare R2 for full archive, (c) serve from Mac Mini via Cloudflare Tunnel.
