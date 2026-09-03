import type { Metadata } from "next";
import { Kalnia } from "next/font/google";
import "./globals.css";

// The chat heading's display face (V0.3 Figma design, "Registered user"
// flow) -- only the chat page's heading uses font-display; everything
// else stays on the existing sans stack.
const kalnia = Kalnia({
  subsets: ["latin"],
  weight: ["500"],
  variable: "--font-display",
});

const TITLE = "Accurate";
const DESCRIPTION = "Use the best AI for every part of your work — without starting over.";
const SITE_URL = "https://app.accurate-ai.app";

// Without an explicit openGraph/twitter block, a shared link showed a
// title and description but no preview thumbnail (confirmed live -- a
// WhatsApp share of this URL rendered as a bare text card). Reuses
// apps/website's own og-image.png -- same brand system, already a real,
// committed asset -- rather than a second near-duplicate image.
export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: TITLE,
  description: DESCRIPTION,
  openGraph: {
    title: TITLE,
    description: DESCRIPTION,
    url: SITE_URL,
    siteName: "Accurate",
    type: "website",
    images: [{ url: "/og-image.png", width: 1200, height: 630, alt: "Accurate" }],
  },
  twitter: {
    card: "summary_large_image",
    title: TITLE,
    description: DESCRIPTION,
    images: ["/og-image.png"],
  },
};

// No shared max-width/padding wrapper here (V0.3): the chat page owns a
// full-height sidebar + main layout, and /login keeps its own narrow
// centered wrapper -- a global constraint here would fight both.
//
// data-theme="light" forces the light palette regardless of the system's
// prefers-color-scheme: the V0.3 chat design (icons, --chat-* tokens) was
// only ever built and verified against light mode -- see app/globals.css's
// `:root:not([data-theme="light"])` dark-mode guard, the same one
// apps/dashboard already uses.
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" data-theme="light" className={kalnia.variable}>
      {/* h-dvh, not h-screen: on iOS Safari, 100vh stays pinned to the
          viewport's height from before the on-screen keyboard opened, so a
          flex-centered layout inside it "centers" against that stale,
          too-tall value -- the content visibly floats above a gap where
          the keyboard now covers the rest of that phantom space, instead
          of recentering in what's actually still visible above the
          keyboard. The dynamic viewport unit updates live as the keyboard
          opens/closes, which is what actually fixes that. */}
      <body className="h-dvh overflow-hidden font-sans antialiased">{children}</body>
    </html>
  );
}
