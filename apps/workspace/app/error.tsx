"use client";

import { useEffect } from "react";

// Phase 10 (V0.2 human workspace): catches a failed server-side fetch (e.g.
// getMe() or getProjectArtifacts() hitting a down API, an expired session,
// or any other unhandled error while rendering a page) so it renders this
// app's own on-brand error state instead of Next.js's default error page.
export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // No analytics/logging pipeline exists yet for apps/workspace -- this
    // at least keeps the failure visible in the server console during dev
    // and in Railway's logs in production, matching how app.worker logs
    // failures on the backend.
    console.error("apps/workspace render error:", error);
  }, [error]);

  return (
    <div className="mt-8 rounded-card border border-border bg-surface p-8 text-center">
      <p className="text-[14px] text-ink">Something went wrong loading this page.</p>
      <button
        type="button"
        onClick={() => reset()}
        className="mt-4 rounded-pill bg-accent px-5 py-2.5 text-[14px] font-semibold text-white"
      >
        Try again
      </button>
    </div>
  );
}
