'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/hooks/useAuth';
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Image from '@tiptap/extension-image';
import Link from '@tiptap/extension-link';
import { Loader2 } from 'lucide-react';

export default function WriteBlogPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  
  // Form state
  const [title, setTitle] = useState('');
  const [slug, setSlug] = useState('');
  const [excerpt, setExcerpt] = useState('');
  const [featuredImage, setFeaturedImage] = useState('');
  const [tags, setTags] = useState('');
  const [metaTitle, setMetaTitle] = useState('');
  const [metaDescription, setMetaDescription] = useState('');
  const [status, setStatus] = useState<'draft' | 'published'>('draft');
  
  // UI state
  const [isSaving, setIsSaving] = useState(false);
  const [postId, setPostId] = useState<number | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);

  // Initialize Tiptap editor
  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        heading: {
          levels: [1, 2, 3]
        }
      }),
      Image,
      Link.configure({
        openOnClick: false,
      })
    ],
    content: '',
    editorProps: {
      attributes: {
        class: 'prose prose-lg max-w-none focus:outline-none min-h-[400px] px-4 py-3'
      }
    }
  });

  // Check if user is admin (only choym92@gmail.com)
  useEffect(() => {
    if (!authLoading) {
      if (!user || user.email !== 'choym92@gmail.com') {
        router.push('/blog');
      }
    }
  }, [user, authLoading, router]);

  // Auto-generate slug from title
  const generateSlug = useCallback(() => {
    if (title && !slug) {
      const newSlug = title
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-+|-+$/g, '');
      setSlug(newSlug);
    }
  }, [title, slug]);

  // Handle save
  const handleSave = async () => {
    setSaveError(null);
    
    if (!title || !editor?.getHTML()) {
      setSaveError('Title and content are required');
      return;
    }

    if (!slug) {
      setSaveError('Slug is required');
      return;
    }

    setIsSaving(true);
    
    try {
      const body = {
        title,
        slug,
        content: editor.getHTML(),
        excerpt: excerpt || '',
        featured_image: featuredImage || null,
        tags: tags ? tags.split(',').map(t => t.trim()).filter(Boolean) : [],
        meta_title: metaTitle || title,
        meta_description: metaDescription || excerpt,
        status
      };

      let res;
      if (postId) {
        res = await fetch(`/api/blog/${postId}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body)
        });
      } else {
        res = await fetch('/api/blog', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body)
        });
      }

      if (!res.ok) {
        const data = await res.json().catch(() => ({ error: 'Failed to save' }));
        throw new Error(data.error || 'Failed to save post');
      }
      
      const data = await res.json();
      if (!postId && data.post) {
        setPostId(data.post.id);
      }
      
      // Redirect if published
      if (status === 'published') {
        router.push(`/blog/${slug}`);
      } else {
        setSaveError(null);
        alert('Draft saved successfully!');
      }
    } catch (error) {
      console.error('Save error:', error);
      setSaveError(error instanceof Error ? error.message : 'Failed to save post');
    } finally {
      setIsSaving(false);
    }
  };

  // Upload image handler
  const handleImageUpload = async (file: File): Promise<string> => {
    if (!postId) {
      throw new Error('Please save the post first');
    }

    const formData = new FormData();
    formData.append('file', file);
    formData.append('postId', String(postId));
    formData.append('type', 'content');

    const res = await fetch('/api/blog/upload', {
      method: 'POST',
      body: formData
    });

    if (!res.ok) {
      throw new Error('Failed to upload image');
    }

    const data = await res.json();
    return data.url;
  };

  if (authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="animate-spin h-8 w-8" />
      </div>
    );
  }

  if (!user || user.email !== 'choym92@gmail.com') {
    return null;
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b">
        <div className="max-w-4xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <h1 className="text-2xl font-semibold">Write Blog Post</h1>
            <div className="flex items-center gap-3">
              <select
                value={status}
                onChange={(e) => setStatus(e.target.value as 'draft' | 'published')}
                className="px-3 py-2 border rounded-md text-sm"
              >
                <option value="draft">Draft</option>
                <option value="published">Published</option>
              </select>
              <button
                onClick={handleSave}
                disabled={isSaving || !title || !editor?.getHTML()}
                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isSaving ? (
                  <>
                    <Loader2 className="inline-block animate-spin h-4 w-4 mr-2" />
                    Saving...
                  </>
                ) : (
                  'Save'
                )}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-4xl mx-auto px-4 py-8">
        {saveError && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 text-red-700 rounded-md">
            {saveError}
          </div>
        )}

        <div className="bg-white rounded-lg shadow-sm">
          <div className="p-6 space-y-6">
            {/* Title */}
            <div>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                onBlur={generateSlug}
                placeholder="Post title"
                className="w-full text-3xl font-bold border-0 focus:outline-none focus:ring-0 placeholder-gray-400"
              />
            </div>

            {/* Slug */}
            <div>
              <input
                type="text"
                value={slug}
                onChange={(e) => setSlug(e.target.value)}
                placeholder="post-url-slug"
                className="w-full text-sm text-gray-600 border-0 focus:outline-none focus:ring-0 placeholder-gray-400"
              />
            </div>

            {/* Excerpt */}
            <div>
              <textarea
                value={excerpt}
                onChange={(e) => setExcerpt(e.target.value)}
                placeholder="Brief description (optional)"
                rows={2}
                className="w-full border-0 focus:outline-none focus:ring-0 placeholder-gray-400 resize-none"
              />
            </div>

            {/* Editor Toolbar */}
            {editor && (
              <div className="border-y py-2 flex flex-wrap gap-1">
                <button
                  onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()}
                  className={`px-3 py-1 rounded ${
                    editor.isActive('heading', { level: 1 }) ? 'bg-gray-200' : 'hover:bg-gray-100'
                  }`}
                >
                  H1
                </button>
                <button
                  onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}
                  className={`px-3 py-1 rounded ${
                    editor.isActive('heading', { level: 2 }) ? 'bg-gray-200' : 'hover:bg-gray-100'
                  }`}
                >
                  H2
                </button>
                <button
                  onClick={() => editor.chain().focus().toggleHeading({ level: 3 }).run()}
                  className={`px-3 py-1 rounded ${
                    editor.isActive('heading', { level: 3 }) ? 'bg-gray-200' : 'hover:bg-gray-100'
                  }`}
                >
                  H3
                </button>
                <div className="w-px h-6 bg-gray-300 mx-1" />
                <button
                  onClick={() => editor.chain().focus().toggleBold().run()}
                  className={`px-3 py-1 rounded font-bold ${
                    editor.isActive('bold') ? 'bg-gray-200' : 'hover:bg-gray-100'
                  }`}
                >
                  B
                </button>
                <button
                  onClick={() => editor.chain().focus().toggleItalic().run()}
                  className={`px-3 py-1 rounded italic ${
                    editor.isActive('italic') ? 'bg-gray-200' : 'hover:bg-gray-100'
                  }`}
                >
                  I
                </button>
                <button
                  onClick={() => editor.chain().focus().toggleCode().run()}
                  className={`px-3 py-1 rounded font-mono text-sm ${
                    editor.isActive('code') ? 'bg-gray-200' : 'hover:bg-gray-100'
                  }`}
                >
                  {'</>'}
                </button>
                <div className="w-px h-6 bg-gray-300 mx-1" />
                <button
                  onClick={() => editor.chain().focus().toggleBulletList().run()}
                  className={`px-3 py-1 rounded ${
                    editor.isActive('bulletList') ? 'bg-gray-200' : 'hover:bg-gray-100'
                  }`}
                >
                  • List
                </button>
                <button
                  onClick={() => editor.chain().focus().toggleOrderedList().run()}
                  className={`px-3 py-1 rounded ${
                    editor.isActive('orderedList') ? 'bg-gray-200' : 'hover:bg-gray-100'
                  }`}
                >
                  1. List
                </button>
                <button
                  onClick={() => editor.chain().focus().toggleBlockquote().run()}
                  className={`px-3 py-1 rounded ${
                    editor.isActive('blockquote') ? 'bg-gray-200' : 'hover:bg-gray-100'
                  }`}
                >
                  &quot; Quote
                </button>
                <div className="w-px h-6 bg-gray-300 mx-1" />
                <button
                  onClick={() => {
                    const url = window.prompt('URL:');
                    if (url) {
                      editor.chain().focus().extendMarkRange('link').setLink({ href: url }).run();
                    }
                  }}
                  className={`px-3 py-1 rounded ${
                    editor.isActive('link') ? 'bg-gray-200' : 'hover:bg-gray-100'
                  }`}
                >
                  Link
                </button>
                <button
                  onClick={() => {
                    const url = window.prompt('Image URL:');
                    if (url) {
                      editor.chain().focus().setImage({ src: url }).run();
                    }
                  }}
                  className="px-3 py-1 rounded hover:bg-gray-100"
                >
                  Image
                </button>
              </div>
            )}

            {/* Editor Content */}
            <div className="min-h-[400px]">
              <EditorContent editor={editor} />
            </div>

            {/* Tags */}
            <div className="border-t pt-6">
              <input
                type="text"
                value={tags}
                onChange={(e) => setTags(e.target.value)}
                placeholder="Tags (comma separated)"
                className="w-full border-0 focus:outline-none focus:ring-0 placeholder-gray-400"
              />
            </div>

            {/* SEO Fields */}
            <div className="border-t pt-6 space-y-4">
              <h3 className="text-sm font-medium text-gray-700">SEO Settings</h3>
              <input
                type="text"
                value={metaTitle}
                onChange={(e) => setMetaTitle(e.target.value)}
                placeholder="SEO Title (optional)"
                className="w-full border-0 focus:outline-none focus:ring-0 placeholder-gray-400"
              />
              <textarea
                value={metaDescription}
                onChange={(e) => setMetaDescription(e.target.value)}
                placeholder="SEO Description (optional)"
                rows={2}
                className="w-full border-0 focus:outline-none focus:ring-0 placeholder-gray-400 resize-none"
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}