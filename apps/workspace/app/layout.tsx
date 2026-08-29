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
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={kalnia.variable}>
      <body className="min-h-screen font-sans antialiased">{children}</body>
    </html>
  );
}
