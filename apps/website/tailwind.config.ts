import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        page: "var(--page)",
        surface: "var(--surface)",
        ink: "var(--ink)",
        "ink-secondary": "var(--ink-secondary)",
        "ink-muted": "var(--ink-muted)",
        border: "var(--border)",
        accent: "var(--accent)",
        "accent-soft": "var(--accent-soft)",
        good: "var(--good)",
        dark: "var(--dark)",
      },
      fontFamily: {
        serif: ["var(--font-fraunces)", "Georgia", "serif"],
        sans: ["var(--font-inter)", "-apple-system", "Helvetica Neue", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      borderRadius: {
        card: "24px",
        pill: "999px",
      },
    },
  },
  plugins: [],
};

export default config;
