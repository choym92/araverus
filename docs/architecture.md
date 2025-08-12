# Architecture (araverus)

## 1) Stack (Pointer)
- **Frontend**: Next.js 15 (App Router), React 19, TypeScript 5, Tailwind CSS 4
- **Auth/DB/Storage**: Supabase (Postgres + Auth + Storage)
- **Validation**: Zod
- **Editor**: TipTap (ProseMirror)
- **Animations**: Framer Motion

> 상세 의존성은 `package.json` 참조. 신규 라이브러리는 CLAUDE.md의 **Over-engineering 금지** 원칙을 따름.

---

## 2) High-level Flow
- **Server-first 원칙** (App Router): 데이터 패칭/보안은 서버에서 처리  
- **Auth**: Supabase Auth (쿠키/세션), 서버에서 role 확인 (`user_profiles.role`)
- **Service Layer**: DB 접근은 `BlogService` 등 서비스 레이어 통해 일관화
- **Storage**: Supabase Storage (블로그 이미지 등)
- **RLS/정책**: 읽기 공개 범위 최소화, 쓰기/관리 권한은 role 기반

```
Client (mostly Server Components)
└─ Next.js App Router (server actions / API routes)
    ├─ Service Layer (e.g., BlogService)
    ├─ Supabase (Postgres, Auth, Storage)
    └─ RLS Policies (role-based access)
```

---

## 3) Folder Convention (summary)
- `src/app` — routes/layouts (server 우선)
- `src/components` — 재사용 UI (필요 시만 `'use client'`)
- `src/hooks` — 커스텀 훅 (브라우저 상호작용 시)
- `src/lib` — 서비스/유틸/클라이언트 생성기
- `docs/` — 아키텍처/스키마/개발 노트
- `PRPs/` — 기능별 제품 요구 프롬프트(가변)

---

## 4) Performance & Quality
- **타입·린트·빌드**: `npm run lint`, `npm run build`는 작업마다 필수
- **이미지/번들**: 불필요한 대형 의존성/이미지 금지
- **접근성(a11y)**: ARIA/포커스/대비—경고 UI는 접근성 있게

---

## 5) ADR Mini-template
> 큰 결정은 간단 ADR로 기록 (`docs/adr/yyyymmdd-meaningful-title.md`)

- Context: (문제/배경)
- Options: (A/B/C 요약)
- Decision: (선택 + 근거)
- Consequences: (+ / −)