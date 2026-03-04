// ─────────────────────────────────────────────────────────────
// Shared primitives
// Supabase returns ISO string timestamps; numeric ids for BIGINT,
// string for UUID. Make that explicit.
// ─────────────────────────────────────────────────────────────
export type BigIntId = number;        // blog_posts.id, etc. (bigserial)
export type Uuid = string;            // auth.users.id, etc.
export type ISODateString = string;   // '2025-08-10T12:34:56.789Z'

export type UserRole = 'admin' | 'author' | 'reader';
export type PostStatus = 'draft' | 'scheduled' | 'published' | 'archived';

// Tags: 권장은 string[] (DB에선 text[] 권장)
// 만약 현재 DB가 comma-separated string이면, API 레이어에서 직렬화/역직렬화하세요.
export type Tag = string;

// ─────────────────────────────────────────────────────────────
// BlogPost (DB 매핑)
// - id: BIGINT → number
// - author_id: UUID → string
// - timestamps: ISO string
// - nullable 가능성 반영해 안전성 ↑
// - view_count: 기본값 0 가정 (nullable 대비)
// - meta_*: optional + nullable
// - featured_image: banner 의미 명확히 주석
// ─────────────────────────────────────────────────────────────
export interface BlogPost {
  id: BigIntId;
  title: string;
  slug: string;
  // 본문은 운영에서 과정이 나뉘는 경우가 많음:
  // draft/published 이원화라면 content는 draft_body로 쓰고,
  // 공개 렌더는 published_body만 사용하도록 서비스 계층에서 분리 권장.
  content: string; // = draft_body (운영 권장 네이밍: draft_body)
  excerpt?: string | null;
  featured_image?: string | null; // banner URL
  status: PostStatus;             // 'scheduled' 포함
  author_id: Uuid;
  created_at: ISODateString;
  updated_at: ISODateString;
  published_at?: ISODateString | null;
  // 권장: text[] (TS: string[]) ; 현재가 string이라면 아래의 db_tags로 브릿지
  tags?: Tag[] | null;

  meta_title?: string | null;
  meta_description?: string | null;

  view_count: number; // default 0; nullable면 number | null 로 바꾸세요
  // 브릿지 필드(선택): 기존 DB가 comma-separated이면 API 레이어에서만 사용
  // db_tags?: string | null;
}

// 공개 뷰 전용 타입 (XSS-safe body만 가진 스냅샷)
export interface PublishedPost {
  id: BigIntId;
  title: string;
  slug: string;
  body_html: string;           // sanitize된 HTML (DOMPurify 등 서버에서 생성)
  excerpt?: string | null;
  featured_image?: string | null;
  published_at: ISODateString;
  tags?: Tag[] | null;
  meta_title?: string | null;
  meta_description?: string | null;
  view_count: number;
}

// ─────────────────────────────────────────────────────────────
// Asset
// ─────────────────────────────────────────────────────────────
export interface BlogAsset {
  id: BigIntId;
  blog_post_id: BigIntId;
  file_path: string;              // 'blog/content/{postId}/{uuid}.webp'
  file_name: string;
  file_size: number;
  mime_type: string;
  alt_text?: string | null;
  created_at: ISODateString;
}

// ─────────────────────────────────────────────────────────────
// User
// ─────────────────────────────────────────────────────────────
export interface UserProfile {
  id: Uuid;                       // auth.users.id
  email: string;
  full_name?: string | null;
  role?: UserRole | null;
  avatar_url?: string | null;
  created_at: ISODateString;
  updated_at: ISODateString;
}

export interface BlogPostWithAuthor extends BlogPost {
  author: UserProfile;
}

// ─────────────────────────────────────────────────────────────
// DTOs (서비스/API 레이어)
// - Create: 최소 필수만 받고 서버에서 author_id/초깃값 설정 권장
// - Update: 부분 업데이트 안전하게 Partial + id
// ─────────────────────────────────────────────────────────────
export interface CreateBlogPostInput {
  title: string;
  slug: string;
  content: string;               // draft_body 역할
  excerpt?: string;
  featured_image?: string;
  status?: Extract<PostStatus, 'draft' | 'scheduled' | 'published'>; // 기본 'draft'
  tags?: Tag[];                  // DB가 text[]가 아니면 API에서 직렬화
  meta_title?: string;
  meta_description?: string;
  publish_at?: ISODateString;    // 'scheduled'일 때만 사용
}

export interface UpdateBlogPostInput extends Partial<CreateBlogPostInput> {
  id: BigIntId;
}

// 발행 액션 전용 DTO (명시적 커맨드)
// - 서버에서 sanitize + published_body 스냅샷 생성하는 트리거로 사용 권장
export interface PublishPostInput {
  id: BigIntId;
  // 즉시 발행 or 지정시각 재지정
  publish_at?: ISODateString;
}
