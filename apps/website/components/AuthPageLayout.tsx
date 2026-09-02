import Link from "next/link";
import GradientBackground from "./GradientBackground";
import GreetingBubble from "./GreetingBubble";

// Shared chrome for /register, /login, and /reset-password (Figma
// "Website v2" node 101-1671: each is its own full page there, not a
// modal). The logo sits centered above each page's own heading (inside
// the centered column below), not left-aligned in a full-width header --
// matches Figma exactly: the logo's own x-position there centers it above
// the 360px form column, not the page.
//
// `decorated` (on by default) additionally splits the page into two
// columns at lg: the form on the left, and a rounded panel on the right.
// The panel's own background is the same warm chat-warm (#FFF5F1) tone
// used everywhere else in the site's chat surfaces; the animated
// NeatGradient sits anchored to the panel's bottom edge, not filling it
// edge to edge, so that warm base color shows through above it -- the
// gradient's own canvas has a transparent background (backgroundAlpha: 0
// in GradientBackground's config) so there's no hard seam where the two
// meet. The rotating greeting bubble + orb sit centered on top of both.
// Figma's own mobile frames for these pages don't include this panel at
// all (no gradient, no bubble, no orb -- just the logo and the form), so
// below lg this collapses to a single centered column, not a stacked
// version of the desktop decoration.
//
// /reset-password passes decorated={false}: that flow is a single focused
// task (set a password), not a moment for the marketing bubble.
export default function AuthPageLayout({
  children,
  decorated = true,
  showLogo = true,
}: {
  children: React.ReactNode;
  decorated?: boolean;
  //: Off during the loading state (AuthPage.tsx) -- the logo above a
  //: brief video+"Loading…" moment just read as clutter, not a page
  //: identity a user needs while it's already mid-navigation away from
  //: this page. The centered group re-centers naturally around whatever
  //: shorter content remains, no offset needed.
  showLogo?: boolean;
}) {
  return (
    <main className="relative flex min-h-screen items-center overflow-hidden bg-page">
      <div
        className={`relative z-10 mx-auto grid w-full max-w-[1400px] items-stretch gap-10 px-6 py-10 sm:px-10 lg:gap-16 lg:py-14 ${
          decorated ? "lg:grid-cols-2" : ""
        }`}
      >
        <div className="flex flex-col items-center justify-center text-center">
          {showLogo ? (
            <Link href="/" className="mb-10 inline-block">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src="/logo.svg" alt="Accurate" className="h-[21px] w-auto" />
            </Link>
          ) : null}
          {children}
        </div>

        {decorated ? (
          <div className="relative hidden overflow-hidden rounded-[32px] bg-white lg:flex lg:min-h-[760px] lg:items-center lg:justify-center">
            {/* The canvas's own box needs a top fade, not just bottom
                anchoring -- backgroundAlpha:0 keeps the shader's *background*
                transparent, but NeatGradient's ambient glow/vignette still
                extends past the sphere shape itself, filling its whole
                assigned box faintly. Without this mask that box's own top
                edge read as a visible rectangle sitting on the panel's
                solid fill above it, not a soft blend into it. */}
            <GradientBackground
              className="pointer-events-none absolute inset-x-0 bottom-0 h-[75%] w-full translate-y-[200px]"
              style={{
                maskImage: "linear-gradient(to bottom, transparent 0%, black 40%)",
                WebkitMaskImage: "linear-gradient(to bottom, transparent 0%, black 40%)",
              }}
            />
            {/* Bubble + video move together as one unit now (was just the
                bubble before) -- -150px up from center, same direction as
                before just deeper now that there's no separate offset
                between the two. */}
            <div className="relative z-10 flex -translate-y-[150px] flex-col items-center gap-8 px-6">
              <GreetingBubble />
              {/* Same looping video as HeroChat's orb slot (and the auth
                  pages' own social-loading state) instead of the static
                  AiOrb -- same 112.5px circle. */}
              {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
              <video
                src="/videos/social-loading.mp4"
                autoPlay
                loop
                muted
                playsInline
                className="h-[112.5px] w-[112.5px] shrink-0 rounded-full object-cover"
              />
            </div>
          </div>
        ) : null}
      </div>
    </main>
  );
}
