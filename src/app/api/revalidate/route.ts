import { revalidatePath, revalidateTag } from "next/cache";
import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  const secret = request.headers.get("x-revalidation-secret");

  if (!secret || secret !== process.env.REVALIDATION_SECRET) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  revalidateTag("news");
  revalidatePath("/news");
  // Note: removed revalidatePath("/news/[slug]", "page") — it invalidates ALL article pages
  // at once (100+), causing massive cache MISS storms. Individual articles revalidate via
  // their 24h ISR TTL or revalidateTag("news") which busts unstable_cache.
  revalidatePath("/sitemap.xml");
  revalidatePath("/rss.xml");

  return NextResponse.json({
    revalidated: true,
    paths: ["/news", "/sitemap.xml", "/rss.xml"],
    tags: ["news"],
    timestamp: new Date().toISOString(),
  });
}
