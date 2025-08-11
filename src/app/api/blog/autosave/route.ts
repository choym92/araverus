import { NextRequest, NextResponse } from 'next/server';
import { z } from 'zod';
import { BlogService } from '@/lib/blog.service';
import { createClient } from '@/lib/supabase-server';

// 입력 검증 스키마
const AutoSaveSchema = z.object({
  postId: z.coerce.number().int().positive(),
  content: z.string().min(0).max(500_000), // 500KB 가드(원하면 조절)
});

// POST /api/blog/autosave - Auto-save draft content
export async function POST(request: NextRequest) {
  try {
    const supabase = await createClient();
    const blogService = new BlogService(supabase);
    
    const isAdmin = await blogService.isAdmin();
    if (!isAdmin) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    const json = await request.json().catch(() => null);
    if (!json) {
      return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 });
    }

    const parsed = AutoSaveSchema.safeParse(json);
    if (!parsed.success) {
      return NextResponse.json(
        { error: 'Validation failed', issues: parsed.error.flatten() },
        { status: 400 }
      );
    }
    const { postId, content } = parsed.data;

    // 초안 상태에서만 저장 (서비스 레이어도 eq('status','draft')로 방어 중)
    const ok = await blogService.autoSaveDraft(postId, content);

    // 저장 성공/실패를 일관 응답으로 반환
    return NextResponse.json(
      {
        success: ok,
        postId,
        savedAt: new Date().toISOString(),
      },
      { status: ok ? 200 : 409 } // 409: 상태·경합 등으로 저장 거절시
    );
  } catch (error) {
    console.error('POST /api/blog/autosave error:', error);
    return NextResponse.json({ error: 'Failed to auto-save' }, { status: 500 });
  }
}