import type { Config } from "tailwindcss";

// Colours are names for the CSS variables in app/globals.css, so a class like `text-muted`
// follows the theme and nothing in a component hardcodes a hex value.
const config: Config = {
  darkMode: "class",
  content: ["./components/**/*.{ts,tsx}", "./app/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "var(--bg)",
        surface: "var(--surface)",
        "surface-2": "var(--surface-2)",
        line: "var(--border)",
        "line-strong": "var(--border-strong)",
        fg: "var(--fg)",
        muted: "var(--muted)",
        accent: "var(--accent-fg)",
        "on-accent": "var(--on-accent)",
        strong: "var(--strong-fg)",
        competitive: "var(--competitive-fg)",
        stretch: "var(--stretch-fg)",
        poor: "var(--poor-fg)",
      },
      borderRadius: { card: "var(--radius)" },
      fontFamily: {
        display: ["var(--font-sora)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      backgroundImage: { accent: "var(--accent-gradient)" },
    },
  },
  plugins: [],
};
export default config;
