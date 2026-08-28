import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Accurate",
  description: "Use the best AI for every part of your work — without starting over.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen font-sans antialiased">
        <div className="mx-auto max-w-[720px] px-6 py-8 sm:px-8">{children}</div>
      </body>
    </html>
  );
}
