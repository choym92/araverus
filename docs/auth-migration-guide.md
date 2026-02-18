<!-- Updated: 2026-02-17 -->
# Auth Migration Guide — Email Hardcoding → Role-based

## Status

Phase 1 is **complete** and deployed. Phase 2 (RLS) is pending — tracked in `docs/workflow/4-todo/auth-rls-migration.md`.

---

## Phase 1: Role-based Auth (Complete)

### What was done

1. **DB**: Added `role TEXT` column to `user_profiles`, created `is_admin(uid)` SQL helper
2. **`src/lib/authz.ts`**: Server-side guards (`requireUser`, `requireAdmin`) using `createClient` from `supabase-server.ts`
3. **`src/lib/blog.service.ts`**: `isAdmin()` checks `user_profiles.role` with `_adminCache` optimization
4. **`src/app/admin/layout.tsx`**: Protected with `requireAdmin()`

### Key implementation notes

- `authz.ts` uses the existing `createClient` wrapper (not raw `createServerClient`)
- `BlogService.isAdmin()` caches the result in `_adminCache` to avoid repeated DB queries per request
- Non-admin users get `notFound()` (404), not a redirect — prevents information leakage

---

## Phase 2: RLS Policies (Pending)

See `docs/workflow/4-todo/auth-rls-migration.md` for the full plan.

Summary: Enable Row Level Security on `user_profiles`, `blog_posts`, `blog_assets` to enforce access control at the database level.

---

## Rollback Plan

```sql
-- Phase 1: No destructive changes were made. To revert, just stop using the role column.
-- Phase 2: If RLS causes issues:
ALTER TABLE public.user_profiles DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.blog_posts DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.blog_assets DISABLE ROW LEVEL SECURITY;
```
