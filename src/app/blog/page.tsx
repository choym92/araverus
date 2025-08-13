import { getAllPosts } from '@/lib/mdx';
import BlogList from './BlogList';

export default async function BlogPage({
  searchParams,
}: {
  searchParams: Promise<{ category?: string }>;
}) {
  const params = await searchParams;
  const posts = await getAllPosts();
  
  return <BlogList initialPosts={posts} initialCategory={params.category} />;
}