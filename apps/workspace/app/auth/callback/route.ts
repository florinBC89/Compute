import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";

// Where a magic-link email lands: exchanges the one-time `code` for a real
// session (setting cookies via the server client), then sends the user on.
export async function GET(request: Request) {
  const { searchParams, origin } = new URL(request.url);
  const code = searchParams.get("code");

  if (code) {
    const supabase = await createClient();
    const { error } = await supabase.auth.exchangeCodeForSession(code);
    if (!error) {
      return NextResponse.redirect(`${origin}/`);
    }
  }

  return NextResponse.redirect(`${origin}/login?error=auth_callback_failed`);
}
