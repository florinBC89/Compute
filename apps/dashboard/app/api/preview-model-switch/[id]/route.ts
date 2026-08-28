import { NextResponse } from "next/server";
import { previewModelSwitch } from "@/lib/api";

// Proxies POST /v1/runs/{id}/preview-model-switch server-side, same reasoning
// as app/api/explain/[id]/route.ts: the API key never reaches the browser.
export async function POST(req: Request, { params }: { params: { id: string } }) {
  const body = await req.json();
  try {
    const preview = await previewModelSwitch(params.id, body.target_model);
    return NextResponse.json(preview);
  } catch {
    return NextResponse.json({ error: "preview unavailable" }, { status: 502 });
  }
}
