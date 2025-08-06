import { supabase } from "@/lib/supabase";
import { NextResponse } from "next/server";

export async function GET() {
  const { data, error } = await supabase.rpc("heartbeat");
  return NextResponse.json({ ok: !error && data === true });
}
