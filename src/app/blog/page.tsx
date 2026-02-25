import { getAllPosts } from '@/lib/mdx';
import { createClient } from '@/lib/supabase-server';
import BlogList from './BlogList';

async function checkIsAdmin(): Promise<boolean> {
  const supabase = await createClient();
  const { data } = await supabase.auth.getUser();
  if (!data.user) return false;

  const { data: profile } = await supabase
    .from('user_profiles')
    .select('role')
    .eq('id', data.user.id)
    .single();

  return profile?.role === 'admin';
}

export default async function BlogPage({
  searchParams,
}: {
  searchParams: Promise<{ category?: string }>;
}) {
  const params = await searchParams;
  const [posts, isAdmin] = await Promise.all([
    getAllPosts(),
    checkIsAdmin(),
  ]);

  return <BlogList initialPosts={posts} initialCategory={params.category} isAdmin={isAdmin} />;
}