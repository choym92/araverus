'use client';

import { AdminGuard } from '@/components/AdminGuard';
import { AdminLayout } from '@/components/AdminLayout';
import { RichTextEditor } from '@/components/RichTextEditor';
import { ImageUpload } from '@/components/ImageUpload';
import { useAuth } from '@/hooks/useAuth';
import { useRouter } from 'next/navigation';
import { useState, FormEvent } from 'react';
import slugify from 'slugify';

interface FormData {
  title: string;
  slug: string;
  content: string;
  excerpt: string;
  featuredImage: string;
  tags: string;
  metaTitle: string;
  metaDescription: string;
  status: 'draft' | 'published';
}

export default function NewBlogPost() {
  const { user, supabase } = useAuth();
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState<FormData>({
    title: '',
    slug: '',
    content: '',
    excerpt: '',
    featuredImage: '',
    tags: '',
    metaTitle: '',
    metaDescription: '',
    status: 'draft',
  });

  const handleTitleChange = (title: string) => {
    const slug = slugify(title, { lower: true, strict: true });
    setFormData(prev => ({ ...prev, title, slug }));
  };

  const handleSubmit = async (e: FormEvent, asDraft = true) => {
    e.preventDefault();
    if (!user) return;

    setLoading(true);

    try {
      const tagsArray = formData.tags
        .split(',')
        .map(tag => tag.trim())
        .filter(tag => tag.length > 0);

      const postData = {
        title: formData.title,
        slug: formData.slug,
        content: formData.content,
        excerpt: formData.excerpt,
        featured_image: formData.featuredImage || null,
        tags: tagsArray,
        meta_title: formData.metaTitle || formData.title,
        meta_description: formData.metaDescription || formData.excerpt,
        status: asDraft ? 'draft' : 'published',
        author_id: user.id,
        published_at: asDraft ? null : new Date().toISOString(),
      };

      const { data, error } = await supabase
        .from('blog_posts')
        .insert([postData])
        .select()
        .single();

      if (error) {
        console.error('Error creating post:', error);
        if (error.code === '23505') {
          alert('A post with this slug already exists. Please use a different title or edit the slug.');
        } else {
          alert('Failed to create post. Please try again.');
        }
        return;
      }

      router.push(`/admin/blog/${data.id}/edit`);
    } catch (error) {
      console.error('Error creating post:', error);
      alert('Failed to create post. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <AdminGuard>
      <AdminLayout>
        <div className="px-4 py-6 sm:px-0">
          <div className="mb-8">
            <h1 className="text-3xl font-bold text-gray-900">Create New Post</h1>
            <p className="mt-2 text-gray-600">Write and publish your blog content</p>
          </div>

          <form onSubmit={(e) => handleSubmit(e, true)} className="space-y-6">
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Main Content */}
              <div className="lg:col-span-2 space-y-6">
                {/* Title */}
                <div>
                  <label htmlFor="title" className="block text-sm font-medium text-gray-700 mb-2">
                    Title *
                  </label>
                  <input
                    type="text"
                    id="title"
                    required
                    value={formData.title}
                    onChange={(e) => handleTitleChange(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    placeholder="Enter post title..."
                  />
                </div>

                {/* Slug */}
                <div>
                  <label htmlFor="slug" className="block text-sm font-medium text-gray-700 mb-2">
                    URL Slug *
                  </label>
                  <div className="flex">
                    <span className="inline-flex items-center px-3 rounded-l-md border border-r-0 border-gray-300 bg-gray-50 text-gray-500 text-sm">
                      /blog/
                    </span>
                    <input
                      type="text"
                      id="slug"
                      required
                      value={formData.slug}
                      onChange={(e) => setFormData(prev => ({ ...prev, slug: e.target.value }))}
                      className="flex-1 px-3 py-2 border border-gray-300 rounded-r-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                      placeholder="url-slug"
                    />
                  </div>
                </div>

                {/* Content */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Content *
                  </label>
                  <RichTextEditor
                    content={formData.content}
                    onChange={(content) => setFormData(prev => ({ ...prev, content }))}
                    placeholder="Start writing your post..."
                  />
                </div>
              </div>

              {/* Sidebar */}
              <div className="space-y-6">
                {/* Publish Actions */}
                <div className="bg-white border border-gray-300 rounded-lg p-4">
                  <h3 className="text-sm font-medium text-gray-900 mb-4">Publish</h3>
                  <div className="space-y-3">
                    <button
                      type="submit"
                      disabled={loading || !formData.title.trim() || !formData.content.trim()}
                      className="w-full bg-gray-600 text-white px-4 py-2 rounded-md hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {loading ? 'Saving...' : 'Save Draft'}
                    </button>
                    <button
                      type="button"
                      onClick={(e) => handleSubmit(e, false)}
                      disabled={loading || !formData.title.trim() || !formData.content.trim()}
                      className="w-full bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {loading ? 'Publishing...' : 'Publish Now'}
                    </button>
                  </div>
                </div>

                {/* Excerpt */}
                <div className="bg-white border border-gray-300 rounded-lg p-4">
                  <label htmlFor="excerpt" className="block text-sm font-medium text-gray-900 mb-2">
                    Excerpt
                  </label>
                  <textarea
                    id="excerpt"
                    rows={3}
                    value={formData.excerpt}
                    onChange={(e) => setFormData(prev => ({ ...prev, excerpt: e.target.value }))}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm"
                    placeholder="Brief description of the post..."
                  />
                </div>

                {/* Featured Image */}
                <div className="bg-white border border-gray-300 rounded-lg p-4">
                  <label className="block text-sm font-medium text-gray-900 mb-2">
                    Featured Image
                  </label>
                  <ImageUpload
                    currentImage={formData.featuredImage}
                    onImageUploaded={(url) => setFormData(prev => ({ ...prev, featuredImage: url }))}
                  />
                  <div className="mt-3">
                    <label htmlFor="featuredImageUrl" className="block text-xs text-gray-600 mb-1">
                      Or enter image URL:
                    </label>
                    <input
                      type="url"
                      id="featuredImageUrl"
                      value={formData.featuredImage}
                      onChange={(e) => setFormData(prev => ({ ...prev, featuredImage: e.target.value }))}
                      className="w-full px-2 py-1 border border-gray-300 rounded text-xs focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
                      placeholder="https://example.com/image.jpg"
                    />
                  </div>
                </div>

                {/* Tags */}
                <div className="bg-white border border-gray-300 rounded-lg p-4">
                  <label htmlFor="tags" className="block text-sm font-medium text-gray-900 mb-2">
                    Tags
                  </label>
                  <input
                    type="text"
                    id="tags"
                    value={formData.tags}
                    onChange={(e) => setFormData(prev => ({ ...prev, tags: e.target.value }))}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm"
                    placeholder="tag1, tag2, tag3"
                  />
                  <p className="mt-1 text-xs text-gray-500">Separate tags with commas</p>
                </div>

                {/* SEO */}
                <div className="bg-white border border-gray-300 rounded-lg p-4">
                  <h3 className="text-sm font-medium text-gray-900 mb-4">SEO Settings</h3>
                  <div className="space-y-3">
                    <div>
                      <label htmlFor="metaTitle" className="block text-sm font-medium text-gray-700 mb-1">
                        Meta Title
                      </label>
                      <input
                        type="text"
                        id="metaTitle"
                        value={formData.metaTitle}
                        onChange={(e) => setFormData(prev => ({ ...prev, metaTitle: e.target.value }))}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm"
                        placeholder="SEO title (defaults to post title)"
                      />
                    </div>
                    <div>
                      <label htmlFor="metaDescription" className="block text-sm font-medium text-gray-700 mb-1">
                        Meta Description
                      </label>
                      <textarea
                        id="metaDescription"
                        rows={2}
                        value={formData.metaDescription}
                        onChange={(e) => setFormData(prev => ({ ...prev, metaDescription: e.target.value }))}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm"
                        placeholder="SEO description (defaults to excerpt)"
                      />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </form>
        </div>
      </AdminLayout>
    </AdminGuard>
  );
}