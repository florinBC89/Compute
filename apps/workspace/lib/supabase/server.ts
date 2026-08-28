import { createServerClient, type CookieOptions } from "@supabase/ssr";
import { cookies } from "next/headers";

type CookieToSet = { name: string; value: string; options: CookieOptions };

// For use in Server Components, Server Actions and Route Handlers. The
// setAll try/catch is deliberate: a Server Component can't write cookies
// (headers are already sent), and that's fine as long as middleware.ts is
// refreshing the session on every request -- this mirrors @supabase/ssr's
// own documented pattern.
export async function createClient() {
  const cookieStore = await cookies();

  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!,
    {
      cookies: {
        getAll() {
          return cookieStore.getAll();
        },
        setAll(cookiesToSet: CookieToSet[]) {
          try {
            cookiesToSet.forEach(({ name, value, options }) =>
              cookieStore.set(name, value, options),
            );
          } catch {
            // Called from a Server Component -- ignored, see comment above.
          }
        },
      },
    },
  );
}
