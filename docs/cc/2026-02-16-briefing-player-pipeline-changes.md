<!-- Created: 2026-02-16 -->
# Briefing Player — Pending Pipeline & Backend Changes

## Context
The briefing player frontend has been enhanced with chapters, EN/KO toggle, transcript, volume control, download, keyboard shortcuts, and resume position. Currently the frontend reads from **local files** (temp hack). This doc lists everything that needs to change for production (Mac Mini launchd automation).

---

## 1. DB Migration (Supabase)

```sql
ALTER TABLE wsj_briefings ADD COLUMN chapters jsonb;
```

- Stores chapter metadata per briefing row
- Format: `[{"title": "Opening", "position": 0.0}, {"title": "Fed & Inflation", "position": 0.15}, ...]`
- `position` is 0.0–1.0 ratio (multiply by `audio_duration` to get seconds)
- Nullable — old briefings without chapters still work

**No other schema changes needed.** `briefing_text` (transcript) and `audio_url` already exist.

---

## 2. Script Changes (`scripts/generate_briefing.py`)

### 2a. Prompt Update — Add Chapter Marker Rule

Add this section to both `BRIEFING_SYSTEM_EN` (line ~96) and `BRIEFING_SYSTEM_KO` (line ~150), **before** the closing structure section:

**English (add before "Closing structure:"):**
```
Chapter markers (for navigation — IMPORTANT):
Before each new topic cluster, insert a marker on its own line: [CHAPTER: Topic Name]
Use short, clear topic names (e.g., "Fed & Inflation", "AI & Big Tech", "Energy & Oil", "Market Snapshot").
The opening greeting/agenda should be marked as [CHAPTER: Opening].
These markers will be stripped before audio generation — they do NOT affect your script's flow or tone.
Continue writing naturally as before; just add the marker line where the topic transition happens.
```

**Korean (add before "클로징 구조:"):**
```
챕터 마커 (네비게이션용 — 중요):
각 새로운 토픽 그룹이 시작될 때, 별도 줄에 마커를 삽입하세요: [CHAPTER: 토픽 이름]
짧고 명확한 토픽 이름을 사용하세요 (예: "연준 & 인플레이션", "AI & 빅테크", "에너지 & 유가", "마켓 스냅샷").
오프닝 인사/어젠다는 [CHAPTER: 오프닝]으로 마킹하세요.
이 마커들은 오디오 생성 전에 제거됩니다 — 스크립트의 흐름이나 톤에 영향을 주지 않습니다.
기존처럼 자연스럽게 작성하되, 토픽 전환이 일어나는 곳에 마커 줄만 추가하세요.
```

### 2b. Chapter Extraction — Add to `generate_briefing()` or post-processing

After the briefing text is generated, before TTS:

```python
import re

def extract_chapters(text: str) -> tuple[str, list[dict]]:
    """Extract [CHAPTER: ...] markers and return (clean_text, chapters)."""
    pattern = re.compile(r'\[CHAPTER:\s*(.+?)\]\s*\n?')
    matches = list(pattern.finditer(text))
    clean = pattern.sub('', text)
    total_len = len(clean)
    chapters = []
    for m in matches:
        preceding = pattern.sub('', text[:m.start()])
        pos = len(preceding) / total_len if total_len > 0 else 0.0
        chapters.append({"title": m.group(1).strip(), "position": round(pos, 4)})
    return clean, chapters
```

Call it after `generate_briefing()` returns, before TTS:
```python
result_text, chapters = extract_chapters(result.text)
result.text = result_text  # clean text goes to TTS
```

### 2c. Save Chapters to DB — Update `save_briefing_to_db()`

Add `chapters` parameter and include in the record:

```python
def save_briefing_to_db(sb, target_date, category, result, articles, tts_result=None, chapters=None):
    record = { ... }  # existing fields
    if chapters:
        record["chapters"] = chapters  # Supabase handles JSONB serialization
    ...
```

### 2d. Save Clean Text to File

Currently `result.text` is saved to local file and used for TTS. After extracting chapters, the clean text (without markers) should be used for both file save and TTS. No new file needed — just ensure the extraction happens before save.

---

## 3. Frontend Changes (after DB migration)

### 3a. `src/lib/news-service.ts` — Update `Briefing` interface

```typescript
export interface Briefing {
  id: string
  date: string
  category: string
  briefing_text: string
  audio_url: string | null
  audio_duration: number | null
  item_count: number
  chapters: { title: string; position: number }[] | null  // NEW
  created_at: string
}
```

### 3b. `src/lib/news-service.ts` — Fetch both EN and KO briefings

Currently `getLatestBriefing()` returns only one row (category='ALL'). Need to either:
- Fetch two rows (EN + KO) by adding a `lang` parameter, OR
- Fetch both in one call and separate client-side

### 3c. `src/app/news/page.tsx` — Remove local file hack

Replace the `readTextFile`/`readJsonFile` temp logic with DB reads:
- `briefing.chapters` → chapters
- `briefing.briefing_text` → transcript
- `briefing.audio_url` → audio URL
- `wsj_briefing_items` → source articles (already exists)

---

## 4. Notebook Changes (already done)

These changes have already been applied to `notebooks/briefing_prototype.ipynb`:
- Cell 14: EN prompt — chapter marker rule added
- Cell 18: EN generation — chapter extraction + JSON save added
- Cell 21: KO prompt + generation — chapter marker rule + extraction added

**Validated:** EN produced 6 chapters, KO produced 9 chapters on 2026-02-16 run.

---

## 5. Execution Order

```
Step 1: DB migration (add chapters column)          ← safe, non-breaking
Step 2: Update generate_briefing.py (2a, 2b, 2c)    ← git commit + push
Step 3: Mac Mini: git pull                           ← picks up script changes
Step 4: Test: run generate_briefing.py manually      ← verify chapters in DB
Step 5: Frontend: remove local hack (3a, 3b, 3c)    ← read from DB
Step 6: Verify full pipeline end-to-end
```

---

## 6. Impact on LaunchD / Cron Job

The launchd plist does NOT need to change. The script (`generate_briefing.py`) is the only thing that changes. Same command, same arguments, same schedule. The script just:
- Generates text with `[CHAPTER: ...]` markers (new prompt)
- Extracts chapters and strips markers (new logic)
- Saves `chapters` JSON to DB alongside existing fields (new column)
- Passes clean text to TTS (unchanged behavior)

**No new dependencies.** Only `re` (stdlib) is used for chapter extraction.

---

## 7. Current Frontend Features (for reference)

| Feature | Status | Notes |
|---------|--------|-------|
| 30s skip buttons | Done | RotateCcw/RotateCw with "30" label |
| Chapter dots on progress bar | Done | Clickable, shows tooltip |
| Chapter chips below controls | Done | Active chapter highlighted |
| EN/KO language toggle | Done | Switches audio, chapters, transcript |
| Transcript panel | Done | Expandable, scrollable |
| Source articles list | Done | Expandable, shows title + category |
| Volume control + mute | Done | Slider + mute button + M key |
| Download button | Done | Downloads current language audio |
| Keyboard shortcuts | Done | Space, arrows, M |
| Resume position | Done | localStorage persist |
| Playback speed | Done | 0.75x, 1x, 1.25x, 1.5x, 2x |

### Not yet built
- Mini/sticky player (scroll past → bottom bar)
- Share button (copy link + timestamp)
- Waveform visualization
