<!-- Created: 2026-02-19 -->
# Plan: Embedding Model & Cross-Encoder A/B Test Notebook

## Context

WSJ 뉴스 파이프라인에서 크롤된 기사의 ~35%가 "wrong event" (같은 주제, 다른 이벤트). 현재 `all-MiniLM-L6-v2` (384d)로 임베딩 필터링 중. 더 좋은 임베딩 모델 + cross-encoder(리랭커) 도입으로 두 가지 핵심 단계의 정확도를 높이고 Gemini 호출을 줄일 수 있는지 실제 DB 데이터로 A/B 테스트.

**두 가지 동등한 목표:**
1. **Pre-crawl 랭킹** (WSJ title+desc vs Google News RSS title) — Top K URL 선택 정확도 향상 → 콘텐츠 확보율 증가
2. **Post-crawl 검증** (WSJ title+desc vs 크롤 콘텐츠) — thread 생성, 관련 기사 매칭, 향후 임베딩 기반 프로젝트에 활용

**Ground truth**: `wsj_llm_analysis.is_same_event` + `relevance_score >= 6` (Gemini 레이블, ~2,326개 쌍)

**SNS 차단은 유저가 직접 완료함** — 이 플랜에 포함 안 됨.

---

## Files

| Action | File | Purpose |
|--------|------|---------|
| **CREATE** | `notebooks/embedding_ab_test.ipynb` | A/B 테스트 노트북 |
| Reference | `scripts/crawl_ranked.py` | 현재 임베딩 로직 (RELEVANCE_CHARS=800, RELEVANCE_THRESHOLD=0.25) |
| Reference | `scripts/embedding_rank.py` | 현재 pre-crawl 랭킹 (min_score=0.3, top_k=5) |
| Reference | `scripts/embed_and_thread.py` | bge-base-en-v1.5 사용 패턴, threshold 0.62/0.03 |
| Reference | `scripts/llm_analysis.py` | Ground truth 레이블 생성 로직 |

---

## Notebook Cell Plan (18 cells)

### Setup (Cells 1-3)
1. **Imports + Supabase 연결** — dotenv, sentence-transformers, sklearn, matplotlib, seaborn
2. **DB에서 레이블된 데이터 풀** — 3 테이블 페이지네이션으로 로드:
   - `wsj_crawl_results` (crawl_status='success'): id, wsj_item_id, wsj_title, title, content, embedding_score
   - `wsj_items`: id, title, description
   - `wsj_llm_analysis`: crawl_result_id, is_same_event, relevance_score
3. **DataFrame 머지 + 텍스트 페어 준비**:
   - `wsj_text` = title + description (query)
   - `crawled_text_800` = content[:800] (post-crawl, `RELEVANCE_CHARS` 기준)
   - `google_title` = wsj_crawl_results.title (pre-crawl)
   - `label` = is_same_event OR relevance_score >= 6 (파이프라인 accept 로직과 동일)

### Baseline (Cell 4)
4. **DB에 저장된 기존 embedding_score 분포 확인** — label별 통계

### Helper Functions (Cell 5)
5. **`evaluate_model_scores()`** — threshold 순회하며 P/R/F1/AUC 계산, 최적 threshold 반환
   **`three_zone_analysis()`** — accept/reject/uncertain 3구간 분석

### Bi-Encoder Tests (Cells 6-8)
6. **all-MiniLM-L6-v2 (baseline)** — wsj_text vs crawled_text_800, cosine similarity
7. **bge-large-en-v1.5** — query에 `"Represent this sentence for searching relevant passages: "` prefix 필요, doc에는 불필요
8. **Qwen3-Embedding-0.6B** — `trust_remote_code=True`, `prompt_name="query"` 시도, 실패 시 fallback. try/except로 감싸서 graceful degradation

### Cross-Encoder Tests (Cells 9-10)
9. **cross-encoder/ms-marco-MiniLM-L-12-v2** — `CrossEncoder` 클래스, `predict(pairs)`, sigmoid 정규화 필요 (raw logits 출력)
10. **Qwen3-Reranker-0.6B (optional)** — try/except, 실패 시 스킵

### Comparison & Visualization (Cells 11-15)
11. **비교 테이블** — model, optimal_threshold, F1, AUC, precision, recall
12. **Score Distribution 히스토그램** — 2x2 grid, same_event(파란색) vs wrong_event(빨간색) 겹쳐 그리기. **분포 분리가 클수록 좋은 모델**
13. **ROC 커브 오버레이** — 모든 모델 한 그래프에
14. **3-Zone Gate 분석** — 각 모델에서 95% 정확도 기준으로:
    - Accept zone: precision >= 95% → Gemini 스킵
    - Reject zone: reject accuracy >= 95% → Gemini 스킵
    - Uncertain zone: Gemini 필요
    - `gemini_savings_pct` = 1 - uncertain_pct
15. **비용 분석** — 일일 크롤 수 × Gemini 단가 × 절감률

### Pre-Crawl Ranking Test (Cell 16)
16. **Pre-crawl: WSJ text vs Google News title** — embedding_rank.py 사용 사례. 모든 bi-encoder + cross-encoder로 테스트

### Final (Cells 17-18)
17. **F1 vs Threshold 커브** — post-crawl / pre-crawl 나란히
18. **Summary & 다음 단계** — 결과 기반 추천

---

## Data Limitations

DB에 저장된 데이터의 한계를 인식하고 해석할 것:

### Selection Bias (Pre-Crawl)
- `wsj_crawl_results`에는 현재 MiniLM 모델이 선택한 top_k(~5개)만 존재. 원래 Google News 후보 20-50개 중 나머지는 DB에 없음
- **MiniLM이 top_k를 선택했으므로, 데이터 분포가 MiniLM에 유리하게 편향될 수 있음** — MiniLM이 A/B에서 과하게 좋아 보일 가능성
- Hard negatives (이벤트는 다르지만 토픽이 매우 유사한 후보)가 MiniLM의 min_score=0.3 이하로 걸러져 데이터에 없을 수 있음
- 도메인 필터(SNS block 등) 이후 운영 분포는 실험 데이터와 다를 수 있음

### Label Coverage
- 크롤 성공(~2,326개)만 라벨 있음. 크롤 실패/스킵(~4,402개)은 content 없어서 LLM 라벨 없음

### 측정 가능 vs 불가능
- **불가능**: Recall@K, MRR, NDCG (전체 후보 풀 필요)
- **가능 (신뢰도 높음)**: Post-crawl 3-zone gate 분석 (라벨이 이 단계에 직접 대응)
- **가능 (참고 수준)**: Pre-crawl score 분리도 비교 (선택된 후보 집합 내에서만 유효)

### 노트북에 명시할 3개 문장
1. "This dataset contains only candidates already selected by the current pre-crawl ranker (top_k). Results may not generalize to the full candidate distribution."
2. "Therefore, we do not claim Recall@K/MRR improvements; we only compare score separation and gate savings on the observed candidate set."
3. "To validate pre-crawl improvements, we need to log/store the full candidate list per WSJ item (N=20–50) for a future evaluation run."

### 금지되는 결론
- "이 모델이 Recall@K를 X% 올린다"
- "전체 후보에서도 무조건 더 잘한다"
- "이 수치대로 운영 바꾸면 성공률이 그대로 오른다"

→ 노트북 Cell 18 (Summary)에 위 한계를 명시 + 전체 후보 로깅 계획 포함

## Key Technical Notes

- **bge-large instruction prefix**: query 텍스트에만 적용, document에는 안 붙임
- **Qwen3 모델**: `trust_remote_code=True` 필수, prompt format 확인 필요 (모델카드 참조)
- **Cross-encoder 출력**: raw logits → `scipy.special.expit()` 으로 [0,1] 정규화
- **Label 정의**: `crawl_ranked.py` 449행의 accept 로직과 동일 (`is_same_event=true OR llm_score >= 6`)
- **800자 truncation**: `crawl_ranked.py` 37행 `RELEVANCE_CHARS = 800`과 동일
- **Read-only**: DB 쓰기 없음, 파이프라인 스크립트 수정 없음

## Dependencies

```
pip install pandas scikit-learn matplotlib seaborn scipy
# sentence-transformers, supabase-py는 이미 설치됨
```

## Verification

1. 노트북 전체 셀 실행 (Cell 1→18 순서)
2. Cell 11 비교 테이블에서 AUC/F1 수치 확인
3. Cell 12 히스토그램에서 분포 분리 정도 시각적 확인
4. Cell 14 3-zone 분석에서 Gemini 절감률 확인
5. 결과 기반으로 다음 세션에서 파이프라인 모델 교체 결정
