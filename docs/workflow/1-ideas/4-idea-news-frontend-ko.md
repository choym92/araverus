<!-- Created: 2026-02-15 -->
# 아이디어: 뉴스 프론트엔드 — WSJ 스타일 금융 뉴스 페이지

## 개요
`chopaul.com/news`를 WSJ 스타일의 독립형 뉴스 페이지로 구축. 기존 금융 파이프라인 데이터(기사, 브리핑, 오디오)를 전문적인 에디토리얼 레이아웃으로 표시.

---

## 아키텍처 다이어그램

```mermaid
graph TB
    subgraph "데이터 소스 (Supabase)"
        DB_BRIEF[wsj_briefings<br/>브리핑 텍스트, 오디오 URL, 재생시간]
        DB_ITEMS[wsj_items<br/>제목, 설명, 피드명, 서브카테고리]
        DB_CRAWL[wsj_crawl_results<br/>본문, 대표이미지, 출처]
        DB_LLM[wsj_llm_analysis<br/>요약, 감성분석, 종목코드]
    end

    subgraph "서버 레이어"
        SVC[NewsService<br/>src/lib/news-service.ts]
        PAGE[news/page.tsx<br/>서버 컴포넌트]
        LAYOUT[news/layout.tsx<br/>독립형 레이아웃]
    end

    subgraph "클라이언트 컴포넌트"
        PLAYER[BriefingPlayer<br/>HTML5 Audio API]
        CARDS[ArticleCard<br/>featured / standard / compact]
        NAV[CategoryNav<br/>시장, 테크, 경제...]
    end

    subgraph "페이지 구조"
        MAST[마스트헤드<br/>'CHOPAUL NEWS']
        NAVBAR[카테고리 네비게이션]
        AUDIO[오디오 브리핑 플레이어]
        MAIN[메인 컬럼 8/12]
        SIDE[사이드바 4/12]
    end

    DB_BRIEF --> SVC
    DB_ITEMS --> SVC
    DB_CRAWL --> SVC
    DB_LLM --> SVC
    SVC --> PAGE
    PAGE --> LAYOUT

    LAYOUT --> MAST
    MAST --> NAVBAR
    NAVBAR --> AUDIO
    AUDIO --> PLAYER

    PAGE --> MAIN
    PAGE --> SIDE
    MAIN --> CARDS
    NAVBAR --> NAV
```

## 페이지 레이아웃 와이어프레임

```mermaid
block-beta
    columns 12

    header["CHOPAUL NEWS — 마스트헤드 (Playfair Display 세리프)"]:12
    nav["시장 | 테크 | 경제 | 세계 | 비즈니스 | 정치        🔍"]:12
    player["🎧 데일리 브리핑 — 2026년 2월 15일 | ▶ ━━━━━━━━━○━━━━ 3:42 / 5:15 | 1x"]:12

    space:12

    block:main:8
        featured["대표 기사<br/>대형 헤드라인 + 이미지 + 요약"]
        divider1["─────────────────────────"]
        col1["일반 카드 1<br/>헤드라인 + 요약"]
        col2["일반 카드 2<br/>헤드라인 + 요약"]
        divider2["─────────────────────────"]
        section["테크놀로지 섹션"]
        c1["카드"] c2["카드"] c3["카드"]
    end

    block:sidebar:4
        popular["인기 기사<br/>1. 헤드라인...<br/>2. 헤드라인...<br/>3. 헤드라인..."]
        categories["카테고리별<br/>필터 칩"]
        excerpt["브리핑 발췌<br/>오늘의 요약 텍스트..."]
    end
```

## 컴포넌트 트리

```mermaid
graph LR
    subgraph "news/layout.tsx (서버)"
        L[NewsLayout]
        L --> M[NewsMasthead]
        L --> CN[CategoryNav]
    end

    subgraph "news/page.tsx (서버)"
        P[NewsPage]
        P --> BP[BriefingPlayer 🔊<br/>클라이언트 컴포넌트]
        P --> FG[FeaturedGrid]
        P --> SB[Sidebar]

        FG --> AC1[ArticleCard 대표]
        FG --> AC2[ArticleCard 일반]
        FG --> AC3[ArticleCard 컴팩트]

        SB --> MR[인기기사]
        SB --> CF[카테고리필터]
        SB --> BE[브리핑발췌]
    end
```

## 데이터 흐름

```mermaid
sequenceDiagram
    participant 사용자
    participant 페이지 as news/page.tsx (서버)
    participant 서비스 as NewsService
    participant DB as Supabase

    사용자->>페이지: GET /news?category=TECH
    페이지->>서비스: getLatestBriefing()
    서비스->>DB: SELECT from wsj_briefings ORDER BY date DESC LIMIT 1
    DB-->>서비스: { briefing_text, audio_url, date }

    페이지->>서비스: getNewsItems('TECH', 20)
    서비스->>DB: SELECT wsj_items JOIN wsj_crawl_results<br/>WHERE feed_name='TECH' AND processed=true
    DB-->>서비스: [{ title, description, top_image, source, ... }]

    페이지-->>사용자: 렌더링: 마스트헤드 + 플레이어 + 그리드 + 사이드바
```

---

## 설계 결정

| 결정 사항 | 선택 | 이유 |
|----------|------|------|
| 오디오 플레이어 | 네이티브 HTML5 Audio API | 번들 비용 제로, 완전한 UI 제어, 단순한 요구사항 |
| 레이아웃 | 독립형 (사이트 쉘 미사용) | WSJ 스타일 에디토리얼 경험, 자체 마스트헤드 |
| 카드 스타일 | WSJ 에디토리얼 그리드 | 대표기사 + 2열 그리드 + 카테고리 섹션 |
| 스타일링 | `@theme`의 WSJ 토큰 (Tailwind v4) | `news-*` 네임스페이스, 전역 오염 방지 |
| 폰트 | Playfair Display (헤드라인) + Inter (UI) | 루트 레이아웃에 이미 로드됨 |
| 데이터 | 서버 컴포넌트 + NewsService | 클라이언트 사이드 패칭 없음, 빠른 TTFB |
| 카테고리 필터 | URL 검색 파라미터 (`?category=TECH`) | 공유 가능, SEO 친화적, 서버 컴포넌트 호환 |

## 구현 단계

1. **뉴스 레이아웃 + WSJ 디자인 토큰** — `news/layout.tsx` + globals.css `@theme` 추가
2. **오디오 브리핑 플레이어** — 커스텀 `BriefingPlayer` 클라이언트 컴포넌트
3. **뉴스 데이터 서비스** — Supabase에서 가져오는 `NewsService` 클래스
4. **기사 카드 컴포넌트** — 3가지 변형의 `ArticleCard`
5. **페이지 조립** — 실제 데이터로 그리드 레이아웃 연결
6. **카테고리 라우팅** — 검색 파라미터로 카테고리 필터링

## WSJ 디자인 레퍼런스
- 색상: midnight `#111`, coal `#333`, smoke `#ebebeb`, blue `#0274b6`, red `#e10000`, gold `#816d4d`
- 타이포그래피: 17px 기본, 세리프 헤드라인, 산세리프 UI/메타
- 레이아웃: 1280px 최대폭, 12열 그리드 (8+4 사이드바), 전체 1px 보더 구분선
- 헤더: 대형 세리프 타이틀 → 카테고리 네비 (다크 바) → 콘텐츠
