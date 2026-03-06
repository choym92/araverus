<!-- Updated: 2026-03-06 -->
# Threading & Impact Refactor: From Heuristic Matching to Portfolio Intelligence

## ⚠️ Deployment Checklist (v5.0 LLM Judge — code is merged, DB not yet)

- [ ] **Run migration**: Supabase Dashboard → SQL Editor → paste `supabase/migrations/014_llm_judge_threading.sql` → Run
- [ ] **First pipeline run**: `cd scripts && .venv/bin/python 7_embed_and_thread.py` (no flags — runs all 5 steps)
- [ ] **Spot-check judgments**: `SELECT decision, confidence, decision_reason FROM wsj_thread_judgments ORDER BY created_at DESC LIMIT 20`
- [ ] **Spot-check analysis**: `SELECT title, analysis_json->'narrative_strength', analysis_json->'impacts' FROM wsj_story_threads WHERE analysis_json IS NOT NULL LIMIT 10`

## Context

This doc emerged from a deep strategic discussion about Araverus's direction. Key conclusions:

1. **Current threading pipeline** (1,685 lines, 20+ constants) over-engineers heuristic approximations of what an LLM can judge natively — especially causal relationships.
2. **"LLM is already a knowledge graph"** is partially true for MVP but incomplete for product. LLM output lacks consistency, reproducibility, traceability, and accumulation. Impact results must be **stored and accumulated** over time — that history becomes a moat.
3. **Business direction**: Araverus should pivot from "AI news summary site" to **"portfolio-linked thread intelligence"** — showing investors which news threads are relevant to their holdings and why.
4. **Taxonomy prompts constrain output but don't validate.** A minimal exposure rule layer (not Neo4j, just a lookup table) provides the safety rail between LLM suggestions and user-facing output.

---

## Business Goal

**Target user**: Individual investors in US stocks (especially Korean investors reading English financial news)

**Core value prop**: "오늘 내 포트폴리오에 영향을 줄 뉴스가 있는가?" — answered daily, automatically, with structured reasoning.

**Not**: investment advice, buy/sell signals, price predictions
**Is**: relevance filtering, exposure mapping, narrative tracking

This refactor serves two purposes:
1. **Simplify** the threading pipeline (engineering win)
2. **Add impact analysis + portfolio relevance** (product win — the differentiator)

---

## Architecture: Before vs After

### Before (current)
```
article
  → compute embedding
  → compute time-weighted centroid for each thread
  → compute IDF-weighted entity overlap
  → check author boost (48h window)
  → compute dynamic threshold (base + time_penalty + hard_cap)
  → check margin (best - runner_up >= 0.03)
  → if pass → assign to thread
  → if fail → collect for LLM grouping
  → LLM groups unmatched → merge check (cosine > 0.92)
  → CE merge pass (cross-encoder on centroid-prefiltered pairs)
  → update thread statuses
```
**20+ constants, 1,685 lines, causal relationships missed, no portfolio relevance**

### After (target)
```
article
  → compute embedding (keep)
  → cosine similarity against active/cooling thread centroids → top 5 candidates
  → LLM judge: assign to thread or create new (causal-aware)
  → if no candidates above pre-filter → LLM batch-groups unmatched
  → merge check for new threads (keep cosine > 0.92)
  → update centroid (keep running mean)
  → update thread statuses (keep lifecycle logic)
  → [NEW] generate/update thread impacts (LLM + exposure rules validation)
  → [NEW] compute portfolio relevance per user watchlist
```
**5 constants, ~400-500 lines, causal relationships captured, portfolio relevance enabled**

---

## Part 1: Threading Simplification

### What to Keep (unchanged)

| Component | Why keep | Current location |
|-----------|----------|-----------------|
| **Embedding generation** | Pre-filtering candidates | `embed_articles()`, `embed_texts()` |
| **Thread lifecycle** (active/cooling/archived/resurrection) | Solid design | `update_thread_statuses()` |
| **Centroid storage** (running mean) | Cosine pre-filter | centroid update in `assign_threads()` |
| **Golden seed** | Bootstrapping + evaluation | `seed_from_golden()` |
| **Thread status column** | Already working | `status TEXT` in `wsj_story_threads` |
| **Heat score** (query-time) | Frontend ranking | computed in `news-service.ts` |
| **Merge threshold** (0.92) | Prevents duplicate threads | `THREAD_MERGE_THRESHOLD` |

### What to Remove

| Component | Why remove | Constants killed |
|-----------|-----------|-----------------|
| **Time-weighted centroid at match time** | LLM handles recency | `CENTROID_DECAY` |
| **IDF-weighted entity overlap** | LLM understands entities | `ENTITY_WEIGHT` |
| **Dynamic threshold** | LLM decides with full context | `THREAD_BASE_THRESHOLD`, `THREAD_TIME_PENALTY` |
| **Author boost** | LLM sees author in context | `AUTHOR_BOOST_THRESHOLD`, `AUTHOR_BOOST_WINDOW_HOURS` |
| **Margin check** | LLM handles ambiguity | `THREAD_MATCH_MARGIN` |
| **Hard cap / frozen threshold** | LLM told member count | `THREAD_HARD_CAP`, `THREAD_FROZEN_THRESHOLD` |
| **Cross-encoder merge pass** | Overkill, LLM merge detection simpler | `CE_MODEL_NAME`, `CE_CENTROID_PREFILTER`, `CE_MERGE_THRESHOLD` |

### LLM Judge: Thread Assignment

**Purpose**: Given an article + top candidates, decide thread assignment. Captures causal, thematic, and entity relationships that cosine misses.

**Input per article**:
```
Article:
  title: "Housing Market Cools as Mortgage Rates Climb"
  date: 2026-03-05
  author: "Nicole Friedman"
  summary: "Home sales fell 4.2% in February as mortgage rates stayed above 7%,
            following the Fed's decision to hold rates steady."
  keywords: [housing, mortgage, home sales, federal reserve]

Candidate Threads (top 5 by cosine similarity):
1. [abc] "Fed Holds Rates at 4.5%" (12 members, last: today)
   Recent: "Fed Signals Patience on Rate Cuts", "Markets React to Fed Hold"

2. [def] "U.S. Housing Market Slowdown" (8 members, last: 2 days ago)
   Recent: "Home Sales Drop for Third Month", "Builder Confidence Falls"

3. [ghi] "Mortgage Rate Trends 2026" (5 members, last: 5 days ago)
   Recent: "30-Year Fixed Hits 7.2%", "Refinancing Activity Drops"
```

**Prompt rules**:
- Consider causal relationships (rate decisions → housing → mortgages)
- Same event, different angles = same thread
- Downstream effect of event = same thread (if article explicitly references cause)
- Different events in same sector ≠ same thread
- Topic A's IMPACT ON Topic B → prefer Topic A thread (cause over effect)
- If no good fit → `new_thread` with title
- If ambiguous → pick stronger causal link

**Output**:
```json
{
  "action": "assign",
  "thread_id": "abc",
  "reason": "Housing impact directly caused by Fed rate decision"
}
```

**Model**: Gemini 2.5 Flash
**Cost**: ~500 tokens/article × 50 articles/day = $0.01-0.02/day

### Constants: Before vs After

**Before (20+)**:
```python
THREAD_BASE_THRESHOLD, THREAD_TIME_PENALTY, CENTROID_DECAY, ENTITY_WEIGHT,
AUTHOR_BOOST_THRESHOLD, AUTHOR_BOOST_WINDOW_HOURS, THREAD_HARD_CAP,
THREAD_FROZEN_THRESHOLD, THREAD_MATCH_MARGIN, THREAD_MERGE_THRESHOLD,
LLM_GROUP_MAX_SIZE, THREAD_COOLING_DAYS, THREAD_ARCHIVE_DAYS,
LLM_WINDOW_DAYS, CE_MODEL_NAME, CE_CENTROID_PREFILTER, CE_MERGE_THRESHOLD, ...
```

**After (5)**:
```python
CANDIDATE_THRESHOLD = 0.40       # Cosine pre-filter (low — LLM decides)
CANDIDATE_TOP_K = 5              # Max candidates sent to LLM
THREAD_MERGE_THRESHOLD = 0.92    # New thread merge check
THREAD_COOLING_DAYS = 3          # Lifecycle
THREAD_ARCHIVE_DAYS = 14         # Lifecycle
```

---

## Part 2: Thread Impact Analysis (NEW)

This is the feature that transforms Araverus from "news site" to "intelligence product."

### What it does

Each thread gets structured impact data: which commodities, sectors, macro themes, and tickers are affected, how directly, and why.

### Why LLM alone isn't enough (lesson from discussion)

LLM generates good **candidates** for impacts, but:
- **Consistency**: Same thread may get different impacts on different runs
- **Hallucination**: LLM may connect "Iran tensions" to "semiconductors" (plausible-sounding but wrong)
- **Traceability**: User asks "why is XOM here?" — need an auditable chain, not just "the AI said so"
- **Accumulation**: Stored impact history over months becomes proprietary data (moat)

### Architecture: LLM generates → Exposure rules validate → Store results

```
Thread updated (3+ new articles since last analysis)
  → LLM generates impact candidates (constrained by taxonomy)
  → Exposure rules validate direct/indirect (lookup table, not Neo4j)
  → Results stored in DB with timestamp
  → Frontend displays with confidence labels
```

### Step 1: LLM Impact Generation

**Prompt**:
```
Thread: "Iran-US Tensions Escalate"
Recent articles (last 5):
- "US Strikes Militia Base in Syria"
- "Iran Warns of Retaliation"
- "Hormuz Strait Shipping Concerns Rise"
- "Oil Futures Jump on Middle East Risk"
- "Defense Stocks Rally on Geopolitical Fear"

Identify impacts. Choose ONLY from these taxonomies:

Commodities: [crude_oil, natural_gas, gold, silver, copper, lithium, wheat, soybeans, lumber, cotton]
Sectors: [energy, shipping, airlines, defense, banking, tech, real_estate, manufacturing, retail, healthcare, insurance, automotive]
Macro themes: [inflation, interest_rates, employment, trade, geopolitics, supply_chain, consumer_spending, currency]

For each:
- confidence: direct | indirect | speculative
- direction: positive | negative | volatile | neutral
- reason: one sentence explaining the link
```

**Output**:
```json
{
  "impacts": [
    {"type": "commodity", "name": "crude_oil", "confidence": "direct", "direction": "positive", "reason": "Hormuz strait disruption threatens oil supply"},
    {"type": "sector", "name": "shipping", "confidence": "direct", "direction": "negative", "reason": "Maritime disruption risk in Persian Gulf"},
    {"type": "sector", "name": "defense", "confidence": "direct", "direction": "positive", "reason": "Military escalation drives defense demand narrative"},
    {"type": "sector", "name": "airlines", "confidence": "indirect", "direction": "negative", "reason": "Oil price increase pressures fuel costs"},
    {"type": "sector", "name": "insurance", "confidence": "indirect", "direction": "negative", "reason": "Shipping insurance premiums rise on conflict risk"},
    {"type": "macro", "name": "geopolitics", "confidence": "direct", "direction": "volatile", "reason": "Major power confrontation in Middle East"}
  ]
}
```

### Step 2: Exposure Rules Validation (minimal, not Neo4j)

A simple lookup table — start with ~50-100 rules, expand as needed:

```python
# exposure_rules.py — simple dict, not a database
EXPOSURE_RULES = {
    # event_theme → [(target, relationship, default_direction)]
    "hormuz_disruption": [
        ("crude_oil", "direct", "positive"),
        ("shipping", "direct", "negative"),
        ("airlines", "indirect", "negative"),
    ],
    "oil_price_increase": [
        ("energy", "direct", "positive"),
        ("airlines", "direct", "negative"),
        ("shipping", "indirect", "volatile"),
    ],
    "interest_rate_hold": [
        ("banking", "direct", "volatile"),
        ("real_estate", "direct", "negative"),
    ],
    "geopolitical_conflict": [
        ("defense", "direct", "positive"),
        ("gold", "indirect", "positive"),
    ],
    # ... ~50-100 rules total to start
}
```

**What this does**:
- LLM says "airlines affected" → check: is there a rule connecting this thread's theme to airlines? If yes → keep, label confidence. If no rule exists → label as "speculative" (don't remove, just lower confidence).
- This is NOT blocking — LLM output still shows. The rules add confidence calibration.

**Why this isn't over-engineering**:
- It's a Python dict, not a graph database
- 50 rules cover the major financial relationships
- Takes 1-2 hours to write manually
- Can be LLM-assisted ("generate exposure rules for oil supply disruption")
- Grows organically as you see LLM errors

### Step 3: Store Results

```sql
ALTER TABLE wsj_story_threads
  ADD COLUMN impacts JSONB DEFAULT NULL,
  ADD COLUMN impacts_updated_at TIMESTAMPTZ DEFAULT NULL,
  ADD COLUMN impact_article_count INT DEFAULT 0;  -- member_count at last analysis
```

**Trigger**: When `member_count - impact_article_count >= 3` (3+ new articles since last analysis)

### Step 4: Ticker Mapping (for portfolio relevance)

LLM should NOT generate specific tickers — too much hallucination risk.

Instead, maintain a sector-to-ticker mapping table:

```python
# ticker_sectors.py — or DB table
SECTOR_TICKERS = {
    "energy": ["XOM", "CVX", "COP", "SLB"],
    "defense": ["LMT", "RTX", "NOC", "GD"],
    "airlines": ["DAL", "UAL", "LUV", "AAL"],
    "shipping": ["ZIM", "GOGL", "INSW"],
    "banking": ["JPM", "BAC", "GS", "MS"],
    "tech": ["AAPL", "MSFT", "NVDA", "GOOG"],
    # ...
}
```

When a thread impacts "airlines (direct, negative)" → system maps to DAL, UAL, etc.
User's portfolio contains DAL → thread shows as portfolio-relevant.

**Important**: The system says "this thread is relevant to your airline holdings" — NOT "sell DAL." This is relevance, not advice. Key for regulatory safety.

---

## Part 3: Portfolio Relevance (Future — after Part 1+2 ship)

### How it works

```
User watchlist: [NVDA, XOM, DAL, JPM]
  → Map tickers to sectors: tech, energy, airlines, banking
  → Find threads with impacts matching those sectors
  → Rank by: direct > indirect > speculative, recency, heat score
  → Display: "Today's news relevant to your portfolio"
```

### User experience

```
Your Portfolio Intelligence — March 6

XOM (Energy)
  Iran-US Tensions → crude oil ↑ risk (direct)
  "Hormuz strait disruption threatens oil supply"

DAL (Airlines)
  Iran-US Tensions → airlines ↓ risk (indirect)
  "Oil price increase pressures fuel costs"

NVDA (Tech)
  AI Chip Export Controls → tech volatile (direct)
  "New restrictions on advanced chip exports discussed"

JPM (Banking)
  No significant thread activity today.
```

### DB for portfolio

```sql
CREATE TABLE user_watchlist (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users(id),
  ticker TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(user_id, ticker)
);
```

---

## Migration Strategy

### Phase 1: LLM Judge — replace matching core (Week 1)
1. Create `match_article_llm()` — cosine pre-filter → LLM judge
2. Keep `match_to_threads()` as fallback (`--legacy` flag)
3. Run both on 1 day's articles, compare results
4. Validate against golden dataset v2.1 (target: ≥ 88% + better causal capture)
5. If good → switch, delete old code + constants

### Phase 2: Impact Analysis — new feature (Week 2)
1. Add `impacts` columns to `wsj_story_threads`
2. Write `exposure_rules.py` (~50 rules)
3. Write `analyze_thread_impacts()` — LLM generate + rules validate
4. Backfill impacts for active/cooling threads
5. Frontend: "Related Impacts" section on thread page

### Phase 3: Portfolio Relevance — the differentiator (Week 3-4)
1. `user_watchlist` table + simple UI for ticker input
2. `ticker_sectors.py` mapping
3. Portfolio relevance matching (thread impacts ↔ user sectors)
4. "Your Portfolio Intelligence" dashboard section
5. Update site copy/positioning to reflect portfolio focus

### Phase 4: Cleanup & Polish (Week 4-5)
1. Remove cross-encoder code + model dependency
2. Update `docs/1.3-news-threading.md`
3. Update site messaging: "Track the stories moving your portfolio"
4. Add causal test cases to golden dataset evaluation

---

## Evaluation Plan

### Golden dataset A/B (Phase 1)
- Current heuristic pipeline → measure accuracy
- New LLM-judge pipeline → measure accuracy on same articles
- Target: ≥ 88% thread match + qualitatively better causal grouping

### Causal relationship test cases (new, add to evaluation)
| Article | Should join thread | Why (causal) |
|---------|-------------------|-------------|
| "Housing Sales Fall 4%" | "Fed Rate Decision" | Rate → mortgage → housing |
| "Airline Stocks Drop" | "Oil Price Surge" | Oil → fuel cost → airlines |
| "Chile Mining Revenue Up" | "China EV Subsidies" | EV → batteries → lithium → Chile |
| "Shipping Insurance Costs Rise" | "Iran-US Tensions" | Tension → Hormuz → shipping |

These fail cosine matching but should pass LLM judgment.

### Impact quality (Phase 2)
- Manual review of first 20 thread impact analyses
- Check: false connections, missing obvious connections, confidence calibration
- Compare LLM-only vs LLM+rules output

---

## Cost Estimate

| Component | Daily volume | Cost/day |
|-----------|-------------|----------|
| LLM judge (per article) | 50 articles x ~500 tok | $0.01 |
| LLM grouping (unmatched batch) | 1 batch x ~2K tok | $0.005 |
| Impact analysis (per thread update) | ~10 threads x ~800 tok | $0.008 |
| **Total** | | **~$0.02/day (~$0.70/month)** |

Embedding compute: local model, free. Exposure rules: Python dict, free.

---

## Files Affected

| File | Change | Phase |
|------|--------|-------|
| `scripts/7_embed_and_thread.py` | Major refactor: 1,685 → ~500 lines | 1 |
| `scripts/exposure_rules.py` | New: ~50-100 sector/commodity rules | 2 |
| `scripts/ticker_sectors.py` | New: sector → ticker mapping | 3 |
| `supabase/migrations/` | New: `impacts` columns, `user_watchlist` table | 2, 3 |
| `docs/1.3-news-threading.md` | Rewrite for new architecture | 4 |
| `docs/schema.md` | Add new columns/tables | 2, 3 |
| `src/lib/news-service.ts` | Fetch impacts, portfolio relevance | 2, 3 |
| `src/app/news/components/` | Impact display, portfolio section | 2, 3 |

---

## Dependencies

### Remove
- `sentence_transformers.CrossEncoder`
- `Alibaba-NLP/gte-reranker-modernbert-base` model

### Keep
- `sentence_transformers.SentenceTransformer` + `BAAI/bge-base-en-v1.5`
- `numpy`
- Gemini API

### Add
- Nothing new (Gemini API already a dependency)

---

## Open Questions

1. **Pre-filter threshold (0.40)**: Intentionally low so LLM sees diverse candidates. Need to test — too low = noise, too high = misses causal links.
2. **Gemini Flash vs Pro**: Start Flash ($0.01/day). Upgrade if judge quality is insufficient.
3. **Per-article vs batch LLM calls**: Per-article = simpler, better context. Start there, batch later if cost matters.
4. **Exposure rules maintenance**: Start manual (~50 rules). Later, LLM can suggest new rules from recurring patterns — human approves.
5. **Portfolio feature scope**: Start with ticker input only (no auth required for MVP — localStorage). Add accounts later if PMF is found.
6. **Regulatory framing**: All copy must say "relevance" not "recommendation." "This thread relates to your energy holdings" not "buy XOM." Review with SEC publisher's exclusion criteria before launch.
7. **Customer validation**: Before building Phase 3 (portfolio), talk to 5-10 target users (Korean investors in US stocks). Confirm the pain point and willingness to use/pay. Don't build blind.

---

## Strategic Notes (from discussion)

- **LLM as knowledge graph**: True for generation, false for product trust. Store everything — impact history over months becomes proprietary data that no chatbot session has.
- **Taxonomy is not validation**: Enum constrains vocabulary; exposure rules validate logic. Both are needed, but rules can start as a 50-line Python dict.
- **GDELT/existing data ≠ no opportunity**: Raw event databases exist, but "which threads matter to MY portfolio" is a product layer no one has built well for retail investors.
- **Biggest risk**: Building features no one asked for. Validate with real users before Phase 3.
- **Biggest upside**: If portfolio-linked thread intelligence resonates, this becomes "Finviz + narrative intelligence" — a defensible niche product.
