<!-- Updated: 2026-02-14 -->
# Session Handoff — Thinking Budget Optimization & Cost Analysis

## Summary
Converted notebook briefing prototype to production script, compared thinking budgets (32K vs 4K), optimized for cost, and calculated monthly expenses.

## What Was Done

### 1. Script Creation: `scripts/generate_briefing.py`
- **Status**: ✅ Complete (1,063 lines)
- Consolidated 26-cell notebook into single production-ready script
- Proper error handling, CLI args, structured logging, cost tracking
- Fixed 6 bugs from notebook (undefined variables, dead code, temperature inconsistency)
- Added previously-briefed article filter (cell-3 logic)
- Updated KO TTS style prefix (calm delivery, avoiding breathless tone)

### 2. Thinking Budget Comparison: 32K vs 4K
**Experiment**: Lowered thinking budget from 32,768 to 4,096 tokens and compared output quality.

**EN Briefing Results** (4K is BETTER):
- 4K: ~1,800 words ✅ (hits target 1,800-2,000)
- 32K: ~1,499 words ❌ (under target)
- 4K includes "what to watch" closing section (prompt requirement)
- 4K adds 61bp rate cut expectation, specific dollar figures ($678M Moderna), 7% stock drops
- 4K covers fewer stories (20 vs 28) but deeper — aligns with "60-70% on top 8-12" rule

**KO Briefing Results** (marginal, both ~equivalent):
- Both equally rich in detail
- 32K slightly tighter narrative flow
- 4K adds some unique coverage (Rivian, Diageo)
- Quality difference indistinguishable

**Decision**: Keep **4K thinking budget across all** (curation, EN, KO).

### 3. TTS Style Fix (Notebook)
- **Problem**: Korean TTS sounded breathless (energetic + fast)
- **Old**: "[활기차고 에너지 넘치는 팟캐스트 진행자 톤, 흥미로운 부분에서 목소리에 힘을 주고, 빠르지만 명확하게]"
- **New**: "[차분하고 또렷한 팟캐스트 진행자 톤, 문장 사이에 자연스러운 호흡을 넣고, 적당한 속도로 명확하게]"

### 4. Previously-Briefed Filter
- **Added to notebook** (cell-3) and **script** (new `filter_previously_briefed()` function)
- Prevents same articles appearing in consecutive days
- Queries `wsj_briefing_items` junction table to identify already-used articles
- Filters before LLM curation

### 5. Cost Analysis & Monthly Projection

#### 1회 실행 비용 (Per Run - TTS 포함)
| Component | Input | Output | Thinking | Cost |
|-----------|-------|--------|----------|------|
| Curation (Pro, 4K) | 2.5K tok | 120 tok | 1.2K tok | $0.0058 |
| EN Briefing (Pro, 4K) | 12.8K tok | 2K tok | 4K tok | $0.0512 |
| KO Briefing (Pro, 4K) | 13.4K tok | 3.1K tok | 4K tok | $0.0634 |
| EN TTS (Chirp 3 HD) | 9,000 chars | - | - | $0.1440 |
| KO TTS (Gemini) | 6,000 chars | - | - | $0.0600 |
| **Total per run** | | | | **$0.324** |

#### 월간 비용 (Monthly Cost)

**매일 돌릴 경우 (30 runs/month):**
- **Total: ~$9.70/month**
  - LLM: ~$3.70 (curation + EN/KO briefings)
  - TTS: ~$6.00 (EN Chirp 3 HD + KO Gemini)

**평일만 (22 runs/month):**
- **Total: ~$7.10/month**
  - LLM: ~$2.70
  - TTS: ~$4.40

**TTS 없이 텍스트만 (30 runs/month):**
- **Total: ~$3.70/month**

#### 왜 이 가격인가? (Why This Cost)

1. **TTS가 전체 비용의 64%** ($0.20/$0.32 per run)
   - EN Chirp 3 HD: $0.144/run ($16/1M chars, ~9,000 chars per brief)
   - KO Gemini TTS: $0.060/run ($10/1M chars, ~6,000 chars per brief)
   - LLM은 상대적으로 저렴 (thinking 4K로 낮춰서)

2. **Thinking 비용 절감 효과 (32K→4K)**
   - Thinking tokens: $3.75/1M tokens (Pro에서 가장 비싼 부분)
   - 32K budget: thinking만 ~$0.11/run
   - 4K budget: thinking만 ~$0.015/run
   - **월간 약 $3.30 절약** (30 runs/month)

3. **Curation은 저렴**
   - Flash 폴백으로 인한 비용 최소화
   - Pro 3회 시도 → Flash 1회 시도 (실패 시)
   - 평균 ~$0.006/curation

## Files Changed
- ✅ `scripts/generate_briefing.py` — 새로 생성 (1,063 lines)
- ✅ `scripts/requirements.txt` — google-genai, google-cloud-texttospeech 추가
- ✅ `notebooks/briefing_prototype.ipynb` — 3개 cells 수정 (thinking 4096, TTS style, previously-briefed filter)

## Key Decisions & Reasoning

| Decision | Why |
|----------|-----|
| **Thinking budget = 4096** | EN output quality actually better + huge cost savings. More thinking ≠ better output for this task. |
| **Keep both EN & KO TTS providers** | Different languages need different providers (Chirp3 no good KO voice, Gemini TTS preview only). Pragmatic choice. |
| **Previously-briefed filter** | Prevents user fatigue from seeing same articles repeatedly. Junction table makes this efficient. |
| **KO TTS style prefix change** | Original was too energetic → caused breathless delivery. New version: calm, natural pacing. |

## Remaining Work
- [ ] **Production verification**: Run script on actual data (not dry-run) to confirm output quality holds
- [ ] **Monthly cost monitoring**: After 30 days, confirm actual costs match $9.70 prediction
- [ ] **TTS storage**: Currently saves to `scripts/output/briefings/YYYY-MM-DD/audio-*.wav` — consider S3/Cloud Storage for persistence
- [ ] **DB audio_url field**: Schema has `audio_url` column but script doesn't populate it yet

## Blockers / Open Questions
- **CSV cost logging**: Removed per user request (wants to eyeball notebook summary instead)
- **Supabase upsert safety**: Today's briefing can be re-run safely (upsert), but re-running yesterday's will overwrite. Consider date range protection?

## Context for Next Session

### Important Patterns
1. **Thinking budget sweet spot**: 4K is sufficient for this task. 2K might be too low (not tested).
2. **Output quality metric**: Use word count (1800-2000 target) + coverage depth (20-28 stories) as quality measure, not just thinking tokens.
3. **TTS is the cost driver**: Optimizing LLM thinking saves money but has diminishing returns. TTS optimization (cloud storage, batch processing) would have bigger impact.

### Critical File Paths
- Script: `scripts/generate_briefing.py` (main entry point)
- Notebook: `notebooks/briefing_prototype.ipynb` (sandbox for experimentation)
- Output dir: `scripts/output/briefings/YYYY-MM-DD/` (briefings, articles, audio)
- Schema: `supabase/migrations/002_briefings.sql` (wsj_briefings, wsj_briefing_items)
- DB tables: `wsj_briefings` (upsert on date,category), `wsj_briefing_items` (junction)

### Gotchas
1. **Chirp3 HD requires specific voice name**: `en-US-Chirp3-HD-Alnilam` (other variants may fail)
2. **Gemini TTS is preview-only**: May have reliability issues; no chunking API (full text single pass)
3. **Previously-briefed filter queries all past briefings**: O(N) complexity; if thousands of briefings, may slow down. Consider DB index or date range limit.
4. **Temperature inconsistency fixed**: EN was 0.7, KO was 0.6 → now both 0.6 for consistency

### Next Steps (If Continuing)
1. Run script on real data: `python scripts/generate_briefing.py`
2. Verify EN/KO audio quality (listen to samples)
3. Check Supabase upsert (briefing record should exist)
4. Collect 30 days of actual costs to validate $9.70 estimate
5. Consider TTS storage strategy (local → cloud)
