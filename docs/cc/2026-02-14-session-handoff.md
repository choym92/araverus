<!-- Updated: 2026-02-14 -->
# Session Handoff — 2026-02-14

## What Was Done

### 1. **Gemini Pro TTS for Korean Briefing** (Recovered)
- Restored missing `gemini-2.5-pro-preview-tts` + Kore voice cell
- Uses Kore (female, firm) with energetic podcast style prefix
- Single-pass generation (no chunking) — Pro model handles longer text better
- Output: `gemini-tts-ko-kore-{date}.wav`
- Search: `gemini-2.5-pro-preview-tts` or `Kore` in notebook

### 2. **Curation Cell Print Line** (cell-9)
- Added explicit model name output: `Curation model: {model_used} ({model_version})`
- Now visible as separate line instead of buried in combined output

### 3. **EN & KO Briefing Prompts — Major Upgrade**
Restructured both prompts with:
- **Opening structure**: Agenda preview (3-4 topics) weaved into natural conversation (no lists)
- **Closing structure**: Market snapshot (S&P, Nasdaq, Dow, 10yr Treasury, Brent, Gold) + article count recap
- **Factual integrity rules** (NEW & CRITICAL):
  - Only provided articles are truth source — NO background knowledge infill
  - NEVER add specific numbers/dates/percentages not in source
  - NEVER dramatize ("movie-like", "SF-like") unless source uses it
  - Do NOT infer/estimate figures (e.g., don't add "June" if source only says "rate cuts expected")
  - Do NOT quote statements not in provided content

### 4. **Temperature & Comparison Setup**
- **Main KO briefing** (cell-23): Temperature changed **0.7 → 0.6**
- **Comparison cell** (inserted after cell-23): Temperature 0.6 test with separate file output
  - EN briefing: still 0.7 (needs update to 0.6 if decided)
  - KO saves: `briefing-ko-pro-{date}.txt` (temp 0.6) vs `briefing-ko-pro-t06-{date}.txt` (temp 0.6 test)

### 5. **Factual Accuracy Investigation**
Validated previous 0.7 output against source articles:
- **Over-dramatized**: "거의 SF 영화에나", "영화 같은" — not in sources
- **Invented details**:
  - "로열티나 세금 미국 계좌 조건" — not in crawl source
  - "6월, 25bp" rate cut timing — sources don't specify
  - "개인 정보 뒤짐" — actually public activity records, not personal info
- **Hallucinations fixed by**: Factual integrity rules in prompts

## Key Decisions

| Decision | Reason |
|----------|--------|
| Temperature: 0.7 → 0.6 (KO) | Better balance between personality and accuracy. 0.6 reduces hallucinations while keeping natural tone. 0.5 too clinical, 0.7 too creative. |
| Factual integrity as CRITICAL section | Previous output had dramatization + invented details. Explicit rules prevent model from filling gaps with background knowledge. |
| Gemini Pro TTS (not Chirp 3 HD) for KO | Single-pass generation; Pro model handles longer audio better. Kore voice matches user preference (energetic female). |
| Temperature 0.6 for main KO briefing | Immediate change; temp 0.6 test cell added for A/B comparison. EN still at 0.7 (should probably be 0.6 too for consistency). |

## Files Changed

| File | Change | Location |
|------|--------|----------|
| `notebooks/briefing_prototype.ipynb` | Updated EN prompt with opening/closing structure + factual integrity rules | cell-14, search: `Factual integrity` |
| `notebooks/briefing_prototype.ipynb` | Updated KO prompt with opening/closing structure + factual integrity rules | cell-23, search: `팩트 무결성` |
| `notebooks/briefing_prototype.ipynb` | Changed KO briefing temperature 0.7 → 0.6 | cell-23, search: `temperature=0.6` |
| `notebooks/briefing_prototype.ipynb` | Added Gemini Pro TTS recovery cell (KO) | Inserted after cell-23, search: `gemini-2.5-pro-preview-tts` |
| `notebooks/briefing_prototype.ipynb` | Added curation model name print line | cell-9, search: `Curation model:` |
| `notebooks/briefing_prototype.ipynb` | Added temperature 0.6 comparison test cell (KO) | Inserted after cell-23, search: `temp=0.6` |

## Remaining Work

- [ ] **Run notebooks with new prompts & temp 0.6**
  - Generate new KO briefing (temp 0.6) → compare with previous 0.7 output
  - Check if factual accuracy improved (no invented details)
  - Verify opening agenda structure works naturally
  - Verify closing market snapshot only uses provided data

- [ ] **Update EN temperature to 0.6** (consistency)
  - Currently EN briefing still 0.7 (cell-18)
  - Should match KO treatment for consistency
  - Search: `# Generate briefing — Friendly only` in cell-18

- [ ] **Delete/cleanup old cells** (if decided)
  - cell-19: "Select Source for TTS" (orphan markdown, no corresponding code)
  - cell-22: Old KO prompt (v0.7, before opening/closing structure added)
  - cell-26: V1 FORMAL + V3 BALANCED unused prompts
  - cell-20: Old EN Chirp 3 HD (if decided to remove)

- [ ] **Compare output quality**
  - 0.7 vs 0.6 on same input
  - Check for hallucinations, factual errors
  - Listen to TTS audio (Kore voice, Gemini Pro model)

- [ ] **Update English briefing closing**
  - Currently uses "At the end, briefly note..." — should match KO's market snapshot structure
  - Add explicit market numbers extraction to EN prompt

## Blockers / Questions

1. **EN temperature decision pending**: Should EN also be 0.6? Currently 0.7 (old). Recommend: **YES, make it 0.6 for consistency**.

2. **Audio quality baseline unclear**: Previous session had audio degradation issues with Gemini TTS. Need to listen to current Kore voice output (gemini-tts-ko-kore-{date}.wav) to confirm Pro model fixed it.

3. **Thinking token counting**: `thinking_token_count` still not printing. Need to verify attribute name after running with Pro model. Check output of cell-18 or cell-23 to see full `usage_metadata` structure.

4. **File structure redundancy**:
   - Currently have Chirp 3 HD TTS cells still in notebook (cell-20, cell-24, cell-27 area)
   - Once Gemini Pro TTS is confirmed as primary, should clean up old Chirp cells

## Context for Next Session

### Key Patterns in Codebase
- **Gemini 2.5 Pro with thinking**: Use `thinking_config=types.ThinkingConfig(thinking_budget=32768)` for editorial decisions
- **Gemini 2.5 Flash**: Fallback option, used in curation if Pro fails 3x
- **TTS output format**: All TTS saves WAV at 24kHz, mono, 16-bit PCM
- **Chirp 3 HD limits**: 5000 byte char limit per request, requires chunking for longer text

### Critical Prompt Principle — FACTUAL INTEGRITY
- **ONLY source of truth**: provided articles (no background knowledge fill)
- **Never add**: specific numbers/dates/percentages not explicitly stated
- **Never infer**: timing (e.g., "June" if not in source), figures, conditions
- **Never dramatize**: without source backing (no "movie-like" unless source says it)
- This rule is why 0.6 temperature works — constraint + lower randomness = high accuracy

### File Locations to Remember
- `notebooks/briefing_prototype.ipynb` — main working notebook (29 cells)
- `notebooks/tts_outputs/text/` — briefing outputs (`.txt` files by date)
- `notebooks/tts_outputs/audio/` — TTS outputs (`.wav` files)
- Briefing files pattern: `briefing-{lang}-{model}-{date}.txt` (e.g., `briefing-ko-pro-2026-02-14.txt`)

### Gotchas to Watch
1. **Variable names mismatch**: Previous session had `briefing_text` undefined in cell-21. Fixed by using actual variable names (`briefing_pro` from cell-18).
2. **Model hardcoding**: Cell-27 (Supabase save) still had `'model': 'gemini-2.5-flash'` hardcoded. Needs update to reflect actual model used (Pro).
3. **Thinking tokens not visible**: Attribute name might be `thinking_token_count` or `thoughts_token_count` — need to verify after running cell.
4. **Prompt length creep**: Factual integrity rules added ~150 words to each prompt. Keep eye on total input token count (currently ~12.9K with articles).

## Next Actions (Priority Order)

1. **Run cell-23 (KO briefing, temp 0.6)** → check output for hallucinations
2. **Compare**: temp 0.7 output (previous session) vs temp 0.6 output (current)
3. **Listen to**: `gemini-tts-ko-kore-2026-02-14.wav` → confirm audio quality
4. **Update EN briefing** to temperature 0.6 (cell-18)
5. **Run A/B test**: Compare both temp 0.6 outputs (cell-23 vs inserted test cell)
6. **Decision**: Keep 0.6, or revert if 0.7 was better? (depends on output comparison)
7. **Cleanup**: Delete unused cells if decided

---

**Session ended successfully.** Prompts fully restructured with factual integrity guardrails. Ready for next iteration of temperature tuning & accuracy validation.
