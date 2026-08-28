import { getMe } from "@/lib/api";
import { signOut } from "./actions";

export const dynamic = "force-dynamic";

// Phase 2 (V0.2 human workspace): login -> protected shell calling GET
// /v1/me, proving the Supabase session reaches the API and resolves to a
// real, auto-provisioned workspace. Task input, the project tree and the
// result screen are later phases, once the job/worker/SSE plumbing (Phase 3)
// and the real pipeline (Phase 4+) exist to back them.
export default async function HomePage() {
  const me = await getMe();

  return (
    <div>
      <div className="flex items-center justify-between">
        <h1 className="text-[20px] font-semibold text-ink">{me.workspace_name}</h1>
        <form action={signOut}>
          <button
            type="submit"
            className="text-[13px] text-ink-muted hover:text-ink"
          >
            Sign out
          </button>
        </form>
      </div>

      <div className="mt-8 rounded-card border border-border bg-surface p-8 text-center">
        <p className="text-[14px] text-ink-secondary">
          Signed in as {me.email}. Nothing to research yet.
        </p>
        <p className="mt-1 text-[13px] text-ink-muted">
          Task input is coming in a later phase of this build.
        </p>
      </div>
    </div>
  );
}
