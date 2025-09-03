# Database Schema (araverus)
<!-- Updated: 2025-09-03 -->

> 실제 스키마는 마이그레이션/DB를 기준으로 하며, 본 문서는 개념 요약입니다.

**Note**: Finance-related tables (`trading_signals`, `stock_prices`) were removed in 2025-09-03 cleanup.

## Tables

### 1) user_profiles
- `id` (uuid, pk)
- `user_id` (uuid, unique, Supabase auth uid)
- `email` (text, unique)
- `role` (text, enum-like: 'admin' | 'user', default 'user')
- `created_at` (timestamptz, default now())

**Notes**
- 관리자 판별은 **이메일 하드코드 금지**, 반드시 `role='admin'` 사용
- 인덱스: `(user_id)`, `(email)`

---

### 2) blog_posts
- `id` (uuid, pk)
- `author_id` (uuid, fk → user_profiles.user_id)
- `title` (text)
- `slug` (text, unique)
- `content_md` (text)  <!-- TipTap JSON을 쓰면 content_json(JSONB)로 대체 -->
- `tags_csv` (text)    <!-- "tag1,tag2,tag3" -->
- `status` (text, enum-like: 'draft' | 'published', default 'draft')
- `published_at` (timestamptz, nullable)
- `created_at` / `updated_at` (timestamptz)

**Notes**
- 검색/목록 최적화: `(status)`, `(published_at desc)`, `(slug)` 인덱스 고려

---

### 3) blog_assets
- `id` (uuid, pk)
- `owner_id` (uuid, fk → user_profiles.user_id)
- `path` (text)    <!-- storage object path -->
- `url` (text)     <!-- public URL if exposed -->
- `created_at` (timestamptz)

**Notes**
- Storage 정책: 경로별 접근 권한 최소화

---

## RLS (개략)
- `blog_posts`
  - SELECT: `status='published'` OR (`author_id = auth.uid()` OR role admin)
  - INSERT/UPDATE/DELETE: `author_id = auth.uid()` OR role admin
- `blog_assets`
  - SELECT: 소유자 또는 게시물 공개 범위에 한해 노출
  - INSERT/UPDATE/DELETE: `owner_id = auth.uid()` OR role admin

> 실제 정책은 프로젝트의 보안 요구에 맞게 작성/검증하세요.