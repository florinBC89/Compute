import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";

// Kalnia isn't in this Next.js version's bundled next/font/google metadata
// yet, so it's loaded as a plain stylesheet instead -- functionally
// identical, just without next/font's self-hosting/preload optimization.
const KALNIA_HREF =
  "https://fonts.googleapis.com/css2?family=Kalnia:wght@400;500;600;700&display=swap";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
});

const mono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
});

export const metadata: Metadata = {
  title: "Accurate",
  description: "Your AI doesn't need to recompute everything.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="stylesheet" href={KALNIA_HREF} />
      </head>
      <body className={`${inter.variable} ${mono.variable} font-sans antialiased`}>
        {children}
      </body>
    </html>
  );
}
