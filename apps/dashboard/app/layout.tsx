import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ComputeLayer",
  description: "Reuse, cost and savings for every agent run.",
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
