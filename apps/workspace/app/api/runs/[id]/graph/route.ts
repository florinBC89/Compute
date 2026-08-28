import { NextResponse } from "next/server";
import { authorizedFetch } from "@/lib/api";

export async function GET(_req: Request, { params }: { params: { id: string } }) {
  const response = await authorizedFetch(`/workspace/runs/${params.id}/graph`);
  const data = await response.json();
  return NextResponse.json(data, { status: response.status });
}
