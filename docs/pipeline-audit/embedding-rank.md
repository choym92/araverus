<!-- Created: 2026-02-22 -->
# Audit: 4_embedding_rank.py

Phase 2 · Step 1 · Embedding Rank — 207 LOC (post-refactor)

---

## Why This Script Exists

Google News returns 80-180 candidates per WSJ item, but most are irrelevant. This script uses semantic similarity (BAAI/bge-base-en-v1.5) to rank candidates and keep only the top 10 with cosine similarity >= 0.3.

Without this script, the crawler would waste time on irrelevant articles.

**Cost:** Free (local model inference). Runtime: ~15 seconds for 60 WSJ items.

---

## CLI Commands (1)

| Command | Pipeline Phase | What It Does |
|---------|---------------|--------------|
| *(default)* | Phase 2 · Step 1 | Read candidates JSONL → embed + rank → write ranked JSONL |

| Flag | Default | Action |
|------|---------|--------|
| `--top-k N` | 10 | Max results per WSJ item |
| `--min-score F` | 0.3 | Minimum cosine similarity threshold |

**Pipeline call** (`run_pipeline.sh` L60):
```bash
$VENV "$SCRIPTS/4_embedding_rank.py" || { echo "ERROR: Embedding rank failed"; exit 1; }
```

Fatal — if ranking fails, pipeline stops (no point crawling unranked candidates).

---

## Functions (3)

### `_get_model()` (L21) `[KEEP]`

Lazy singleton for sentence-transformer model. Loads on first call (~3-5 sec), returns cached instance on subsequent calls. Avoids loading on `--help` or when imported as a library.

### `normalize_title(title)` (L32) `[KEEP]`

Strips " - Publisher Name" suffixes from article titles before embedding. This prevents publisher names from inflating similarity scores between unrelated articles from the same outlet.

### `rank_candidates(query_text, candidates, top_k, min_score)` (L37) `[KEEP]`

Core function:
1. Encode WSJ title+description as query vector
2. Encode all candidate `"{title} {source}"` strings in one batch
3. Cosine similarity via dot product (normalized embeddings)
4. Filter by min_score, return top_k

**External caller**: `ab_test_pipeline.py` imports this function directly.

---

## Data Flow

```
wsj_google_news_results.jsonl (from 3_wsj_to_google_news.py)
    │ 80-180 candidates per WSJ item
    ▼ rank_candidates() × N
[top 10, score >= 0.3]
    │
    ▼ write output
wsj_ranked_results.jsonl → 5_resolve_ranked.py
wsj_ranked_results.txt   → manual inspection
```

---

## Shared Dependencies

| Module | What's Used | Why |
|--------|-------------|-----|
| `sentence_transformers` | `SentenceTransformer` | BAAI/bge-base-en-v1.5 model (768-dim embeddings) |
| `numpy` | `np.dot` | Fast cosine similarity (dot product of normalized vectors) |

No DB dependencies — pure JSONL-to-JSONL transformation.

---

## Refactoring Notes

### Done (this session)
- Module-level `MODEL = SentenceTransformer(...)` → lazy `_get_model()` singleton
- Manual `sys.argv` parsing → `argparse`
- Removed `crawl_status: 'pending'` from output (5_resolve_ranked.py sets this independently)
- Added Step number (Phase 2 · Step 1)

### Not Changed
| Pattern | Why Kept |
|---------|----------|
| Hardcoded input path | Pipeline always uses same path; `--input` flag not needed |
| `f"{title} {source}"` for candidate text | Including source improves similarity accuracy |
| TXT debug output | Small, useful for manual inspection |
