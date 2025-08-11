import { NextRequest, NextResponse } from 'next/server';
import { z } from 'zod';
import { BlogService } from '@/lib/blog.service';
import { createClient } from '@/lib/supabase-server';

// GET /api/blog - Get published posts or admin posts
export async function GET(request: NextRequest) {
  try {
    const supabase = await createClient();
    const blogService = new BlogService(supabase);
    
    const { searchParams } = new URL(request.url);
    const isAdminView = searchParams.get('admin') === 'true';
    
    if (isAdminView) {
      const isAdmin = await blogService.isAdmin();
      if (!isAdmin) {
        return NextResponse.json(
          { error: 'Unauthorized' },
          { status: 401 }
        );
      }
      
      const posts = await blogService.getAdminPosts();
      return NextResponse.json({ posts });
    }
    
    // Public view - paginated
    const page = parseInt(searchParams.get('page') || '1');
    const limit = parseInt(searchParams.get('limit') || '10');
    
    const result = await blogService.getPublishedPosts(page, limit);
    return NextResponse.json(result);
  } catch (error) {
    console.error('GET /api/blog error:', error);
    return NextResponse.json(
      { error: 'Failed to fetch posts' },
      { status: 500 }
    );
  }
}

// Validation schema for creating blog post
const CreatePostSchema = z.object({
  title: z.string().min(1).max(200),
  content: z.string().min(1),
  slug: z.string().optional(),
  excerpt: z.string().max(500).optional(),
  featured_image: z.string().optional(),
  status: z.enum(['draft', 'published', 'scheduled']).optional(),
  tags: z.array(z.string()).optional(),
  meta_title: z.string().max(200).optional(),
  meta_description: z.string().max(500).optional(),
  publish_at: z.string().optional(),
});

// POST /api/blog - Create new blog post (admin only)
export async function POST(request: NextRequest) {
  try {
    const supabase = await createClient();
    const blogService = new BlogService(supabase);
    
    const isAdmin = await blogService.isAdmin();
    if (!isAdmin) {
      return NextResponse.json(
        { error: 'Unauthorized - Admin access required' },
        { status: 401 }
      );
    }

    const body = await request.json();
    
    // Validate with zod
    const parsed = CreatePostSchema.safeParse(body);
    if (!parsed.success) {
      return NextResponse.json(
        { error: 'Validation failed', issues: parsed.error.flatten() },
        { status: 400 }
      );
    }

    const data = parsed.data;
    
    // Generate slug if not provided
    const slug = data.slug || await blogService.generateSlug(data.title);

    // Clean up null values to undefined for TypeScript compatibility
    const createData = {
      ...data,
      slug,
      featured_image: data.featured_image || undefined,
      excerpt: data.excerpt || undefined,
      meta_title: data.meta_title || undefined,
      meta_description: data.meta_description || undefined,
    };

    const post = await blogService.createPost(createData);
    
    if (!post) {
      return NextResponse.json(
        { error: 'Failed to create post' },
        { status: 500 }
      );
    }

    return NextResponse.json({ post }, { status: 201 });
  } catch (error) {
    console.error('POST /api/blog error:', error);
    return NextResponse.json(
      { error: 'Failed to create post' },
      { status: 500 }
    );
  }
}