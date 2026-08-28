import { createClient } from "@/lib/supabase/server";

export interface ProjectSummary {
  id: string;
  name: string;
  slug: string;
}

export interface Me {
  user_id: string;
  email: string;
  workspace_id: string;
  workspace_name: string;
  projects: ProjectSummary[];
}

const API_URL = process.env.COMPUTELAYER_API_URL ?? "http://localhost:8000/v1";

// Server-side only: forwards the signed-in user's own Supabase access token
// as the bearer token, so the API's resolve_user_scope verifies it exactly
// as it would any other Supabase session (see apps/api/app/services/user_scope.py).
async function authorizedFetch(path: string, init?: RequestInit): Promise<Response> {
  const supabase = await createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session) {
    throw new Error("no active session");
  }

  return fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      ...init?.headers,
      Authorization: `Bearer ${session.access_token}`,
    },
    cache: "no-store",
  });
}

export async function getMe(): Promise<Me> {
  const response = await authorizedFetch("/me");
  if (!response.ok) {
    throw new Error(`GET /me failed: ${response.status}`);
  }
  return response.json();
}
