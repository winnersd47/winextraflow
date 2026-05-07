import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#f0fdfa",
          100: "#ccfbf1",
          500: "#14b8a6",
          600: "#0d9488",
          700: "#0f766e",
        },
        surface: {
          DEFAULT: "var(--color-surface)",
          card: "var(--color-surface-card)",
          hover: "var(--color-surface-hover)",
        },
      },
      textColor: {
        "text-primary": "var(--color-text-primary)",
        "text-secondary": "var(--color-text-secondary)",
        "text-muted": "var(--color-text-muted)",
      },
      borderColor: {
        border: "var(--color-border)",
      },
    },
  },
  plugins: [],
};
export default config;
