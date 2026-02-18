<!-- Created: 2026-02-17 -->
# TODO: Enable RLS on Blog & Auth Tables

Phase 1 (role-based auth) is complete. This is Phase 2: database-level access control via Row Level Security.

**Why**: Currently access control is code-level only (`authz.ts`, `BlogService.isAdmin()`). Anyone with the Supabase anon key can bypass it by calling the API directly.

---

## Prerequisites

- [ ] Verify `is_admin(uid)` function exists in Supabase (created in Phase 1)
- [ ] Confirm all blog/admin code paths go through `authz.ts` or `BlogService` (no direct Supabase calls in components)

## Migration SQL

```sql
-- 1. Enable RLS
ALTER TABLE public.user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.blog_posts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.blog_assets ENABLE ROW LEVEL SECURITY;

-- 2. user_profiles: owner or admin can read
CREATE POLICY "users_view_own_or_admin" ON public.user_profiles
  FOR SELECT USING (
    auth.uid() = id OR public.is_admin(auth.uid())
  );

-- 3. blog_posts: published = public, drafts = author/admin only
CREATE POLICY "posts_public_read" ON public.blog_posts
  FOR SELECT USING (
    status = 'published'
    OR author_id = auth.uid()
    OR public.is_admin(auth.uid())
  );

CREATE POLICY "posts_author_admin_write" ON public.blog_posts
  FOR ALL USING (
    author_id = auth.uid() OR public.is_admin(auth.uid())
  );

-- 4. blog_assets: same as blog_posts
CREATE POLICY "assets_author_admin" ON public.blog_assets
  FOR ALL USING (
    -- assumes blog_assets has an author_id or link through blog_posts
    public.is_admin(auth.uid())
  );
```

## Testing Checklist

- [ ] Unauthenticated user can read published blog posts
- [ ] Unauthenticated user cannot read draft posts
- [ ] Admin can read/write all posts
- [ ] Author can read/write own posts only
- [ ] `blog_assets` accessible only to admin
- [ ] Supabase Dashboard → Auth → test with anon key directly

## Rollback

```sql
ALTER TABLE public.user_profiles DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.blog_posts DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.blog_assets DISABLE ROW LEVEL SECURITY;
```

## Notes

- `blog_assets` policy assumes admin-only access. If authors need to manage their own assets, the policy needs a join through `blog_posts.author_id`.
- Consider adding `user_profiles` UPDATE/INSERT policies if user self-service features are added later.
- Reference: `docs/auth-migration-guide.md`
