// ⏺ Write(src/app/api/blog/[id]/route.ts)
import { NextRequest, NextResponse } from 'next/server';
import { revalidateTag } from 'next/cache';
import { z } from 'zod';
import { BlogService } from '@/lib/blog.service';

const blogService = new BlogService();

// --- Schemas ---
const IdSchema = z.coerce.number().int().min(1);

const UpdatePostSchema = z.object({
  title: z.string().min(1).max(200).optional(),
  content: z.string().min(1).optional(),
  slug: z.string().min(1).max(220).optional(),
  excerpt: z.string().max(300).optional(),
  featured_image: z.string().url().nullable().optional(),
  status: z.enum(['draft', 'scheduled', 'published', 'archived']).optional(),
  tags: z.array(z.string().min(1).max(40)).optional(),
  meta_title: z.string().max(70).optional(),
  meta_description: z.string().max(160).optional(),
  publish_at: z.string().datetime().optional(), // ISO8601 (scheduled/published에만 의미)
});

// GET /api/blog/[id] - Get single post for editing (admin only)
export async function GET(
  _request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const isAdmin = await blogService.isAdmin();
    if (!isAdmin) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

    const idRes = IdSchema.safeParse(params.id);
    if (!idRes.success) return NextResponse.json({ error: 'Invalid id' }, { status: 400 });
    const id = idRes.data;

    const post = await blogService.getPostForEdit(id);
    if (!post) return NextResponse.json({ error: 'Post not found' }, { status: 404 });

    return NextResponse.json({ post }, { status: 200 });
  } catch (error) {
    console.error('GET /api/blog/[id] error:', error);
    return NextResponse.json({ error: 'Failed to fetch post' }, { status: 500 });
  }
}

// PUT /api/blog/[id] - Update blog post (admin only)
export async function PUT(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const isAdmin = await blogService.isAdmin();
    if (!isAdmin) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

    const idRes = IdSchema.safeParse(params.id);
    if (!idRes.success) return NextResponse.json({ error: 'Invalid id' }, { status: 400 });
    const id = idRes.data;

    const json = await request.json().catch(() => null);
    if (!json) return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 });

    const parsed = UpdatePostSchema.safeParse(json);
    if (!parsed.success) {
      return NextResponse.json(
        { error: 'Validation failed', issues: parsed.error.flatten() },
        { status: 400 }
      );
    }

    // 상태/예약발행 간단 규칙 예시: scheduled이면 publish_at 필요
    if (parsed.data.status === 'scheduled' && !parsed.data.publish_at) {
      return NextResponse.json(
        { error: 'publish_at is required when status is scheduled' },
        { status: 400 }
      );
    }

    const post = await blogService.updatePost({ ...parsed.data, id });
    if (!post) return NextResponse.json({ error: 'Failed to update post' }, { status: 500 });

    try {
      revalidateTag('blog'); // 목록/상세에 tag 기반 캐시 쓰는 경우
    } catch (_) {}

    return NextResponse.json({ post }, { status: 200 });
  } catch (error) {
    console.error('PUT /api/blog/[id] error:', error);
    return NextResponse.json({ error: 'Failed to update post' }, { status: 500 });
  }
}

// DELETE /api/blog/[id] - Delete blog post (admin only)
export async function DELETE(
  _request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const isAdmin = await blogService.isAdmin();
    if (!isAdmin) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

    const idRes = IdSchema.safeParse(params.id);
    if (!idRes.success) return NextResponse.json({ error: 'Invalid id' }, { status: 400 });
    const id = idRes.data;

    const success = await blogService.deletePost(id);
    if (!success) return NextResponse.json({ error: 'Failed to delete post' }, { status: 500 });

    try {
      revalidateTag('blog');
    } catch (_) {}

    return NextResponse.json({ success: true }, { status: 200 });
  } catch (error) {
    console.error('DELETE /api/blog/[id] error:', error);
    return NextResponse.json({ error: 'Failed to delete post' }, { status: 500 });
  }
}