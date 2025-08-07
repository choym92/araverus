import { createClient } from '@/lib/supabase-server';
import Link from 'next/link';
import { format } from 'date-fns';
import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Blog - Araverus',
  description: 'Insights on financial markets, SEC filings, and AI-powered investment analysis.',
};

interface BlogPostListing {
  id: string;
  title: string;
  slug: string;
  excerpt: string;
  featured_image?: string;
  published_at: string;
  tags: string[];
  view_count: number;
}

async function getBlogPosts(): Promise<BlogPostListing[]> {
  const supabase = await createClient();
  
  const { data, error } = await supabase
    .from('blog_posts')
    .select('id, title, slug, excerpt, featured_image, published_at, tags, view_count')
    .eq('status', 'published')
    .order('published_at', { ascending: false });

  if (error) {
    console.error('Error fetching blog posts:', error);
    return [];
  }

  return data || [];
}

export default async function BlogPage() {
  const posts = await getBlogPosts();

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white shadow-sm">
        <div className="max-w-4xl mx-auto px-4 py-12 sm:px-6 lg:px-8">
          <div className="text-center">
            <h1 className="text-4xl font-bold text-gray-900 mb-4">
              Araverus Blog
            </h1>
            <p className="text-xl text-gray-600 max-w-2xl mx-auto">
              Insights on financial markets, SEC filings, and AI-powered investment analysis.
            </p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <div className="bg-white border-b">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-4">
            <Link 
              href="/"
              className="text-blue-600 hover:text-blue-800 font-medium"
            >
              ← Back to Home
            </Link>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-4xl mx-auto px-4 py-8 sm:px-6 lg:px-8">
        {posts.length === 0 ? (
          <div className="text-center py-16">
            <div className="text-gray-400 text-6xl mb-4">📝</div>
            <h2 className="text-2xl font-bold text-gray-900 mb-2">No posts yet</h2>
            <p className="text-gray-600">
              Check back soon for insights on financial analysis and market trends.
            </p>
          </div>
        ) : (
          <div className="space-y-8">
            {posts.map((post, index) => (
              <article key={post.id} className={`bg-white rounded-lg shadow-sm overflow-hidden ${
                index === 0 ? 'lg:flex' : ''
              }`}>
                {/* Featured Image */}
                {post.featured_image && (
                  <div className={index === 0 ? 'lg:w-1/2' : 'w-full'}>
                    <img
                      src={post.featured_image}
                      alt={post.title}
                      className={`w-full object-cover ${
                        index === 0 ? 'h-64 lg:h-full' : 'h-48'
                      }`}
                    />
                  </div>
                )}

                <div className={`p-6 ${index === 0 && post.featured_image ? 'lg:w-1/2' : 'w-full'}`}>
                  <div className="flex items-center text-sm text-gray-500 mb-3">
                    <time dateTime={post.published_at}>
                      {format(new Date(post.published_at), 'MMMM d, yyyy')}
                    </time>
                    <span className="mx-2">•</span>
                    <span>{post.view_count} views</span>
                  </div>

                  <h2 className={`font-bold text-gray-900 mb-3 ${
                    index === 0 ? 'text-2xl lg:text-3xl' : 'text-xl'
                  }`}>
                    <Link 
                      href={`/blog/${post.slug}`}
                      className="hover:text-blue-600 transition-colors"
                    >
                      {post.title}
                    </Link>
                  </h2>

                  {post.excerpt && (
                    <p className={`text-gray-600 mb-4 ${
                      index === 0 ? 'text-lg' : 'text-base'
                    }`}>
                      {post.excerpt}
                    </p>
                  )}

                  <div className="flex items-center justify-between">
                    <div className="flex flex-wrap gap-2">
                      {post.tags.slice(0, 3).map((tag) => (
                        <span
                          key={tag}
                          className="inline-block bg-gray-100 text-gray-700 px-2 py-1 rounded-full text-xs"
                        >
                          {tag}
                        </span>
                      ))}
                      {post.tags.length > 3 && (
                        <span className="text-gray-500 text-xs">
                          +{post.tags.length - 3} more
                        </span>
                      )}
                    </div>

                    <Link
                      href={`/blog/${post.slug}`}
                      className="text-blue-600 hover:text-blue-800 font-medium text-sm"
                    >
                      Read more →
                    </Link>
                  </div>
                </div>
              </article>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}