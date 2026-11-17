/** @type {import('tailwindcss').Config} */
const token = (name) => `rgb(var(--${name}) / <alpha-value>)`;

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        display: ["var(--font-display)"],
      },
      colors: {
        canvas: token("canvas"),
        surface: { DEFAULT: token("surface"), 2: token("surface-2") },
        line: token("line"),
        ink: { DEFAULT: token("ink"), soft: token("ink-soft"), muted: token("ink-muted") },
        accent: {
          DEFAULT: token("accent"),
          hover: token("accent-hover"),
          soft: token("accent-soft"),
          2: token("accent-2"),
        },
        "on-accent": token("on-accent"),
        danger: { DEFAULT: token("danger"), soft: token("danger-soft") },
        success: token("success"),
      },
      borderRadius: { theme: "var(--radius)" },
      boxShadow: {
        card: "0 1px 2px rgb(0 0 0 / 0.04), 0 8px 24px -12px rgb(0 0 0 / 0.12)",
        lift: "0 2px 4px rgb(0 0 0 / 0.04), 0 24px 48px -20px rgb(0 0 0 / 0.25)",
        glow: "var(--glow)",
      },
      animation: {
        "fade-up": "fade-up 0.7s cubic-bezier(.2,.7,.2,1) both",
        float: "float 6s ease-in-out infinite",
        marquee: "marquee 40s linear infinite",
        blink: "blink 1s step-end infinite",
      },
    },
  },
  plugins: [],
};
