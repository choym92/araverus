<!-- Updated: 2026-02-16 -->
# Project Conventions

### Auth
Protected routes/pages must use `useAuth` hook **or** server-side session/role check. Never leave a protected route unguarded.

### Data
Always use the service layer for DB logic. Never call Supabase directly in components.

```typescript
// GOOD: Service layer handles DB logic
const posts = await BlogService.getPublished();

// BAD: Direct Supabase call in component
const { data } = await supabase.from('posts').select('*');
```

### Admin
**No hardcoded emails**. Use `user_profiles.role = 'admin'` with RLS/policies for authorization.

### Styling
Tailwind only; no inline styles (except utility overrides when justified).

### Common Gotchas
- `supabase-server.ts` creates the server client; `supabase.ts` is for browser client — don't mix them.
- MDX blog posts live in `src/app/blog/posts/` as `.mdx` files — not in a CMS.
- Finance pipeline scripts are Python in `scripts/finance/` — separate from the Next.js app.
