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

export const metadata: Metadata = {
  title: "Accurate",
  description: "Use the best AI for every part of your work — without starting over.",
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
