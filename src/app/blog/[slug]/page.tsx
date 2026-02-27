import { notFound } from 'next/navigation';
import { Metadata } from 'next';
import Image from 'next/image';
import Link from 'next/link';
import { Tag, ArrowLeft } from 'lucide-react';
import { MDXRemote } from 'next-mdx-remote/rsc';
import remarkGfm from 'remark-gfm';
import rehypeSlug from 'rehype-slug';
import rehypePrettyCode from 'rehype-pretty-code';
import { getPostBySlug, getAllPostSlugs, getAllPosts } from '@/lib/mdx';
import { mdxComponents } from '@/components/mdx/components';
import ShareBar from '@/components/ShareBar';

// --- helpers ---
const formatDate = (iso: string) =>
  new Date(iso).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });

const calcReadTime = (content?: string) => {
  const text = (content ?? '').replace(/[#_*`>~\[\]\(\)!]/g, ' ').replace(/<[^>]+>/g, ' ');
  const words = text.trim() ? text.trim().split(/\s+/).length : 0;
  return `${Math.max(1, Math.ceil(words / 200))} min read`;
};

// Generate static params for all blog posts
export async function generateStaticParams() {
  const slugs = await getAllPostSlugs();
  return slugs.map((slug) => ({
    slug,
  }));
}

// SEO metadata
export async function generateMetadata({ 
  params 
}: { 
  params: Promise<{ slug: string }> 
}): Promise<Metadata> {
  const { slug } = await params;
  const post = await getPostBySlug(slug);
  
  if (!post) {
    return { title: 'Post not found' };
  }
  
  return {
    title: post.frontmatter.title,
    description: post.frontmatter.excerpt || undefined,
    openGraph: {
      title: post.frontmatter.title,
      description: post.frontmatter.excerpt || undefined,
      type: 'article',
      images: post.frontmatter.coverImage ? [{ url: post.frontmatter.coverImage }] : undefined,
      publishedTime: post.frontmatter.date,
    },
  };
}

export default async function BlogPostPage({ 
  params 
}: { 
  params: Promise<{ slug: string }> 
}) {
  const { slug } = await params;
  const post = await getPostBySlug(slug);

  if (!post) {
    notFound();
  }

  // Get related posts (same category)
  const allPosts = await getAllPosts(post.frontmatter.category);
  const relatedPosts = allPosts
    .filter(p => p.slug !== post.slug)
    .slice(0, 3);

  return (
    <div className="blog max-w-4xl mx-auto px-6 py-12">
      {/* Back to Blog */}
      <Link 
        href="/blog" 
        className="inline-flex items-center gap-2 text-gray-500 hover:text-gray-700 text-sm mb-8"
      >
        <ArrowLeft size={14} />
        Back to Blog
      </Link>

      {/* Post Header */}
      <header className="mb-12 text-center">
        {/* Title */}
        <h1 className="text-3xl md:text-4xl font-semibold text-gray-900 mb-4 leading-tight">
          {post.frontmatter.title}
        </h1>

        {/* Meta */}
        <div className="flex flex-wrap items-center justify-center gap-4 text-sm text-gray-500">
          <span>
            {formatDate(post.frontmatter.date)}
          </span>
          <span>·</span>
          <span>
            {calcReadTime(post.content)}
          </span>
        </div>

        {/* Tags */}
        {post.frontmatter.tags && post.frontmatter.tags.length > 0 && (
          <div className="flex flex-wrap justify-center gap-2 mt-4">
            {post.frontmatter.tags.map((tag) => (
              <span 
                key={tag} 
                className="inline-flex items-center gap-1 px-2 py-1 text-xs text-gray-500 bg-gray-50 rounded"
              >
                <Tag size={10} />
                {tag}
              </span>
            ))}
          </div>
        )}
      </header>

      {/* Featured Image */}
      {post.frontmatter.coverImage && (
        <div className="mb-12">
          <Image
            src={post.frontmatter.coverImage}
            alt={post.frontmatter.title}
            width={1200}
            height={630}
            className="w-full h-auto rounded"
            priority
          />
        </div>
      )}

      {/* MDX Content */}
      <div className="prose prose-lg max-w-none">
          <MDXRemote
            source={post.content}
            components={mdxComponents}
            options={{
              mdxOptions: {
                remarkPlugins: [remarkGfm],
                rehypePlugins: [
                  rehypeSlug,
                  [rehypePrettyCode, {
                    theme: 'github-dark',
                    keepBackground: true,
                    defaultLang: 'plaintext',
                  }],
                ],
              },
            }}
          />
      </div>

      {/* Share Buttons */}
      <div className="mt-12 pt-8 border-t border-gray-200">
        <ShareBar
          url={`https://chopaul.com/blog/${post.slug}`}
          title={post.frontmatter.title}
        />
      </div>

      {/* Related Posts */}
      {relatedPosts.length > 0 && (
        <section className="mt-16 pt-16 border-t border-gray-200">
          <h2 className="text-xl font-semibold text-gray-900 mb-8">Related Posts</h2>
          <div className="grid gap-6 md:grid-cols-3">
            {relatedPosts.map((related) => (
              <Link
                key={related.slug}
                href={`/blog/${related.slug}`}
                className="group"
              >
                <article className="h-full bg-white border border-gray-200 rounded-lg overflow-hidden hover:shadow-lg transition-shadow">
                  {related.frontmatter.coverImage ? (
                    <div className="h-40 bg-gray-200 overflow-hidden">
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img
                        src={related.frontmatter.coverImage}
                        alt={related.frontmatter.title}
                        className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                      />
                    </div>
                  ) : (
                    <div className="h-40 bg-gradient-to-br from-blue-100 to-purple-100" />
                  )}
                  <div className="p-4">
                    <h3 className="font-semibold text-gray-900 line-clamp-2 group-hover:text-blue-600 transition-colors">
                      {related.frontmatter.title}
                    </h3>
                    <p className="mt-2 text-sm text-gray-600">
                      {formatDate(related.frontmatter.date)}
                    </p>
                  </div>
                </article>
              </Link>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}