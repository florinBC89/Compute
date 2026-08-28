import { createBrowserClient } from "@supabase/ssr";

// One client per call site is intentional here (matches @supabase/ssr's own
// guidance) -- each call reads fresh cookies rather than risking a stale
// module-level singleton across navigations.
export function createClient() {
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!,
  );
}
