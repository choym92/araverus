import { NextRequest, NextResponse } from 'next/server';
import { z } from 'zod';
import { BlogService } from '@/lib/blog.service';

const blogService = new BlogService();

// GET /api/blog - Get published posts or admin posts
export async function GET(request: NextRequest) {
  try {
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
  featured_image: z.string().url().optional(),
  status: z.enum(['draft', 'published', 'scheduled']).optional(),
  tags: z.array(z.string()).optional(),
  meta_title: z.string().max(200).optional(),
  meta_description: z.string().max(500).optional(),
  publish_at: z.string().optional(),
});

// POST /api/blog - Create new blog post (admin only)
export async function POST(request: NextRequest) {
  try {
    const isAdmin = await blogService.isAdmin();
    if (!isAdmin) {
      return NextResponse.json(
        { error: 'Unauthorized' },
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

    const post = await blogService.createPost({
      ...data,
      slug
    });
    
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