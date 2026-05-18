import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "sans-serif"],
      },
      colors: {
        // Enterprise neutral palette
        surface: {
          DEFAULT: "#0f0f0f",
          "50": "#fafafa",
          "100": "#f5f5f5",
          "800": "#1a1a1a",
          "900": "#0f0f0f",
        },
        border: {
          DEFAULT: "#2a2a2a",
          subtle: "#1f1f1f",
        },
      },
    },
  },
  plugins: [],
};

export default config;
