import type { Config } from "tailwindcss";

// Same token vocabulary as apps/dashboard's tailwind.config.ts, so the two
// apps read as related without sharing a component package.
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        page: "var(--page)",
        surface: "var(--surface)",
        "surface-raised": "var(--surface-raised)",
        ink: "var(--ink)",
        "ink-secondary": "var(--ink-secondary)",
        "ink-muted": "var(--ink-muted)",
        border: "var(--border)",
        accent: "var(--accent)",
        "accent-soft": "var(--accent-soft)",
        "accent-track": "var(--accent-track)",
        good: "var(--good)",
        warning: "var(--warning)",
        serious: "var(--serious)",
        critical: "var(--critical)",
        info: "var(--info)",
        violet: "var(--violet)",
        // Chat surface (V0.3) -- see app/globals.css for why these are
        // separate from page/surface/ink above.
        "chat-warm": "var(--chat-warm)",
        "chat-ink": "var(--chat-ink)",
        "chat-ink-soft": "var(--chat-ink-soft)",
        "chat-ink-strong": "var(--chat-ink-strong)",
        "chat-label": "var(--chat-label)",
        "chat-border-warm": "var(--chat-border-warm)",
        "chat-accent-strong": "var(--chat-accent-strong)",
      },
      borderRadius: {
        card: "28px",
        pill: "999px",
      },
      boxShadow: {
        card: "0 1px 2px rgba(11,11,11,0.04), 0 12px 32px -12px rgba(11,11,11,0.10)",
      },
      fontFamily: {
        sans: [
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "Inter",
          "Helvetica Neue",
          "Arial",
          "sans-serif",
        ],
        // Chat surface heading font (V0.3 Figma design) -- loaded via
        // next/font/google in app/layout.tsx as the --font-display CSS var.
        display: ["var(--font-display)", "Georgia", "serif"],
      },
    },
  },
  plugins: [],
};

export default config;
