import { NextResponse } from "next/server";
import { authorizedFetch } from "@/lib/api";

export async function POST(req: Request, { params }: { params: { id: string } }) {
  const body = await req.json();
  const response = await authorizedFetch(`/workspace/runs/${params.id}/preview-model-switch`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await response.json();
  return NextResponse.json(data, { status: response.status });
}
