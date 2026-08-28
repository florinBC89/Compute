"use server";

import { createClient } from "@/lib/supabase/server";

export type LoginState = {
  status: "idle" | "sent" | "error";
  message?: string;
};

// Magic-link only, deliberately: the spec's whole premise is that a
// researcher/writer "should not need to understand APIs ... or caching" --
// a password to remember and reset is exactly the kind of incidental
// complexity that promise is against.
export async function signInWithMagicLink(
  _prevState: LoginState,
  formData: FormData,
): Promise<LoginState> {
  const email = formData.get("email");
  if (typeof email !== "string" || !email.includes("@")) {
    return { status: "error", message: "Enter a valid email address." };
  }

  const supabase = await createClient();
  const { error } = await supabase.auth.signInWithOtp({
    email,
    options: {
      emailRedirectTo: `${process.env.NEXT_PUBLIC_SITE_URL ?? ""}/auth/callback`,
    },
  });

  if (error) {
    return { status: "error", message: error.message };
  }
  return { status: "sent", message: `Check ${email} for a sign-in link.` };
}
