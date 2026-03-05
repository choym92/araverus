<!-- Updated: 2026-03-05 -->
# Threading v4.7/4.8 Implementation — COMPLETE

## Status: ✅ All Done (2026-03-05)

## What Was Done

### 1. Timing logs ✅ (already existed from v4.6)
`[TIMING]` logs were already in `main()` for each step.

### 2. Cosine params ✅ (already applied in v4.6)
```
THREAD_BASE_THRESHOLD:    0.73 → 0.60
AUTHOR_BOOST_THRESHOLD:   0.60 → 0.55
THREAD_TIME_PENALTY:      0.01 → 0.005
```

### 3. Golden seed ✅ (new — v4.8)
- Added `seed_from_golden()` function + `--seed-golden PATH` CLI arg
- Resets all thread assignments, creates threads from golden dataset with computed centroids
- Seeded DB with golden v2.1: 170 threads, 612 articles

### 4. CE merge pass ✅ (new — v4.8)
- Added `merge_similar_threads_ce()` — centroid prefilter → CE scoring → pair merge
- No union-find — direct pair merges, highest CE first, skip absorbed
- CE threshold tuned via production testing:
  - 0.60: 129 merges, heavy contamination (unrelated threads merged)
  - 0.75: 84 merges, still contaminated
  - 0.80: 51 merges, borderline cases
  - **0.85: 10 merges, clean** ← chosen
- Model: `Alibaba-NLP/gte-reranker-modernbert-base`, MPS/CPU auto

### 5. Production run verified ✅
| Step | Time | Result |
|------|------|--------|
| Embed | 6s | 0 (already done) |
| Cosine match | 120s | 252 matched, 3 new threads, 2 LLM merges |
| Status update | 16s | 68 cooling, 74 archived |
| CE merge | 60s | 10 merges from 2,127 candidates |
| **Total** | **~3.4 min** | **163 threads, 882 threaded articles** |

## Key Decisions
- **Golden seed over backfill**: Chronological backfill from 0 threads caused mega-threads (snowball at 0.60 threshold). Golden seed provides well-formed starting threads.
- **CE threshold 0.85**: Notebook research suggested 0.60 but production testing showed heavy contamination. 0.85 yields clean merges only.
- **No union-find**: Direct pair merges avoid transitive contamination chains.
