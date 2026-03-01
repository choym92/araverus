  1. General topic centroid이 목적에 충분한가?     
   
  목표가 카테고리별 3-4개 주요 스토리 식별이라면 — 
  네, 충분합니다. "Amazon AI" centroid가 "general
  Amazon"으로 수렴해도, 유저 입장에서 "Amazon이 AI
  관련해서 뭔가 하고 있구나"를 파악하는 데는 문제
  없습니다. Centroid drift가 문제가 되는 건 "Amazon
   AI chip" vs "Amazon AI agent"를 구분해야 할
  때인데, 지금 목표에서는 둘 다 같은 thread여도
  괜찮습니다.

  2. 14일 archive가 garbage thread를 처리하는가?

  부분적으로요. 두 가지 시나리오:

  - Garbage thread + 기사 안 들어옴 → 14일 후 자동
  archive. 문제 해결.
  - Garbage thread + centroid가 너무 넓어서 계속
  기사 흡수 → archive 안 됨. 이게 anti-gravity가
  방지하려는 건데, 초기 2-3개 기사가 서로 다른
  토픽이면 centroid가 "뭐든 매칭되는" 위치에 놓일
  수 있습니다.

  현실적으로 LLM grouping의 cross-validation (0.60
  threshold)이 이걸 상당히 잡아줍니다. 서로 다른
  토픽 기사들은 pairwise similarity가 낮아서 group
  생성 자체가 reject됩니다.

  3. Many-to-many 가능한가?

  가능합니다. 현재 wsj_items.thread_id (1:1 FK)
  대신 junction table을 만들면 됩니다:

  wsj_item_threads (wsj_item_id, thread_id,
  similarity_score)

  다만 프론트엔드 복잡도가 크게 올라갑니다 — 카드에
   thread carousel이 여러 개? 어떤 thread를 대표로
  보여줄지? 지금 목표(카테고리별 3-4개 주요
  스토리)에서는 1:1로 충분하고, many-to-many는
  나중에 "Stories" 탭에서 cross-story 관계를 보여줄
   때 의미가 있습니다. 지금은
  over-engineering이라고 봅니다.

  4. 더 논의할 사항

  - Thread 품질 모니터링: 지금 thread가 실제로
  어떤지 정기적으로 보고 계신가요?
  pipeline_health.py에 thread 품질 metrics (평균
  pairwise similarity, 멤버 수 분포 등)를 추가하면
  좋겠습니다.
  - Thread 제목 품질: Gemini가 생성하는 제목이
  유저가 보기에 충분히 좋은지. 이게 "무슨 일이
  일어나고 있는지" 전달하는 핵심입니다.
  - 카테고리별 thread 노출 전략: 지금은 heat
  score로 전체 정렬인데, "Markets에서 top 3,
  Tech에서 top 3"을 보장하는 로직이 없습니다.

  5. Mean embedding의 실제 의미

  직관적으로 설명하면:

  3개 기사의 embedding이 768차원 공간에서 각각
  "점"이라고 하면, np.mean은 그 무게중심입니다.
  삼각형의 세 꼭짓점의 무게중심처럼요.

     A (Amazon AI chips)
      \
       * ← centroid (여기)
      / \
     B    C
  (Amazon  (Amazon
   AI race) AI agents)

  / np.linalg.norm()은 이 점을 단위 구 표면으로
  투영합니다. Cosine similarity는 방향만
  비교하므로, 벡터 크기를 1로 맞춰야 공정한 비교가
  됩니다.

  한계: 만약 A가 "Amazon AI", B가 "Tesla AI"이면
  centroid는 "AI industry general" 어딘가에 놓이고,
   실제로는 Amazon도 Tesla도 아닌 지점을 대표하게
  됩니다. 하지만 이건 LLM cross-validation이
  방지합니다 — A와 B의 pairwise similarity가 낮으면
   group 자체가 reject되니까요.

  결론: 목표(카테고리별 주요 스토리 식별)에는 현재
  시스템이 충분합니다. 가장 투자 대비 효과가 큰 건
  thread 품질 모니터링과 카테고리별 노출 전략이라고
   봅니다.

---

<!-- Updated: 2026-02-27 -->
## Current State Assessment

Topical threading is working. Articles about the same developing story get grouped:
```
Feb 25 — Oil Rises As U.S.-Iran Tensions Keep Risk Premium Elevated
Feb 27 — Oil Rises With Focus on U.S.-Iran Talks, OPEC+ Meeting
Feb 27 — OPEC+ Expected to Resume Output Hikes at Sunday Meeting
```

This covers the "what's happening with topic X" use case well.

### Current Goal

**Category-level story identification**: 3-4 major threads per news category (Markets, Tech, Economy, etc.) so users can quickly see what's going on in the world.

For this goal, topical threading with mean centroid is sufficient.

---

## Known Limitations

### 1. Cannot do causal threading

Current system groups articles by **topical similarity** (same words/entities). It cannot link:
```
"Fed Cuts Interest Rates" → "S&P 500 Surges 3%" → "Housing Market Heats Up"
```

These are different topics with different embeddings (cosine ~0.55-0.65, below the 0.73 threshold). The embedding model (bge-base-en-v1.5) measures semantic similarity, not causation.

### 2. Mean centroid drifts to "nothing"

When diverse articles join a thread, centroid averages to a point that represents none of them well. Mitigated by anti-gravity and EMA.

### 3. 1:1 FK constraint

`wsj_items.thread_id` means one article belongs to one thread. "Fed cuts rates" can't be in both "Fed Policy" and "Stock Market" threads.

### 4. Only title + description embedded

Full article body often contains explicit causal language ("The rate cut led to...") but isn't used for threading.

---

## Future: Causal Thread Links (Option B)

**Keep current topical threading as-is. Add a separate causal relationship layer on top.**

### Concept

```
Topical threads (existing, unchanged):
  [Fed Rate Policy]  ●●●●
  [Stock Market]     ●●●
  [Housing Market]   ●●

Causal links (new layer):
  [Fed Rate Policy] --causes→ [Stock Market]
  [Fed Rate Policy] --causes→ [Housing Market]
  [Stock Market]    --causes→ [Housing Market]
```

### Schema

```sql
CREATE TABLE wsj_thread_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_thread_id UUID NOT NULL REFERENCES wsj_story_threads(id),
    target_thread_id UUID NOT NULL REFERENCES wsj_story_threads(id),
    relationship TEXT NOT NULL,        -- 'causes', 'reacts_to', 'escalates'
    confidence FLOAT,                  -- LLM confidence score
    evidence_summary TEXT,             -- LLM reasoning ("Fed rate cut drove equity rally")
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(source_thread_id, target_thread_id)
);
```

### Detection Pipeline

After daily threading completes:
1. Collect active threads with their titles + recent article titles
2. Send to Gemini: "Which of these threads have causal relationships?"
3. Store detected links in `wsj_thread_links`
4. No embedding validation needed — purely LLM judgment about causation

### Frontend: "Related Storylines"

On article detail page, below the Story Timeline:
```
┌─ Related Storylines ──────────────────────────────┐
│  This story is connected to:                        │
│                                                     │
│  📈 S&P 500 Rally (3 articles)                      │
│     "Fed rate cut drove market optimism"            │
│                                                     │
│  🏠 Housing Market Surge (2 articles)               │
│     "Lower rates boosted mortgage demand"           │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### Many-to-Many (Optional Enhancement)

If causal links exist, articles could be associated with multiple threads:
```sql
CREATE TABLE wsj_item_threads (
    wsj_item_id UUID REFERENCES wsj_items(id),
    thread_id UUID REFERENCES wsj_story_threads(id),
    relationship TEXT DEFAULT 'member',  -- 'member' | 'related' | 'caused_by'
    PRIMARY KEY (wsj_item_id, thread_id)
);
```

Replaces `wsj_items.thread_id` FK. Defer until "Stories" tab is built.

### Priority & Dependencies

| Step | Effort | Depends on |
|------|--------|------------|
| 1. `wsj_thread_links` table + migration | Small | Nothing |
| 2. LLM causal detection in pipeline | Medium | Step 1 |
| 3. "Related Storylines" on detail page | Medium | Step 2 |
| 4. Many-to-many junction table | Large | Stories tab design |
| 5. Stories tab with causal graph view | Large | Steps 1-4 |

Steps 1-3 are independent and can be built incrementally. Steps 4-5 are for later.

---

## Other Action Items

### Thread Quality Monitoring
Add to `pipeline_health.py`: avg pairwise similarity per thread, member count distribution, creation/archive rate per day.

### Category-Level Thread Exposure
Current: all threads ranked by heat score globally. Needed: "Top 3 threads per category" to guarantee coverage across Markets/Tech/Economy/World/Politics. Frontend sorting change, not pipeline.

### Centroid Alternatives (Low Priority)

| Method | Pros | Cons |
|--------|------|------|
| Mean (current) | Simple, fast | Drifts with diverse members |
| Medoid | Always a real article | O(n²) per update |
| LLM-generated text → embed | Most semantically accurate | API cost per update |

Not worth changing until monitoring shows problems.