import { getMe } from "@/lib/api";
import TaskRunner from "@/components/TaskRunner";
import { signOut } from "./actions";

export const dynamic = "force-dynamic";

// Phases 2-3 (V0.2 human workspace): a protected shell (GET /v1/me) plus a
// task runner proving the job/worker/SSE plumbing against the stub
// pipeline. The project tree and a real result screen are later phases,
// once the real research pipeline (Phase 4+) gives them real data to show.
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

      <TaskRunner />
    </div>
  );
}
