import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#f0fdf4",
          100: "#dcfce7",
          500: "#22c55e",
          600: "#16a34a",
          700: "#15803d",
        },
        surface: {
          DEFAULT: "#0f1117",
          card: "#1a1d27",
          hover: "#242736",
        },
      },
    },
  },
  plugins: [],
};
export default config;
