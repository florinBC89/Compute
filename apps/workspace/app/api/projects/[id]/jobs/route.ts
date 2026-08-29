import { NextResponse } from "next/server";
import { authorizedFetch } from "@/lib/api";

// Proxies GET /v1/workspace/projects/{id}/jobs -- a project's turn history
// (V0.3 Phase 0), used by ChatThread to refresh the thread after a turn
// completes.
export async function GET(_req: Request, { params }: { params: { id: string } }) {
  const response = await authorizedFetch(`/workspace/projects/${params.id}/jobs`);
  const data = await response.json();
  return NextResponse.json(data, { status: response.status });
}
