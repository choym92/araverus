<!-- Created: 2026-02-15 -->
# PRD: Mac Mini Briefing Cron Job Setup

## Overview
Deploy `scripts/generate_briefing.py` as a daily cron job on the Mac Mini server. The existing finance pipeline (ingest → crawl → save) stays on GitHub Actions. The briefing job runs independently on the Mac Mini, reading from Supabase and writing text/audio outputs locally + to Supabase.

## Why Mac Mini (Not GitHub Actions)
1. **Service account credentials**: Chirp 3 HD TTS requires a `GOOGLE_APPLICATION_CREDENTIALS` JSON file on disk. GitHub Actions would need base64-encode/decode workaround.
2. **Audio file persistence**: Output files (MP3, text) persist on local disk. No artifact upload/download dance.
3. **Debugging**: Can SSH in, check output files, re-run with `--dry-run` or `--skip-tts`.
4. **Cost**: No Actions minutes consumed for a 3-5 minute job.
5. **Decoupled**: Briefing reads from Supabase (not artifacts), so it doesn't need to chain after GitHub Actions jobs.

## Architecture

```
┌─────────────────────────────┐     ┌──────────────────────────────┐
│   GitHub Actions (6 AM ET)  │     │   Mac Mini (7 AM ET)         │
│                             │     │                              │
│  Job 1: ingest-search       │     │  Cron: generate_briefing.py  │
│  Job 2: rank-resolve        │     │    ├── Read from Supabase    │
│  Job 3: crawl               │     │    ├── LLM curation (Gemini) │
│  Job 4: save-results        │     │    ├── EN/KO briefing gen    │
│         │                   │     │    ├── TTS audio (MP3)       │
│         ▼                   │     │    └── Save to Supabase      │
│    Supabase DB ◄────────────┼─────┼────────────────────┘         │
└─────────────────────────────┘     └──────────────────────────────┘
```

**Timing**: GitHub Actions pipeline runs at 6 AM ET (~45-60 min). Briefing cron runs at 7 AM ET, by which time fresh articles are crawled and analyzed in Supabase.

---

## Prerequisites Checklist

### 1. System Dependencies

| Dependency | Check Command | Install |
|---|---|---|
| Python 3.11+ | `python3 --version` | `brew install python@3.11` |
| ffmpeg | `ffmpeg -version` | `brew install ffmpeg` |
| pip/venv | `python3 -m venv --help` | Bundled with Python |

### 2. Repository Setup

```bash
# Clone the repo (or pull latest)
cd ~/Project
git clone https://github.com/<user>/araverus.git  # or git pull
cd araverus

# Create Python virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r scripts/requirements.txt
```

### 3. Environment Variables

Create `~/Project/araverus/.env` with:

```env
# Supabase
NEXT_PUBLIC_SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJhbGci...

# Google Gemini (for LLM + KO TTS)
GEMINI_API_KEY=AIza...

# Google Cloud (for EN TTS — Chirp 3 HD)
GOOGLE_APPLICATION_CREDENTIALS=/Users/<user>/path/to/service-account.json
```

**Where to get each**:
- `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY`: Supabase Dashboard → Settings → API
- `GEMINI_API_KEY`: Google AI Studio → API Keys
- `GOOGLE_APPLICATION_CREDENTIALS`: Google Cloud Console → IAM → Service Accounts → Keys → Create JSON key. The service account needs `Cloud Text-to-Speech API` enabled.

### 4. Google Cloud Service Account

```bash
# Verify the JSON key file exists and is valid
cat $GOOGLE_APPLICATION_CREDENTIALS | python3 -c "import json,sys; json.load(sys.stdin); print('Valid JSON')"

# Verify TTS API access
python3 -c "
from google.cloud import texttospeech
client = texttospeech.TextToSpeechClient()
print('Chirp TTS client OK')
"
```

### 5. Verify Script Runs

```bash
cd ~/Project/araverus
source .venv/bin/activate

# Step 1: Dry run (no LLM/TTS/DB calls, just query + assemble)
python scripts/generate_briefing.py --dry-run

# Step 2: Text only (LLM briefing, no audio, no DB save)
python scripts/generate_briefing.py --skip-tts --skip-db

# Step 3: Full run
python scripts/generate_briefing.py
```

Check output at `scripts/output/briefings/YYYY-MM-DD/`.

---

## Cron Job Setup

### Option A: crontab (Simple)

```bash
crontab -e
```

Add:

```cron
# Finance Briefing — daily 7 AM ET (12:00 UTC Nov-Mar, 11:00 UTC Mar-Nov)
# Runs after GitHub Actions pipeline (6 AM ET) finishes
0 12 * * * cd /Users/<user>/Project/araverus && /Users/<user>/Project/araverus/.venv/bin/python scripts/generate_briefing.py >> /Users/<user>/Project/araverus/logs/briefing-cron.log 2>&1
```

**Important crontab notes**:
- Use **absolute paths** everywhere (cron has minimal PATH)
- Point directly to `.venv/bin/python` (no `source activate` needed)
- The `cd` ensures relative paths in the script resolve correctly
- `>> log 2>&1` appends stdout+stderr to log file
- Create log directory: `mkdir -p ~/Project/araverus/logs`
- Add `logs/` to `.gitignore`

### Option B: launchd (macOS-native, recommended)

Create `~/Library/LaunchAgents/com.araverus.briefing.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.araverus.briefing</string>

    <key>ProgramArguments</key>
    <array>
        <string>/Users/USER/Project/araverus/.venv/bin/python</string>
        <string>/Users/USER/Project/araverus/scripts/generate_briefing.py</string>
    </array>

    <key>WorkingDirectory</key>
    <string>/Users/USER/Project/araverus</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>

    <!-- 7 AM ET daily = Hour 12 UTC (EST) or Hour 11 (EDT) -->
    <!-- Use Hour 12 for EST; adjust to 11 when DST starts -->
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>12</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>

    <key>StandardOutPath</key>
    <string>/Users/USER/Project/araverus/logs/briefing-launchd.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/USER/Project/araverus/logs/briefing-launchd-err.log</string>

    <!-- Retry if Mac was asleep at scheduled time -->
    <key>StartInterval</key>
    <integer>0</integer>
</dict>
</plist>
```

```bash
# Load the job
launchctl load ~/Library/LaunchAgents/com.araverus.briefing.plist

# Verify it's loaded
launchctl list | grep araverus

# Test run immediately
launchctl start com.araverus.briefing

# Check logs
tail -f ~/Project/araverus/logs/briefing-launchd.log

# Unload (to stop/edit)
launchctl unload ~/Library/LaunchAgents/com.araverus.briefing.plist
```

**launchd advantages over crontab**:
- Runs missed job if Mac was asleep at scheduled time
- Native macOS process management
- Per-job environment variables
- Separate stdout/stderr logs

---

## Output Files

Each run produces:

```
scripts/output/briefings/
  YYYY-MM-DD/
    articles-input-YYYY-MM-DD.txt    # All assembled articles (debug/audit)
    briefing-en-YYYY-MM-DD.txt       # English briefing text
    briefing-ko-YYYY-MM-DD.txt       # Korean briefing text
    audio-en-YYYY-MM-DD.mp3          # English audio (Chirp 3 HD, 128kbps)
    audio-ko-YYYY-MM-DD.mp3          # Korean audio (Gemini TTS, 128kbps)
```

These stay on local disk. The text + audio URL are also saved to Supabase (`wsj_briefings` table).

---

## Monitoring & Troubleshooting

### Log Rotation

```bash
# Add to crontab — rotate logs weekly, keep 4 weeks
0 0 * * 0 cd /Users/<user>/Project/araverus/logs && mv briefing-cron.log "briefing-cron-$(date +\%Y\%m\%d).log" 2>/dev/null; find . -name "briefing-cron-*.log" -mtime +28 -delete
```

### Common Failures

| Symptom | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError` | Wrong Python or venv not activated | Use absolute path to `.venv/bin/python` |
| `GEMINI_API_KEY not set` | Env vars not loaded | Script uses `python-dotenv`; ensure `.env` exists in project root |
| `ffmpeg: command not found` | ffmpeg not in cron PATH | Install: `brew install ffmpeg`. For launchd, add `/opt/homebrew/bin` to PATH in plist |
| `google.auth.exceptions` | Service account JSON missing/invalid | Check `GOOGLE_APPLICATION_CREDENTIALS` path in `.env` |
| `0 articles found` | Pipeline hasn't run yet or all articles already briefed | Check timing — briefing must run after GitHub Actions pipeline. Check `wsj_items.briefed` column |
| `Connection refused` (Supabase) | Network issue on Mac Mini | Check internet connectivity, Supabase status |
| Audio file 0 bytes | TTS API quota exceeded | Check Google Cloud quotas, wait for reset |

### Health Check Script

Create `scripts/check_briefing.sh` (optional):

```bash
#!/bin/bash
# Quick health check — run after cron to verify output
DATE=$(date +%Y-%m-%d)
DIR="scripts/output/briefings/$DATE"

if [ ! -d "$DIR" ]; then
  echo "FAIL: No output directory for $DATE"
  exit 1
fi

for f in briefing-en briefing-ko audio-en audio-ko; do
  FILE="$DIR/$f-$DATE"
  if [ "$f" = "audio-en" ] || [ "$f" = "audio-ko" ]; then
    FILE="$FILE.mp3"
  else
    FILE="$FILE.txt"
  fi
  if [ ! -s "$FILE" ]; then
    echo "FAIL: Missing or empty $FILE"
    exit 1
  fi
done

echo "OK: All briefing files present for $DATE"
```

---

## Cost Per Run

| Component | Estimate |
|---|---|
| LLM Curation (Gemini Pro) | ~$0.006 |
| EN Briefing (Gemini Pro) | ~$0.051 |
| KO Briefing (Gemini Pro) | ~$0.063 |
| EN TTS (Chirp 3 HD) | ~$0.144 |
| KO TTS (Gemini TTS) | ~$0.060 |
| **Total per run** | **~$0.32** |
| **Monthly (daily)** | **~$9.70** |
| **Monthly (weekdays only)** | **~$7.10** |

---

## Security Notes

- `.env` file must be in `.gitignore` (already is)
- Service account JSON must NOT be committed — store outside repo or in a secure location
- `SUPABASE_SERVICE_ROLE_KEY` has full DB access — keep it secure
- `logs/` directory should be in `.gitignore`

---

## Rollback Plan

If the cron job causes issues:

```bash
# 1. Disable the cron job
launchctl unload ~/Library/LaunchAgents/com.araverus.briefing.plist
# or: crontab -e and comment out the line

# 2. If articles were incorrectly marked as briefed, reset:
# (Run in Supabase SQL editor)
UPDATE wsj_items SET briefed = false, briefed_at = NULL
WHERE briefed_at >= '2026-02-15';

# 3. Delete bad briefing records
DELETE FROM wsj_briefings WHERE date = '2026-02-15';
```

---

## Implementation Steps

1. **On MacBook** (now): Commit and push this PRD + all pending changes
2. **On Mac Mini**:
   - [ ] Pull latest from `main`
   - [ ] Install system deps (`python3`, `ffmpeg`)
   - [ ] Set up venv + `pip install -r scripts/requirements.txt`
   - [ ] Create `.env` with all 4 env vars
   - [ ] Place Google Cloud service account JSON
   - [ ] Test: `python scripts/generate_briefing.py --dry-run`
   - [ ] Test: `python scripts/generate_briefing.py --skip-tts --skip-db`
   - [ ] Test: `python scripts/generate_briefing.py` (full run)
   - [ ] Set up launchd plist (or crontab)
   - [ ] `mkdir -p logs && echo "logs/" >> .gitignore`
   - [ ] Load the cron job
   - [ ] Verify next morning: check logs + output files + Supabase

## Open Questions

- **Supabase Storage for audio?** Currently MP3 saved locally only. Future: upload to Supabase Storage and save public URL in `wsj_briefings.audio_url`.
- **DST handling for launchd**: launchd uses UTC. Need to manually adjust hour (12→11) when DST starts in March, or write a wrapper that checks ET.
- **Notification on failure?** Consider a simple Slack/email webhook if the cron job fails.
