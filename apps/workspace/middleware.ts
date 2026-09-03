import { type NextRequest } from "next/server";
import { updateSession } from "@/lib/supabase/middleware";

export async function middleware(request: NextRequest) {
  return await updateSession(request);
}

export const config = {
  // .png/.jpg/.jpeg alongside the existing .svg exclusion: every image
  // under public/ here is a static, public branding/social asset (model
  // icons, the orb graphic, og-image.png) -- nothing user-uploaded or
  // private sits behind these extensions in this app. Without this,
  // og-image.png 307'd to /login for anonymous requests, which is
  // exactly how social platforms' link-preview crawlers fetch it --
  // confirmed live via curl, the thumbnail silently never rendered.
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpe?g)$).*)"],
};
