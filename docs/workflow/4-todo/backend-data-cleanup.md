<!-- Updated: 2026-02-18 -->
# Backend TODO: WSJ Data Cleanup & Pipeline Review

Findings from `/audit-data wsj_` (2026-02-17) + Stage-by-stage pipeline review (2026-02-18).

---

## Stage 1: RSS Ingest (`wsj_ingest.py`)

### 1.1 ~~Doc inconsistencies~~ — RESOLVED
Line counts, LLM model names (GPT-4o-mini → Gemini 2.5 Flash), env vars all corrected in `docs/4-news-backend.md`.

### 1.2 ~~28% NULL subcategory~~ — RESOLVED
- Added `personal-finance`, `science` to `URL_CATEGORY_MAP`
- Added subcategory fallback: `feed_name.lower()` when URL has no subcategory
- Ran `backfill_subcategory.py`: 435 items backfilled → **0 NULL remaining**

### 1.3 ~~Junk content leaking past SKIP_CATEGORIES~~ — RESOLVED
- Added `/buyside/`, `/sports/`, `/opinion/` to `SKIP_CATEGORIES`
- Ran `backfill_subcategory.py`: **36 junk items deleted** (buyside, lifestyle, arts-culture, etc.)

### 1.4 Title dedup — exact match only
`dedup_by_title()` uses exact `item.title` string match. Near-duplicates with minor wording differences (e.g., "Fed Holds Rates" vs "Fed Holds Rates Steady") slip through.

**Impact**: Low — RSS cross-posts usually have identical titles. But edge cases exist.
**Action**: Consider fuzzy matching (e.g., normalized title comparison) if duplicates become noticeable.

### 1.5 ~~`BUSINESS` vs `BUSINESS_MARKETS` feed_name inconsistency~~ — NOT AN ISSUE
URL_CATEGORY_MAP overrides RSS feed_name for all BUSINESS/MARKETS articles. DB only contains `BUSINESS_MARKETS` — no inconsistency.

### 1.6 ~~Stale article detection~~ — NOT AN ISSUE
10 items from Dec 2025 ingested on first pipeline run (2026-01-20). One-time occurrence — no stale articles since. Old buyside content already cleaned by 1.3. Adding a date filter would risk dropping valid articles after pipeline downtime.

---

## Stage 1 — Earlier Audit Findings

### 1.7 ~~Block `finance.yahoo.com`~~ — RESOLVED
Wilson Score auto-blocking handles this. `wilson=0.12 < 0.15` → auto-blocked.

### 1.8 ~~Block `livemint.com`~~ — RESOLVED
Wilson Score auto-blocking handles this. `wilson=0.06 < 0.15` → auto-blocked.

### 1.9 ~~Clean stale pending crawls~~ — RESOLVED
Deleted 2 stale pending crawls (>7 days, "Roundup: Market Talk" articles).

### 1.10 ~~391 successful crawls missing LLM analysis~~ — RESOLVED
359 of 360 were `relevance_flag='low'` — intentionally skipped (embedding score < 0.25, LLM analysis unnecessary). Remaining 5 `flag='ok'` items backfilled successfully.

### 1.11 ~~103 items with >5 crawl results each~~ — NOT AN ISSUE
100 items have 6-10 crawl results (from multiple pipeline runs). Max is 10. `crawl_ranked.py` uses first success and marks rest as `skipped`. No real waste — minor storage only.

### 1.12 629 unprocessed items (39%)
Normal backlog. Monitor — if it grows, pipeline throughput needs tuning.

### 1.13 ~~NULL subcategory~~ — RESOLVED (same as 1.2)

---

## Stages 2-9: Pending Review

| Stage | Script | Status |
|-------|--------|--------|
| 2 | `wsj_to_google_news.py` | TODO |
| 3 | `embedding_rank.py` | TODO |
| 4 | `resolve_ranked.py` | TODO |
| 5 | `crawl_ranked.py` + `crawl_article.py` | TODO |
| 6 | `llm_analysis.py` | TODO |
| 7 | Post-process (`--mark-processed-from-db`, `--update-domain-status`) | TODO |
| 8 | `embed_and_thread.py` | TODO |
| 9 | `generate_briefing.py` | TODO |

---

## Data Health Summary

| Check | Status |
|-------|--------|
| Orphan rows (broken FKs) | Clean (0) |
| Duplicate items (`url_hash`) | Clean (0) |
| Duplicate crawl results | Clean (0) |
| Duplicate LLM analyses | Clean (0) |
| Blocked domains | Auto-managed by Wilson Score |
| NULL subcategory | **0 remaining** (was 28%) |
| Junk content | **36 deleted**, filters updated |


Stage: 2                                                 
  Script: wsj_to_google_news.py (1078 lines)           
  내용: Google News 검색 — 4 queries/item, dual-phase, date
                                                       
    filtering
  ────────────────────────────────────────
  Stage: 3
  Script: embedding_rank.py (232 lines)
  내용: 후보 기사 semantic ranking — all-MiniLM-L6-v2
  ────────────────────────────────────────
  Stage: 4
  Script: resolve_ranked.py (304 lines)
  내용: Google News redirect URL → 실제 URL 해석
  ────────────────────────────────────────
  Stage: 5
  Script: crawl_ranked.py (597 lines) + crawl_article.py
    (1394 lines)
  내용: 크롤링 + 품질 검증
  ────────────────────────────────────────
  Stage: 6
  Script: llm_analysis.py (280 lines)
  내용: Gemini 2.5 Flash 검증 + 메타데이터 추출
  ────────────────────────────────────────
  Stage: 7
  Script: Post-process (--mark-processed-from-db,
    --update-domain-status)
  내용: 후처리 + 도메인 통계
  ────────────────────────────────────────
  Stage: 8
  Script: embed_and_thread.py
  내용: 기사 임베딩 + 스토리 스레드 매칭
  ────────────────────────────────────────
  Stage: 9
  Script: generate_briefing.py
  내용: EN/KO 브리핑 생성 + TTS

  8개 스테이지 남았습니다. 계속 진행할까요, 아니면 여기서
  커밋하고 다음 세션에서 이어갈까요? 컨텍스트가 꽤
  쌓여있어서 /handoff도 고려할 만합니다.