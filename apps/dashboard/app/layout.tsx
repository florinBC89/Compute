import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Accurate",
  description: "Know exactly what your AI costs — and what Accurate prevented.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen font-sans antialiased">
        <div className="mx-auto max-w-[1240px] px-6 py-6 sm:px-10 sm:py-8">{children}</div>
      </body>
    </html>
  );
}
