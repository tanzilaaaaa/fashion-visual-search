/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        display: ["Fraunces", "ui-serif", "Georgia", "serif"],
      },
      colors: {
        ink: { DEFAULT: "#1c1917", soft: "#44403c", muted: "#78716c" },
        canvas: "#faf9f7",
        accent: { DEFAULT: "#9f1239", soft: "#ffe4e6", hover: "#881337" },
      },
      boxShadow: { card: "0 1px 2px rgba(28,25,23,.06), 0 4px 16px rgba(28,25,23,.06)" },
    },
  },
  plugins: [],
};
