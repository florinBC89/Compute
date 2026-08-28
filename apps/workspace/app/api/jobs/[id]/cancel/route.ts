import { NextResponse } from "next/server";
import { authorizedFetch } from "@/lib/api";

export async function POST(_req: Request, { params }: { params: { id: string } }) {
  const response = await authorizedFetch(`/jobs/${params.id}/cancel`, { method: "POST" });
  const data = await response.json();
  return NextResponse.json(data, { status: response.status });
}
