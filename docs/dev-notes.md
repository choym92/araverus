# Development Notes (araverus)

## Commands
- Dev server: `npm run dev`
- Type/Build: `npm run build`
- Lint: `npm run lint`
- Start (prod): `npm start`
- Test (예: Vitest): `npm run test`

## Env Variables (examples)
Create `.env.local` (never commit):
```
NEXT_PUBLIC_SUPABASE_URL=...
NEXT_PUBLIC_SUPABASE_ANON_KEY=...
SUPABASE_SERVICE_ROLE_KEY=... # server only (never expose)
NEXT_PUBLIC_BASE_URL=http://localhost:3000
```

## Working Rules (from CLAUDE.md)
- **Server-first** (App Router): 서버에서 데이터/보안 처리, 클라 상호작용만 Client
- **Service Layer**: DB 로직은 `BlogService` 등에서 일관성 유지
- **Role-based Admin**: `user_profiles.role='admin'`으로 권한 확인
- **A11y/Security/Tests**: 최소 가드라인 준수 (happy + edge 1개)

## Release Checklist
1) `npm run lint` / `npm run build` clean  
2) 비밀키/로그 노출 확인  
3) 변경사항 요약 `docs/cc/YYYY-MM-DD.md` 업데이트  
4) (선택) E2E/접근성 점검

## Notes
- 큰 변경은 ADR로 기록: `docs/adr/yyyymmdd-title.md`
- 이미지/라이브러리 사이즈 주의 (번들/성능)