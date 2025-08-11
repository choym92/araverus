import type { 
  BlogPost, 
  BlogPostWithAuthor, 
  CreateBlogPostInput, 
  UpdateBlogPostInput,
  BigIntId
} from './blog.types';
import type { SupabaseClient } from '@supabase/supabase-js';

export class BlogService {
  private supabase: SupabaseClient;
  private _adminCache?: boolean;
  private static readonly IMAGE_BUCKET = 'blog-assets';
  private static readonly IMAGE_BASE_PATH = 'blog-images';
  
  constructor(supabaseClient: SupabaseClient) {
    // Supabase client is required
    if (!supabaseClient) {
      throw new Error('BlogService requires a Supabase client instance');
    }
    this.supabase = supabaseClient;
  }

  // Check if user is admin (only choym92@gmail.com)
  async isAdmin(): Promise<boolean> {
    if (this._adminCache !== undefined) return this._adminCache;
    try {
      const { data: { user } } = await this.supabase.auth.getUser();
      if (!user) return (this._adminCache = false);
      
      // Only allow specific admin email
      if (user.email !== 'choym92@gmail.com') {
        return (this._adminCache = false);
      }

      const { data: profile, error } = await this.supabase
        .from('user_profiles')
        .select('role')
        .eq('id', user.id)
        .single();

      if (error) {
        // If no profile exists yet, create one for admin email
        if (user.email === 'choym92@gmail.com') {
          await this.supabase
            .from('user_profiles')
            .upsert({
              id: user.id,
              email: user.email,
              role: 'admin',
              created_at: new Date().toISOString(),
              updated_at: new Date().toISOString()
            }, {
              onConflict: 'id'
            });
          return (this._adminCache = true);
        }
        return (this._adminCache = false);
      }
      return (this._adminCache = profile?.role === 'admin');
    } catch {
      return (this._adminCache = false);
    }
  }

  // Create new blog post
  async createPost(input: CreateBlogPostInput): Promise<BlogPost | null> {
    try {
      const { data: { user } } = await this.supabase.auth.getUser();
      if (!user) throw new Error('Not authenticated');

      const isAdmin = await this.isAdmin();
      if (!isAdmin) throw new Error('Not authorized');

      const nowIso = new Date().toISOString();
      const isPublishNow = input.status === 'published';
      const published_at = isPublishNow ? nowIso : input.publish_at || null;

      const row = {
        ...input,
        author_id: user.id,
        published_at,
        tags: input.tags ? input.tags.join(',') : null, // Convert array to string for DB
      };
      delete (row as Record<string, unknown>).publish_at;

      const { data, error } = await this.supabase
        .from('blog_posts')
        .insert(row)
        .select()
        .single();

      if (error) throw error;
      
      // Convert tags back to array
      if (data && typeof data.tags === 'string') {
        data.tags = data.tags.split(',').filter(Boolean);
      }
      
      return data as BlogPost;
    } catch (error) {
      console.error('Error creating blog post:', error);
      return null;
    }
  }

  // Update existing blog post
  async updatePost(input: UpdateBlogPostInput): Promise<BlogPost | null> {
    try {
      const isAdmin = await this.isAdmin();
      if (!isAdmin) throw new Error('Not authorized');

      const updates: Record<string, unknown> = { 
        ...input, 
        updated_at: new Date().toISOString(),
        tags: input.tags ? input.tags.join(',') : undefined
      };
      delete updates.id;
      delete updates.publish_at;

      if (input.status === 'published') {
        const { data: existing } = await this.supabase
          .from('blog_posts')
          .select('published_at')
          .eq('id', input.id)
          .single();

        if (!existing?.published_at) {
          updates.published_at = input.publish_at || new Date().toISOString();
        }
      } else if (input.status === 'scheduled' && input.publish_at) {
        updates.published_at = input.publish_at;
      }

      const { data, error } = await this.supabase
        .from('blog_posts')
        .update(updates)
        .eq('id', input.id)
        .select()
        .single();

      if (error) throw error;
      
      // Convert tags back to array
      if (data && typeof data.tags === 'string') {
        data.tags = data.tags.split(',').filter(Boolean);
      }
      
      return data as BlogPost;
    } catch (error) {
      console.error('Error updating blog post:', error);
      return null;
    }
  }

  // Get single blog post by slug (public)
  async getPostBySlug(slug: string): Promise<BlogPostWithAuthor | null> {
    try {
      const { data, error } = await this.supabase
        .from('blog_posts')
        .select(`
          *,
          author:user_profiles(*)
        `)
        .eq('slug', slug)
        .eq('status', 'published')
        .lte('published_at', new Date().toISOString())
        .single();

      if (error) throw error;

      // Increment view count (non-blocking)
      void this.supabase
        .from('blog_posts')
        .update({ view_count: ((data as BlogPost).view_count || 0) + 1 })
        .eq('id', (data as BlogPost).id);

      // Convert tags to array
      if (data && typeof data.tags === 'string') {
        data.tags = data.tags.split(',').filter(Boolean);
      }

      return data as BlogPostWithAuthor;
    } catch (error) {
      console.error('Error fetching blog post:', error);
      return null;
    }
  }

  // Get all published blog posts (public, paginated)
  async getPublishedPosts(
    page = 1, 
    limit = 10
  ): Promise<{ posts: BlogPostWithAuthor[]; total: number }> {
    try {
      const start = (page - 1) * limit;
      const end = start + limit - 1;

      const { data, error, count } = await this.supabase
        .from('blog_posts')
        .select(`
          *,
          author:user_profiles(*)
        `, { count: 'exact' })
        .eq('status', 'published')
        .lte('published_at', new Date().toISOString())
        .order('published_at', { ascending: false })
        .range(start, end);

      if (error) throw error;

      // Convert tags to array for each post
      const posts = (data || []).map(post => {
        if (typeof post.tags === 'string') {
          post.tags = post.tags.split(',').filter(Boolean);
        }
        return post;
      });

      return {
        posts: posts as BlogPostWithAuthor[],
        total: count || 0
      };
    } catch (error) {
      console.error('Error fetching blog posts:', error);
      return { posts: [], total: 0 };
    }
  }

  // Get all posts for admin (including drafts)
  async getAdminPosts(): Promise<BlogPostWithAuthor[]> {
    try {
      const isAdmin = await this.isAdmin();
      if (!isAdmin) throw new Error('Not authorized');

      const { data, error } = await this.supabase
        .from('blog_posts')
        .select(`
          *,
          author:user_profiles(*)
        `)
        .order('created_at', { ascending: false });

      if (error) throw error;
      
      // Convert tags to array for each post
      const posts = (data || []).map(post => {
        if (typeof post.tags === 'string') {
          post.tags = post.tags.split(',').filter(Boolean);
        }
        return post;
      });

      return posts as BlogPostWithAuthor[];
    } catch (error) {
      console.error('Error fetching admin posts:', error);
      return [];
    }
  }

  // Delete blog post
  async deletePost(id: BigIntId): Promise<boolean> {
    try {
      const isAdmin = await this.isAdmin();
      if (!isAdmin) throw new Error('Not authorized');

      // Delete associated assets first
      await this.supabase
        .from('blog_assets')
        .delete()
        .eq('blog_post_id', id);

      const { error } = await this.supabase
        .from('blog_posts')
        .delete()
        .eq('id', id);

      if (error) throw error;
      return true;
    } catch (error) {
      console.error('Error deleting blog post:', error);
      return false;
    }
  }

  // Upload image to Supabase Storage
  async uploadImage(
    file: File,
    postId: BigIntId,
    type: 'banner' | 'content'
  ): Promise<string | null> {
    try {
      const isAdmin = await this.isAdmin();
      if (!isAdmin) throw new Error('Not authorized');

      const ext = file.name.includes('.') ? file.name.split('.').pop() : 'bin';
      const fileName = `${Date.now()}-${Math.random().toString(36).substr(2, 9)}.${ext}`;
      const filePath = `${BlogService.IMAGE_BASE_PATH}/${type}/${postId}/${fileName}`;

      const { error: uploadError } = await this.supabase.storage
        .from(BlogService.IMAGE_BUCKET)
        .upload(filePath, file, {
          upsert: false,
          cacheControl: '3600',
        });

      if (uploadError) throw uploadError;

      const { data: pub } = this.supabase.storage
        .from(BlogService.IMAGE_BUCKET)
        .getPublicUrl(filePath);

      const assetRow = {
        blog_post_id: postId,
        file_path: filePath,
        file_name: fileName,
        file_size: file.size,
        mime_type: file.type,
        alt_text: type === 'banner' ? 'Blog banner image' : null,
      };

      const { error: assetErr } = await this.supabase
        .from('blog_assets')
        .insert(assetRow);

      if (assetErr) console.error('Asset record error:', assetErr);

      return pub.publicUrl ?? null;
    } catch (error) {
      console.error('Error uploading image:', error);
      return null;
    }
  }

  // Generate unique slug from title
  async generateSlug(title: string): Promise<string> {
    const base = title
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '');

    const baseSlug = base || 'post';
    let suffix = 0;

    for (let i = 0; i < 20; i++) {
      const candidate = suffix === 0 ? baseSlug : `${baseSlug}-${suffix}`;
      const { data, error } = await this.supabase
        .from('blog_posts')
        .select('id')
        .eq('slug', candidate)
        .limit(1);

      if (error) break;
      if (!data || data.length === 0) return candidate;
      suffix++;
    }

    return `${baseSlug}-${Date.now().toString(36)}`;
  }

  // Auto-save draft
  async autoSaveDraft(postId: BigIntId, content: string): Promise<boolean> {
    try {
      const isAdmin = await this.isAdmin();
      if (!isAdmin) return false;

      const { error } = await this.supabase
        .from('blog_posts')
        .update({ 
          content,
          updated_at: new Date().toISOString() 
        })
        .eq('id', postId)
        .eq('status', 'draft');

      return !error;
    } catch {
      return false;
    }
  }

  // Get post for editing (admin only)
  async getPostForEdit(id: BigIntId): Promise<BlogPost | null> {
    try {
      const isAdmin = await this.isAdmin();
      if (!isAdmin) throw new Error('Not authorized');

      const { data, error } = await this.supabase
        .from('blog_posts')
        .select('*')
        .eq('id', id)
        .single();

      if (error) throw error;
      
      // Convert tags to array
      if (data && typeof data.tags === 'string') {
        data.tags = data.tags.split(',').filter(Boolean);
      }

      return data as BlogPost;
    } catch (error) {
      console.error('Error fetching post for edit:', error);
      return null;
    }
  }

  // Sanitize HTML content for safe display
  sanitizeHtml(content: string): string {
    // This would use DOMPurify in production
    // For now, return as-is (implement proper sanitization)
    return content;
  }
}