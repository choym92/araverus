import { NextRequest, NextResponse } from 'next/server';
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
    
    // Validate required fields
    if (!body.title || !body.content) {
      return NextResponse.json(
        { error: 'Title and content are required' },
        { status: 400 }
      );
    }

    // Generate slug if not provided
    if (!body.slug) {
      body.slug = await blogService.generateSlug(body.title);
    }

    const post = await blogService.createPost(body);
    
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