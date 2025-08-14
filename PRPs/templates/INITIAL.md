## FEATURE
<한 줄 요약>  
예) 관리자 전용 태그 관리 UI(`/admin/tags`): 생성/이름수정/삭제

## CONTEXT (Why)
<이 기능이 왜 필요한가 (2~3줄)>

## USER STORY
- As an admin, I want to <…>
- So that <…>

## NON-GOALS
- 이번 스코프에서 하지 않을 것 2~3개 (예: 검색, 페이지네이션, 권한 에디터)

## EXAMPLES (Codebase references)
- `src/lib/authz.ts` → `requireAdmin()` 서버 가드
- `src/lib/blog.service.ts` → 서비스 레이어 패턴 참고
- (유사 UI/라우트 경로가 있으면 1~2개 더 추가)

## DOCUMENTATION
- Global rules: `CLAUDE.md` (server-first, role-based admin)
- DB: `docs/schema.md` (관련 테이블/컬럼)
- (필요 시) Next.js / Supabase / Zod / Tailwind 공식 문서 링크 1~2개

## SUCCESS CRITERIA (Acceptance)
- 접근 제어: 비로그인→`/login`, 일반유저→404, admin→정상 접근
- 동작: <구체 기준 2~3개> (예: 태그 생성/수정/삭제가 DB에 반영되고 목록 갱신)
- 품질: `npm run lint && npm run build` 통과

## IMPLEMENTATION NOTES
- **서버 우선**: 클라이언트에서 Supabase 직접 호출 금지. 변경은 **API(POST)** 또는 **서버 액션**.
- **서비스 레이어**: DB 변경은 반드시 `BlogService` 메서드를 통해 수행.
- UI 상태: 로딩/에러/성공 메시지 표시(접근성 고려, alert() 사용 금지)

## VALIDATION (How to verify)
- curl 스모크(있다면 API 경로 1~2개):
  - `POST /api/admin/<resource>/<id>/create|update|delete`
- 브라우저: `/admin/<path>` 접근/버튼 동작 확인 (happy + edge 1)

## RISKS / GOTCHAS
- 서버/클라이언트 경계, RLS/권한, 중복/대소문자 정책 등

## SLICE HINT (선택)
- 1단계: 목록/읽기 → 2단계: 생성 → 3단계: 수정/삭제
