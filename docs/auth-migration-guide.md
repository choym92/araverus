# Auth Migration Guide - From Email Hardcoding to Role-based

## Phase 1: Safe Minimum Setup (No Drops, Minimal Changes)

### 1. Database Setup - Run in Supabase SQL Editor

```sql
-- 1) Add role column if not exists (default 'user')
do $$
begin
  if not exists (
    select 1
    from information_schema.columns
    where table_schema='public' and table_name='user_profiles' and column_name='role'
  ) then
    alter table public.user_profiles
      add column role text not null default 'user';
  end if;
end$$;

-- 2) Create is_admin(uid) helper function (uses user_profiles.id)
create or replace function public.is_admin(uid uuid)
returns boolean
language sql stable
as $$
  select exists (
    select 1
    from public.user_profiles
    where id = uid and role = 'admin'
  );
$$;

-- 3) Set initial admin (modify email as needed)
update public.user_profiles
set role = 'admin'
where email = 'choym92@gmail.com';

-- Verify the setup
select email, role from public.user_profiles where role = 'admin';
```

### 2. Create Server-side Auth Guards

Create `src/lib/authz.ts`:

```typescript
// src/lib/authz.ts
import { cookies } from 'next/headers';
import { redirect, notFound } from 'next/navigation';
import { createServerClient } from '@supabase/ssr';

export async function getSupabaseServer() {
  const cookieStore = await cookies();
  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: { get: (name: string) => cookieStore.get(name)?.value },
    }
  );
}

export async function requireUser() {
  const supabase = await getSupabaseServer();
  const { data } = await supabase.auth.getUser();
  if (!data.user) redirect('/login');
  return data.user;
}

export async function requireAdmin() {
  const supabase = await getSupabaseServer();
  const { data } = await supabase.auth.getUser();
  if (!data.user) redirect('/login');

  const { data: profile } = await supabase
    .from('user_profiles')
    .select('role')
    .eq('id', data.user.id)   // Use id column
    .single();

  if (profile?.role !== 'admin') notFound(); // or redirect('/')
  return data.user;
}
```

### 3. Update BlogService isAdmin Method

Replace email hardcoding with role check in `src/lib/blog.service.ts`:

```typescript
async isAdmin(): Promise<boolean> {
  try {
    const { data: { user } } = await this.supabase.auth.getUser();
    if (!user) return false;

    const { data: profile } = await this.supabase
      .from('user_profiles')
      .select('role')
      .eq('id', user.id)
      .single();

    return profile?.role === 'admin';
  } catch (error) {
    console.error('Admin check failed:', error);
    return false;
  }
}
```

### 4. Protect Admin Routes

Example for admin layout (`src/app/admin/layout.tsx`):

```typescript
import { requireAdmin } from '@/lib/authz';

export default async function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  await requireAdmin(); // Throws if not admin
  
  return (
    <div className="admin-layout">
      {children}
    </div>
  );
}
```

## Phase 2: RLS Policies (After Testing Phase 1)

### Enable RLS and Add Policies

```sql
-- Enable RLS on tables
alter table public.user_profiles enable row level security;
alter table public.blog_posts enable row level security;
alter table public.blog_assets enable row level security;

-- User profiles: viewable by owner or admin
create policy "users_view_own_or_admin" on public.user_profiles
  for select using (
    auth.uid() = id or public.is_admin(auth.uid())
  );

-- Blog posts: public can view published, authors/admins see all
create policy "posts_public_view" on public.blog_posts
  for select using (
    status = 'published' or 
    author_id = auth.uid() or 
    public.is_admin(auth.uid())
  );

-- Blog posts: authors and admins can insert/update/delete
create policy "posts_author_admin_write" on public.blog_posts
  for all using (
    author_id = auth.uid() or public.is_admin(auth.uid())
  );
```

## Migration Checklist

- [ ] Run Phase 1 SQL in Supabase
- [ ] Create `authz.ts` with guard functions
- [ ] Update `BlogService.isAdmin()` method
- [ ] Test admin access with role-based check
- [ ] Remove all email hardcoding
- [ ] Run Phase 2 RLS policies (after testing)
- [ ] Test all auth flows

## Rollback Plan

If issues occur:

```sql
-- Remove role check (revert to email)
-- Just don't use the role column, no need to drop

-- Disable RLS if enabled
alter table public.user_profiles disable row level security;
alter table public.blog_posts disable row level security;
```