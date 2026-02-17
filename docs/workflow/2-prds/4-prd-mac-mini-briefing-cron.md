<!-- Updated: 2026-02-16 -->
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
| **HuggingFace model** | Cache action, still slow first run | Downloaded once, persistent |
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
│                  ├── Phase 5: Briefing               (~5 min)    │
│                  │   └── generate_briefing.py                    │
│                  │                                               │
│                  └── Log summary + exit code                     │
│                                                                  │
├── logs/pipeline-YYYY-MM-DD.log                                   │
├── scripts/output/          (JSONL intermediates)                 │
└── scripts/output/briefings/ (text + audio)                       │
```

**Total runtime**: ~45 min end-to-end (crawl is the bottleneck).

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

mkdir -p "$LOG_DIR" "$SCRIPTS/output"

# Redirect all output to log (and stdout for launchd)
exec > >(tee -a "$LOG_FILE") 2>&1

echo "============================================"
echo "Finance Pipeline — $DATE"
echo "Started: $(date)"
echo "============================================"

cd "$PROJECT_DIR"

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
$VENV "$SCRIPTS/generate_briefing.py" || echo "ERROR: Briefing generation failed"

# ── Done ────────────────────────────────────────────────
echo ""
echo "============================================"
echo "Pipeline complete — $(date)"
echo "============================================"
```

**Key design decisions**:
- `set -euo pipefail` for strict error handling
- Phase 1 failure = hard abort (no articles = nothing to do)
- Phase 3 (crawl) and Phase 5 (briefing) failures = log warning but don't kill the pipeline
- `tee -a` writes to both log file and stdout (launchd captures stdout)
- Date-stamped log files — one per day, easy to grep

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

### 3. Environment Variables

Create `~/Project/araverus/.env`:

```env
# Supabase (used by all pipeline scripts)
NEXT_PUBLIC_SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJhbGci...

# OpenAI (used by crawl_ranked.py → llm_analysis.py)
OPENAI_API_KEY=sk-...

# Google Gemini (used by generate_briefing.py for LLM + KO TTS)
GEMINI_API_KEY=AIza...

# Google Cloud (used by generate_briefing.py for EN TTS — Chirp 3 HD)
GOOGLE_APPLICATION_CREDENTIALS=/Users/<user>/credentials/araverus-tts-sa.json
```

**Where to get each**:

| Key | Source |
|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase Dashboard → Settings → API → Project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase Dashboard → Settings → API → service_role (secret) |
| `OPENAI_API_KEY` | platform.openai.com → API Keys |
| `GEMINI_API_KEY` | aistudio.google.com → API Keys |
| `GOOGLE_APPLICATION_CREDENTIALS` | Google Cloud Console → IAM → Service Accounts → Create Key (JSON). Enable `Cloud Text-to-Speech API` on the project. |

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

    <!-- Run missed job when Mac wakes from sleep -->
    <key>AbandonProcessGroup</key>
    <false/>
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
    articles-input-YYYY-MM-DD.txt      # assembled articles
    briefing-en-YYYY-MM-DD.txt         # EN briefing text
    briefing-ko-YYYY-MM-DD.txt         # KO briefing text
    audio-en-YYYY-MM-DD.mp3            # EN audio (~20MB)
    audio-ko-YYYY-MM-DD.mp3            # KO audio (~20MB)

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
| `ERROR: Briefing generation failed` | Gemini API error or 0 articles | Check `GEMINI_API_KEY`, check `wsj_items.briefed` filter |
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
| LLM Analysis per crawl | OpenAI gpt-4o-mini | ~$0.02 |
| Briefing Curation | Gemini 2.5 Pro | ~$0.006 |
| EN Briefing | Gemini 2.5 Pro | ~$0.051 |
| KO Briefing | Gemini 2.5 Pro | ~$0.063 |
| EN TTS | Google Chirp 3 HD | ~$0.144 |
| KO TTS | Gemini TTS Preview | ~$0.060 |
| **Total per day** | | **~$0.35** |
| **Monthly (daily)** | | **~$10.50** |

---

## Security

### Credential Isolation

```
~/Project/araverus/.env              # Pipeline keys (Supabase, OpenAI, Gemini)
~/credentials/araverus-tts-sa.json   # Google Cloud service account (outside repo)
```

- `.env` and `credentials/` are in `.gitignore` — never committed
- `SUPABASE_SERVICE_ROLE_KEY` has full DB access — treat as root password
- Service account JSON stored **outside the repo directory**

### Future AI Agent Isolation (Open Claw, etc.)

If running untrusted AI agents on the same Mac Mini:

- Run agents inside **Docker containers** with no host filesystem access
- **Never** mount `~/Project/araverus/` or `~/credentials/` into agent containers
- Create **separate API keys** with minimal scopes for each agent project
- The araverus pipeline runs natively (trusted code); agents run containerized (untrusted code)

---

## Implementation Checklist

### On MacBook (now)
- [x] Write this PRD
- [ ] Commit + push to `feature/news-frontend`

### On Mac Mini
- [ ] `git pull` (or clone) + checkout branch
- [ ] `brew install python@3.11 ffmpeg`
- [ ] `python3 -m venv .venv && source .venv/bin/activate`
- [ ] `pip install -r scripts/requirements.txt`
- [ ] `playwright install chromium`
- [ ] Create `.env` with 5 keys (copy from MacBook + add OPENAI_API_KEY)
- [ ] Place Google Cloud service account JSON at `~/credentials/araverus-tts-sa.json`
- [ ] Verify: `python scripts/wsj_ingest.py` (Phase 1 only)
- [ ] Verify: `python scripts/generate_briefing.py --dry-run` (Phase 5 only)
- [ ] Verify: `bash scripts/run_pipeline.sh` (full pipeline, manual)
- [ ] `chmod +x scripts/run_pipeline.sh`
- [ ] `mkdir -p logs`
- [ ] Add `logs/` to `.gitignore`
- [ ] Create plist at `~/Library/LaunchAgents/com.araverus.pipeline.plist`
- [ ] `launchctl load ~/Library/LaunchAgents/com.araverus.pipeline.plist`
- [ ] `launchctl start com.araverus.pipeline` (manual test)
- [ ] Check logs: `tail -f logs/pipeline-$(date +%Y-%m-%d).log`
- [ ] Wait for next morning's automatic run — verify all 5 phases complete
- [ ] After 3 successful days: disable GitHub Actions workflow

## Open Questions

- **Supabase Storage for audio?** MP3 saved to `~/Documents/Briefings/`. Free tier = 1GB, at ~40MB/day fills in ~25 days. Not viable without Pro plan ($25/mo, 100GB). For now, local-only. Future: consider Pro plan or self-hosted storage.
- **Notification on failure?** Simple options: macOS Notification Center via `osascript`, or a Discord/Slack webhook curl at the end of `run_pipeline.sh`.
- **Auto-update?** Could add `git pull origin main` at the start of `run_pipeline.sh` to always run latest code. Risk: untested changes break the pipeline. Safer to deploy manually.
