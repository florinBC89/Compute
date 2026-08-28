import { authorizedFetch } from "@/lib/api";

// SSE has to be proxied server-side, not called directly from the browser
// via EventSource: the API authenticates with a bearer token, and the
// native EventSource API can't set custom headers. This route forwards the
// signed-in user's Supabase token (authorizedFetch) and pipes the upstream
// stream straight through.
export const dynamic = "force-dynamic";

export async function GET(_req: Request, { params }: { params: { id: string } }) {
  const upstream = await authorizedFetch(`/jobs/${params.id}/events`);

  if (!upstream.ok || !upstream.body) {
    return new Response(JSON.stringify({ error: "job events unavailable" }), {
      status: upstream.status || 502,
      headers: { "Content-Type": "application/json" },
    });
  }

  return new Response(upstream.body, {
    status: 200,
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}
