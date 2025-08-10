import { notFound } from 'next/navigation';
import { Metadata } from 'next';
import Image from 'next/image';
import Link from 'next/link';
import { Calendar, Clock, Eye, Tag, ArrowLeft } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';
import 'highlight.js/styles/github.css';
import type { BlogPostWithAuthor } from '@/lib/blog.types';
import ShareButtons from './ShareButtons';

// --- helpers ---
const formatDate = (iso: string) =>
  new Date(iso).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });

const calcReadTime = (content?: string) => {
  const text = (content ?? '').replace(/[#_*`>~\[\]\(\)!]/g, ' ').replace(/<[^>]+>/g, ' ');
  const words = text.trim() ? text.trim().split(/\s+/).length : 0;
  return `${Math.max(1, Math.ceil(words / 200))} min read`;
};

// fetchers (서버에서 API 호출: 캐시 없이 최신)
async function fetchPost(slug: string): Promise<BlogPostWithAuthor | null> {
  const { BlogService } = await import('@/lib/blog.service');
  const svc = new BlogService();
  return await svc.getPostBySlug(slug);
}

async function fetchRelated(limit = 3): Promise<BlogPostWithAuthor[]> {
  const baseUrl = process.env.NEXT_PUBLIC_BASE_URL || 'http://localhost:3000';
  const res = await fetch(`${baseUrl}/api/blog?limit=${limit}`, {
    cache: 'no-store',
    next: { revalidate: 0 },
  }).catch(() => null);
  if (!res || !res.ok) return [];
  const data = await res.json().catch(() => ({ posts: [] }));
  return (data.posts ?? []) as BlogPostWithAuthor[];
}

// SEO 메타 (가능하면 서버에서 생성)
export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  const post = await fetchPost(slug);
  if (!post) return { title: 'Post not found' };
  return {
    title: post.meta_title ?? post.title,
    description: post.meta_description ?? post.excerpt ?? undefined,
    openGraph: {
      title: post.meta_title ?? post.title,
      description: post.meta_description ?? post.excerpt ?? undefined,
      type: 'article',
      images: post.featured_image ? [{ url: post.featured_image }] : undefined,
      publishedTime: post.published_at ?? undefined,
    },
  };
}

export default async function BlogDetailPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const post = await fetchPost(slug);
  if (!post) notFound();

  // 관련글: 동일 태그 우선 필터링
  const relatedAll = await fetchRelated(6);
  const related = relatedAll
    .filter(p => p.id !== post.id)
    .filter(p => {
      const postTags = Array.isArray(post.tags) ? post.tags : [];
      const relatedTags = Array.isArray(p.tags) ? p.tags : [];
      const a = new Set(postTags.map(t => t.toLowerCase()));
      return relatedTags.some(t => a.has(t.toLowerCase()));
    })
    .slice(0, 3);

  // 관련글이 없으면 최신 글로 채우기
  if (related.length < 3) {
    const remaining = relatedAll
      .filter(p => p.id !== post.id && !related.some(r => r.id === p.id))
      .slice(0, 3 - related.length);
    related.push(...remaining);
  }

  // 공유 링크(클라이언트 전용 동작은 버튼에서 처리)
  const canonical = `${process.env.NEXT_PUBLIC_BASE_URL ?? 'http://localhost:3000'}/blog/${post.slug}`;

  return (
    <article className="min-h-screen bg-white">
      {/* Hero */}
      {post.featured_image && (
        <div className="relative h-[400px] bg-gray-900">
          <Image
            src={post.featured_image}
            alt={post.title}
            fill
            priority
            sizes="100vw"
            className="object-cover opacity-60"
          />
          <div className="absolute inset-0 bg-gradient-to-t from-gray-900 via-gray-900/50 to-transparent" />
        </div>
      )}

      <div className="max-w-4xl mx-auto px-6 py-12">
        {/* Back */}
        <div className="mb-8">
          <Link href="/blog" className="inline-flex items-center gap-2 text-gray-600 hover:text-gray-900 transition-colors">
            <ArrowLeft size={20} />
            <span>Back to blog</span>
          </Link>
        </div>

        {/* Header */}
        <header className="mb-12">
          {post.tags && post.tags.length > 0 && (
            <div className="flex flex-wrap gap-2 mb-4">
              {(Array.isArray(post.tags) ? post.tags : []).map((tag, i) => (
                <span key={i} className="inline-flex items-center gap-1 px-3 py-1 text-sm font-medium text-blue-600 bg-blue-50 rounded-full">
                  <Tag size={12} />
                  {tag}
                </span>
              ))}
            </div>
          )}

          <h1 className="text-4xl md:text-5xl font-bold text-gray-900 mb-6 leading-tight">{post.title}</h1>

          {post.excerpt && <p className="text-xl text-gray-600 mb-8 leading-relaxed">{post.excerpt}</p>}

          <div className="flex flex-wrap items-center gap-6 pb-8 border-b border-gray-200">
            {/* Author */}
            <div className="flex items-center gap-3">
              {post.author?.avatar_url ? (
                <Image 
                  src={post.author.avatar_url} 
                  alt={post.author.full_name ?? 'Author'} 
                  width={40} 
                  height={40} 
                  className="rounded-full object-cover" 
                />
              ) : (
                <div className="w-10 h-10 rounded-full bg-gray-300" />
              )}
              <div>
                <p className="font-medium text-gray-900">
                  {post.author?.full_name || post.author?.email?.split('@')[0] || 'Anonymous'}
                </p>
                <p className="text-sm text-gray-500">{post.author?.role || 'Author'}</p>
              </div>
            </div>

            {/* Meta */}
            <div className="flex items-center gap-4 text-sm text-gray-500">
              <span className="flex items-center gap-1">
                <Calendar size={16} />
                {formatDate(post.published_at || post.created_at)}
              </span>
              <span className="flex items-center gap-1">
                <Clock size={16} />
                {calcReadTime(post.content)}
              </span>
              {post.view_count > 0 && (
                <span className="flex items-center gap-1">
                  <Eye size={16} />
                  {post.view_count} views
                </span>
              )}
            </div>

            {/* Share (클라 동작은 작은 컴포넌트로 분리) */}
            <ShareButtons title={post.title} url={canonical} />
          </div>
        </header>

        {/* Body */}
        <div className="prose prose-lg max-w-none mb-16">
          <ReactMarkdown 
            remarkPlugins={[remarkGfm]} 
            rehypePlugins={[rehypeHighlight]} 
            components={{
              h1: ({ children }) => <h1 className="text-3xl font-bold mt-8 mb-4 text-gray-900">{children}</h1>,
              h2: ({ children }) => <h2 className="text-2xl font-semibold mt-8 mb-4 text-gray-900">{children}</h2>,
              h3: ({ children }) => <h3 className="text-xl font-semibold mt-6 mb-3 text-gray-900">{children}</h3>,
              p: ({ children }) => <p className="mb-4 leading-relaxed text-gray-700">{children}</p>,
              ul: ({ children }) => <ul className="list-disc list-inside mb-4 space-y-2">{children}</ul>,
              ol: ({ children }) => <ol className="list-decimal list-inside mb-4 space-y-2">{children}</ol>,
              li: ({ children }) => <li className="text-gray-700">{children}</li>,
              blockquote: ({ children }) => (
                <blockquote className="border-l-4 border-blue-500 pl-4 my-4 italic text-gray-600">
                  {children}
                </blockquote>
              ),
              code: ({ className, children, ...props }) => {
                const match = /language-(\w+)/.exec(className || '');
                return match ? (
                  <code className={className} {...props}>{children}</code>
                ) : (
                  <code className="bg-gray-100 px-1 py-0.5 rounded text-sm" {...props}>{children}</code>
                );
              },
              pre: ({ children }) => (
                <pre className="bg-gray-50 rounded-lg p-4 overflow-x-auto mb-4">{children}</pre>
              ),
              img: ({ src = '', alt = '' }) => (
                <span className="block relative w-full h-auto my-6">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={src} alt={alt} className="rounded-lg shadow-md w-full" />
                </span>
              ),
              a: ({ href = '', children }) => (
                <a
                  href={href}
                  className="text-blue-600 hover:text-blue-700 underline"
                  target={href.startsWith('http') ? '_blank' : undefined}
                  rel={href.startsWith('http') ? 'noopener noreferrer' : undefined}
                >
                  {children}
                </a>
              ),
            }}
          >
            {post.content}
          </ReactMarkdown>
        </div>

        {/* Related */}
        {related.length > 0 && (
          <section className="border-t border-gray-200 pt-12">
            <h2 className="text-2xl font-bold mb-8">Related Articles</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {related.map(r => (
                <Link key={r.id} href={`/blog/${r.slug}`} className="group">
                  <article className="h-full bg-white border border-gray-200 rounded-lg overflow-hidden hover:shadow-lg transition-shadow">
                    {r.featured_image ? (
                      <div className="relative h-32 bg-gray-200 overflow-hidden">
                        <Image 
                          src={r.featured_image} 
                          alt={r.title} 
                          fill 
                          sizes="(max-width:768px) 100vw, 33vw" 
                          className="object-cover group-hover:scale-105 transition-transform duration-300" 
                        />
                      </div>
                    ) : (
                      <div className="h-32 bg-gradient-to-br from-gray-100 to-gray-200" />
                    )}
                    <div className="p-4">
                      <h3 className="font-semibold text-gray-900 line-clamp-2 group-hover:text-blue-600 transition-colors">
                        {r.title}
                      </h3>
                      <p className="text-sm text-gray-500 mt-2">
                        {formatDate(r.published_at || r.created_at)}
                      </p>
                    </div>
                  </article>
                </Link>
              ))}
            </div>
          </section>
        )}
      </div>
    </article>
  );
}