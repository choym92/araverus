// ⏺ Write(src/app/api/blog/upload/route.ts)
import { NextRequest, NextResponse } from 'next/server';
import { z } from 'zod';
import { BlogService } from '@/lib/blog.service';

const blogService = new BlogService();

// --- Schemas ---
const FormSchema = z.object({
  postId: z.coerce.number().int().positive(),
  type: z.enum(['banner', 'content']).default('content'),
});

// 허용 MIME
const ALLOWED_MIME = new Set([
  'image/jpeg',
  'image/jpg',
  'image/png',
  'image/webp',
  'image/gif',
]);

// 5MB 제한
const MAX_BYTES = 5 * 1024 * 1024;

// 간단한 매직 넘버 체크 (best-effort)
function looksLikeImage(mime: string, bytes: Uint8Array): boolean {
  // JPEG: FF D8 FF
  if (mime.includes('jpeg') || mime.includes('jpg')) {
    return bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff;
  }
  // PNG: 89 50 4E 47 0D 0A 1A 0A
  if (mime.includes('png')) {
    const sig = [0x89,0x50,0x4e,0x47,0x0d,0x0a,0x1a,0x0a];
    return sig.every((v, i) => bytes[i] === v);
  }
  // GIF: "GIF87a" or "GIF89a"
  if (mime.includes('gif')) {
    const hdr = String.fromCharCode(...bytes.slice(0,6));
    return hdr === 'GIF87a' || hdr === 'GIF89a';
  }
  // WebP: RIFF....WEBP
  if (mime.includes('webp')) {
    const riff = String.fromCharCode(...bytes.slice(0,4)) === 'RIFF';
    const webp = String.fromCharCode(...bytes.slice(8,12)) === 'WEBP';
    return riff && webp;
  }
  return false;
}

// POST /api/blog/upload - Upload image for blog post
export async function POST(request: NextRequest) {
  try {
    const isAdmin = await blogService.isAdmin();
    if (!isAdmin) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    const formData = await request.formData().catch(() => null);
    if (!formData) {
      return NextResponse.json({ error: 'Invalid form data' }, { status: 400 });
    }

    const file = formData.get('file') as File | null;
    const rawPostId = formData.get('postId');
    const rawType = (formData.get('type') as string | null) ?? undefined;

    if (!file) {
      return NextResponse.json({ error: 'No file provided' }, { status: 400 });
    }

    // 기본 헤더 검증
    if (!ALLOWED_MIME.has(file.type)) {
      return NextResponse.json(
        { error: 'Invalid file type. Only JPEG/PNG/WebP/GIF are allowed.' },
        { status: 400 }
      );
    }
    if (file.size > MAX_BYTES) {
      return NextResponse.json(
        { error: 'File too large. Maximum size is 5MB.' },
        { status: 400 }
      );
    }

    // postId/type 검증
    const parsed = FormSchema.safeParse({ postId: rawPostId, type: rawType });
    if (!parsed.success) {
      return NextResponse.json(
        { error: 'Validation failed', issues: parsed.error.flatten() },
        { status: 400 }
      );
    }
    const { postId, type } = parsed.data;

    // 매직 넘버(파일 시그니처) 검사 (간단 위변조 방지)
    const buf = new Uint8Array(await file.arrayBuffer());
    if (!looksLikeImage(file.type, buf)) {
      return NextResponse.json(
        { error: 'File signature mismatch for declared image type.' },
        { status: 400 }
      );
    }

    const url = await blogService.uploadImage(file, postId, type);
    if (!url) {
      return NextResponse.json({ error: 'Failed to upload image' }, { status: 500 });
    }

    // 성공 응답 스키마 명확화
    return NextResponse.json(
      { url, postId, type },
      { status: 200, headers: { 'cache-control': 'no-store' } }
    );
  } catch (error) {
    console.error('POST /api/blog/upload error:', error);
    return NextResponse.json({ error: 'Failed to upload image' }, { status: 500 });
  }
}