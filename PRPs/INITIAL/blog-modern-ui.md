## FEATURE
/blog 글 상세 모던 아티클 UI v1 (Prose 테마 + 카드 레이아웃 + 코드블록 하이라이트)

## CONTEXT (Why)
현재 글 상세는 기본 스타일로 가독성과 완성도가 낮음. 타이포/여백/코드블록/ToC를 표준화해 브랜드 일관성과 읽기 만족도를 높임.

## USER STORY
- As a reader, I want a clean, readable article page so that I can focus without visual noise.
- As an author, I want code and headings to render beautifully so that my technical posts look professional.

## NON-GOALS
- 검색/태그 필터/댓글 시스템
- 다크모드 전환(후속)
- 이미지 라이트박스/공유 버튼(후속)

## EXAMPLES (Codebase references)
- `content/blog/*` MDX 원본
- `src/app/blog/[slug]/page.tsx` 렌더 경로
- `tailwind.config.ts` 플러그인 추가 지점

## DOCUMENTATION
- Next.js App Router
- Tailwind Typography 플러그인
- rehype-pretty-code

## SUCCESS CRITERIA
- Lighthouse a11y ≥ 95, CLS < 0.02
- 코드블록에 하이라이트/줄번호 적용, 모바일 가로 스크롤 부드럽게
- h1/h2 스케일·여백·링크/인용구/표가 Prose 테마로 일관 적용

## IMPLEMENTATION NOTES
- 서버 우선: MDX 로딩/직렬화는 서버에서, 클라이언트에 HTML만 전달
- UI 상태: ToC는 rehype-slug로 id 붙이고 클라에서 querySelectorAll('h2,h3')로 구축 가능
- CSS는 /blog 스코핑으로 사이트 전역에 영향 최소화

## VALIDATION
- `/blog/claude-code-automation` 렌더 확인(제목/코드/표/인용구/이미지)
- iPhone 15/Pixel 8/1024/1440 뷰포트 스냅샷 비교

## RISKS / GOTCHAS
- MDX 파이프라인 위치(Next config or unified pipeline)
- Shiki 빌드 타임 비용(문제시 'token-highlighting off' 모드 고려)

## SLICE HINT
1. Prose 테마 + 카드 레이아웃 → 2) 코드블록 → 3) ToC/Progress bar