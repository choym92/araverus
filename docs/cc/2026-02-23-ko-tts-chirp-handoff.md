<!-- Created: 2026-02-23 -->
# Handoff: KO TTS Chirp 3 HD — Failed on First Run

## Status
KO TTS failed on 2026-02-23 pipeline run. EN TTS worked fine. KO briefing text was saved to DB (no audio).

## What Was Done
Transitioned KO TTS from Gemini Pro Preview TTS to Google Cloud Chirp 3 HD in `scripts/generate_briefing.py`:
- Removed `KO_TTS_MODEL`, `KO_TTS_STYLE_PREFIX`
- Added `KO_TTS_VOICE = "ko-KR-Chirp3-HD-Kore"`, `KO_TTS_SPEAKING_RATE = 1.0`
- Rewrote `generate_tts_ko()` to use `chirp.synthesize_speech()` (same pattern as EN)
- Updated `CostTracker` to use `ko_tts_chars` instead of `ko_tts_input_tokens`/`ko_tts_audio_sec`
- Updated `init_clients()` and `validate_env_vars()` to create Chirp client for KO
- Updated `docs/4-news-backend.md` cost summary

## Root Cause
Chirp 3 HD API limit is **5000 bytes** per request (not characters). Korean UTF-8 = 3 bytes/char.

```
KO_TTS_MAX_CHARS = 3000 → 3000 × 3 = ~9000 bytes → exceeds 5000 byte limit
```

Error from log:
```
400 Either `input.text` or `input.ssml` is longer than the limit of 5000 bytes.
```

EN works because ASCII = 1 byte/char, and `EN_TTS_MAX_CHARS = 4000` → ~4000 bytes < 5000.

## Fix Needed
Change chunking to use **byte length** instead of character length. Options:

### Option A: Simple — lower KO_TTS_MAX_CHARS
```python
KO_TTS_MAX_CHARS = 1600  # 1600 × 3 = ~4800 bytes, under 5000
```
Quick but fragile — mixed Korean+ASCII text has variable byte ratios.

### Option B: Byte-aware chunking (recommended)
```python
KO_TTS_MAX_BYTES = 4800  # safe margin under 5000
# In chunking loop, check len(chunk.encode("utf-8")) instead of len(chunk)
```

## Log Location
```
/Users/paul/Documents/Project/araverus/logs/pipeline-2026-02-23.log
```
Key lines: 5611-5618 (KO TTS failure)

### Other log files
| File | Content |
|------|---------|
| `logs/launchd-stdout.log` | Full pipeline stdout (cumulative) |
| `logs/launchd-stderr.log` | Pipeline stderr |
| `logs/pipeline-YYYY-MM-DD.log` | Daily pipeline log |

## Other Issues in Same Run
- **EN Whisper alignment failed** (L5595): MPS float64 dtype error — pre-existing issue, not related to this change
- **LLM 503 errors** (L4362, L4822): Gemini capacity spike — transient, not related

## Files Changed
- `scripts/generate_briefing.py` — TTS rewrite (uncommitted)
- `docs/4-news-backend.md` — cost summary updated (uncommitted)
- `docs/cc/_pending-docs.md` — has entry for this change

## To Resume
1. Read this file
2. Fix byte-aware chunking in `generate_tts_ko()` (line ~880 in generate_briefing.py)
3. Verify: `.venv/bin/ruff check scripts/generate_briefing.py`
4. Test: `python scripts/generate_briefing.py --help`
5. Re-run pipeline for 2026-02-23 to generate KO audio
