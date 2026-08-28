import { NextResponse } from "next/server";
import { authorizedFetch } from "@/lib/api";

// Proxies POST /v1/jobs so the browser never needs to know the API's URL or
// hold a token beyond its own Supabase session (see lib/api.ts).
export async function POST(request: Request) {
  const body = await request.json();

  const response = await authorizedFetch("/jobs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  const data = await response.json();
  return NextResponse.json(data, { status: response.status });
}
