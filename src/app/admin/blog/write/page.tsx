'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/hooks/useAuth';
import TiptapEditor from '@/components/TiptapEditor';
import { Loader2, Save, Eye, X } from 'lucide-react';

export default function WriteBlogPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  
  // Form state
  const [title, setTitle] = useState('');
  const [slug, setSlug] = useState('');
  const [content, setContent] = useState('');
  const [excerpt, setExcerpt] = useState('');
  const [featuredImage, setFeaturedImage] = useState('');
  const [tags, setTags] = useState('');
  const [metaTitle, setMetaTitle] = useState('');
  const [metaDescription, setMetaDescription] = useState('');
  const [status, setStatus] = useState<'draft' | 'published'>('draft');
  
  // UI state
  const [isSaving, setIsSaving] = useState(false);
  const [isAdmin, setIsAdmin] = useState(false);
  const [postId, setPostId] = useState<number | null>(null);
  const [lastSaved, setLastSaved] = useState<Date | null>(null);
  const [showPreview, setShowPreview] = useState(false);

  // Check admin status - Only allow choym92@gmail.com
  useEffect(() => {
    const setupAdmin = async () => {
      if (!user) return;
      
      // Only allow specific admin email
      if (user.email !== 'choym92@gmail.com') {
        console.log('Access denied: Not admin email');
        router.push('/blog');
        return;
      }
      
      try {
        const { createClient } = await import('@/lib/supabase');
        const supabase = createClient();
        
        // Ensure admin profile exists
        const { error: profileError } = await supabase
          .from('user_profiles')
          .upsert({
            id: user.id,
            email: user.email,
            role: 'admin',
            full_name: user.user_metadata?.full_name || user.email?.split('@')[0] || 'Admin',
            avatar_url: user.user_metadata?.avatar_url || user.user_metadata?.picture,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString()
          }, {
            onConflict: 'id'
          });
        
        if (profileError) {
          console.error('Failed to set admin role:', profileError);
          // Try update only
          const { error: retryError } = await supabase
            .from('user_profiles')
            .update({
              role: 'admin',
              updated_at: new Date().toISOString()
            })
            .eq('id', user.id);
            
          if (!retryError) {
            console.log('Admin role updated successfully');
            setIsAdmin(true);
          }
        } else {
          console.log('Admin role set successfully');
          setIsAdmin(true);
        }
      } catch (error) {
        console.error('Setup error:', error);
      }
    };

    if (!authLoading && user) {
      setupAdmin();
    } else if (!authLoading && !user) {
      router.push('/login');
    }
  }, [user, authLoading, router]);

  // Auto-generate slug from title only when slug is completely empty
  useEffect(() => {
    if (title && slug === '') {
      const autoSlug = title
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-+|-+$/g, '');
      setSlug(autoSlug);
    }
  }, [title]); // Remove slug from dependencies to prevent loop

  // Auto-save draft
  useEffect(() => {
    if (!postId || status !== 'draft') return;
    
    const timer = setTimeout(async () => {
      try {
        await fetch('/api/blog/autosave', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ postId, content })
        });
        setLastSaved(new Date());
      } catch (error) {
        console.error('Auto-save failed:', error);
      }
    }, 5000);

    return () => clearTimeout(timer);
  }, [content, postId, status]);

  const handleSave = async () => {
    if (!title || !content) {
      alert('Title and content are required');
      return;
    }

    if (!slug) {
      alert('Slug is required');
      return;
    }

    setIsSaving(true);
    try {
      const body = {
        title,
        slug,
        content,
        excerpt: excerpt || '',
        featured_image: featuredImage || null,
        tags: tags ? tags.split(',').map(t => t.trim()).filter(Boolean) : [],
        meta_title: metaTitle || '',
        meta_description: metaDescription || '',
        status
      };

      console.log('Saving post:', body);

      let res;
      if (postId) {
        // Update existing post
        res = await fetch(`/api/blog/${postId}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body)
        });
      } else {
        // Create new post
        res = await fetch('/api/blog', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body)
        });
      }

      const responseText = await res.text();
      console.log('Response:', res.status, responseText);

      if (!res.ok) {
        let errorMessage = 'Failed to save post';
        try {
          const errorData = JSON.parse(responseText);
          errorMessage = errorData.error || errorMessage;
        } catch {
          // Use default error message
        }
        throw new Error(errorMessage);
      }
      
      const data = JSON.parse(responseText);
      if (!postId && data.post) {
        setPostId(data.post.id);
        alert('Post created successfully! You can now upload images.');
      } else {
        alert('Post saved successfully!');
      }
      
      setLastSaved(new Date());
      
      if (status === 'published') {
        setTimeout(() => {
          router.push(`/blog/${slug}`);
        }, 1000);
      }
    } catch (error) {
      console.error('Save error:', error);
      alert(error instanceof Error ? error.message : 'Failed to save post');
    } finally {
      setIsSaving(false);
    }
  };

  const handleImageUpload = async (file: File): Promise<string> => {
    if (!postId) {
      alert('Please save the post first before uploading images');
      throw new Error('No post ID');
    }

    console.log('Uploading image:', file.name, 'for post:', postId);

    const fd = new FormData();
    fd.set('file', file);
    fd.set('postId', String(postId));
    fd.set('type', 'content');

    try {
      const res = await fetch('/api/blog/upload', {
        method: 'POST',
        body: fd
      });

      const responseText = await res.text();
      console.log('Upload response:', res.status, responseText);

      if (!res.ok) {
        let errorMessage = 'Upload failed';
        try {
          const errorData = JSON.parse(responseText);
          errorMessage = errorData.error || errorMessage;
        } catch {
          // Use default error message
        }
        throw new Error(errorMessage);
      }

      const data = JSON.parse(responseText);
      console.log('Image uploaded successfully:', data.url);
      return data.url;
    } catch (error) {
      console.error('Image upload error:', error);
      alert(error instanceof Error ? error.message : 'Failed to upload image');
      throw error;
    }
  };

  const handleBannerUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    
    if (!postId) {
      alert('Please save the post first before uploading images');
      e.target.value = ''; // Reset file input
      return;
    }

    console.log('Uploading banner:', file.name, 'for post:', postId);

    const fd = new FormData();
    fd.set('file', file);
    fd.set('postId', String(postId));
    fd.set('type', 'banner');

    try {
      const res = await fetch('/api/blog/upload', {
        method: 'POST',
        body: fd
      });

      const responseText = await res.text();
      console.log('Banner upload response:', res.status, responseText);

      if (!res.ok) {
        let errorMessage = 'Upload failed';
        try {
          const errorData = JSON.parse(responseText);
          errorMessage = errorData.error || errorMessage;
        } catch {
          // Use default error message
        }
        throw new Error(errorMessage);
      }

      const data = JSON.parse(responseText);
      setFeaturedImage(data.url);
      console.log('Banner uploaded successfully:', data.url);
      alert('Banner image uploaded successfully!');
    } catch (error) {
      console.error('Banner upload error:', error);
      alert(error instanceof Error ? error.message : 'Failed to upload banner image');
      e.target.value = ''; // Reset file input on error
    }
  };

  if (authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="animate-spin h-8 w-8" />
      </div>
    );
  }

  if (!user) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-gray-600">Redirecting to login...</p>
      </div>
    );
  }

  if (!isAdmin) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="animate-spin h-8 w-8 mx-auto mb-4" />
          <p className="text-gray-600">Setting up admin access...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <h1 className="text-xl font-semibold">Write Blog Post</h1>
            
            <div className="flex items-center gap-4">
              {lastSaved && (
                <span className="text-sm text-gray-500">
                  Saved {lastSaved.toLocaleTimeString()}
                </span>
              )}
              
              <button
                onClick={() => setShowPreview(!showPreview)}
                className="px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 rounded-md flex items-center gap-2"
              >
                {showPreview ? <X size={16} /> : <Eye size={16} />}
                {showPreview ? 'Edit' : 'Preview'}
              </button>
              
              <select
                value={status}
                onChange={(e) => setStatus(e.target.value as 'draft' | 'published')}
                className="px-3 py-2 border border-gray-300 rounded-md text-sm"
              >
                <option value="draft">Draft</option>
                <option value="published">Published</option>
              </select>
              
              <button
                onClick={handleSave}
                disabled={isSaving || !title || !content}
                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {isSaving ? (
                  <Loader2 size={16} className="animate-spin" />
                ) : (
                  <Save size={16} />
                )}
                {isSaving ? 'Saving...' : 'Save'}
              </button>
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Main Content */}
          <div className="lg:col-span-2 space-y-6">
            {/* Title */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Title *
              </label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Enter post title"
              />
            </div>

            {/* Slug */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Slug
              </label>
              <input
                type="text"
                value={slug}
                onChange={(e) => setSlug(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="post-url-slug"
              />
            </div>

            {/* Content Editor */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Content *
              </label>
              {showPreview ? (
                <div className="prose prose-lg max-w-none p-6 bg-white rounded-lg border border-gray-200">
                  <div dangerouslySetInnerHTML={{ __html: content }} />
                </div>
              ) : (
                <TiptapEditor
                  content={content}
                  onChange={setContent}
                  onImageUpload={postId ? handleImageUpload : undefined}
                />
              )}
            </div>
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            {/* Featured Image */}
            <div className="bg-white p-6 rounded-lg border border-gray-200">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Featured Image
              </label>
              {featuredImage && (
                <img
                  src={featuredImage}
                  alt="Featured"
                  className="w-full h-40 object-cover rounded-md mb-4"
                />
              )}
              <input
                type="file"
                accept="image/*"
                onChange={handleBannerUpload}
                disabled={!postId}
                className="w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100 disabled:opacity-50"
              />
              {!postId && (
                <p className="text-xs text-gray-500 mt-2">
                  Save the post first to upload images
                </p>
              )}
            </div>

            {/* Excerpt */}
            <div className="bg-white p-6 rounded-lg border border-gray-200">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Excerpt
              </label>
              <textarea
                value={excerpt}
                onChange={(e) => setExcerpt(e.target.value)}
                rows={3}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Brief description of the post"
              />
            </div>

            {/* Tags */}
            <div className="bg-white p-6 rounded-lg border border-gray-200">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Tags
              </label>
              <input
                type="text"
                value={tags}
                onChange={(e) => setTags(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="tag1, tag2, tag3"
              />
            </div>

            {/* SEO */}
            <div className="bg-white p-6 rounded-lg border border-gray-200">
              <h3 className="text-sm font-medium text-gray-700 mb-4">SEO Settings</h3>
              
              <div className="space-y-4">
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">
                    Meta Title
                  </label>
                  <input
                    type="text"
                    value={metaTitle}
                    onChange={(e) => setMetaTitle(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                    placeholder="SEO title"
                  />
                </div>
                
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">
                    Meta Description
                  </label>
                  <textarea
                    value={metaDescription}
                    onChange={(e) => setMetaDescription(e.target.value)}
                    rows={2}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                    placeholder="SEO description"
                  />
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}