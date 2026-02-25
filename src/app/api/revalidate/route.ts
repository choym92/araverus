import { revalidatePath } from "next/cache";
import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  const secret = request.headers.get("x-revalidation-secret");

  if (!secret || secret !== process.env.REVALIDATION_SECRET) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  revalidatePath("/news");
  revalidatePath("/news/[slug]", "page");

  return NextResponse.json({
    revalidated: true,
    paths: ["/news", "/news/[slug]"],
    timestamp: new Date().toISOString(),
  });
}
