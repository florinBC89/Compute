import { NextResponse } from "next/server";

// Proxies GET /v1/computations/{id}/explain server-side so the Why? drawer
// (a client component) never needs the API key in the browser -- it fetches
// this same-origin route instead.

const API_URL = process.env.COMPUTELAYER_API_URL;
const API_KEY = process.env.COMPUTELAYER_API_KEY;

export async function GET(_req: Request, { params }: { params: { id: string } }) {
  if (!API_URL) {
    return NextResponse.json({
      computation_id: params.id,
      name: "",
      cache_status: "MISS",
      previous_computation_id: null,
      changes: [],
    });
  }

  const response = await fetch(`${API_URL}/computations/${params.id}/explain`, {
    headers: { Authorization: `Bearer ${API_KEY}` },
    cache: "no-store",
  });

  if (!response.ok) {
    return NextResponse.json({ error: "explain unavailable" }, { status: response.status });
  }
  return NextResponse.json(await response.json());
}
