/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Quicksand"', "ui-rounded", "system-ui", "sans-serif"],
      },
      colors: {
        // 🎨 All theme tokens are CSS variables holding *RGB channels*
        // (e.g. "255 255 255"). The `<alpha-value>` placeholder lets Tailwind
        // opacity modifiers (bg-surface/80, accent/40, …) keep working.
        // The actual values live in index.css and switch with [data-theme].
        surface: {
          DEFAULT: "rgb(var(--surface) / <alpha-value>)",
          raised: "rgb(var(--surface-raised) / <alpha-value>)",
          border: "rgb(var(--surface-border) / <alpha-value>)",
        },
        accent: {
          DEFAULT: "rgb(var(--accent) / <alpha-value>)",
          muted: "rgb(var(--accent-muted) / <alpha-value>)",
        },
        status: {
          running: "rgb(var(--status-running) / <alpha-value>)",
          halted: "rgb(var(--status-halted) / <alpha-value>)",
          complete: "rgb(var(--status-complete) / <alpha-value>)",
        },
        // Slate is used everywhere for text; remap each shade to a themed
        // variable so text flips correctly between the light-pink theme
        // (dark plum on light) and the business theme (light on dark).
        slate: {
          100: "rgb(var(--slate-100) / <alpha-value>)",
          200: "rgb(var(--slate-200) / <alpha-value>)",
          300: "rgb(var(--slate-300) / <alpha-value>)",
          400: "rgb(var(--slate-400) / <alpha-value>)",
          500: "rgb(var(--slate-500) / <alpha-value>)",
          600: "rgb(var(--slate-600) / <alpha-value>)",
          700: "rgb(var(--slate-700) / <alpha-value>)",
          800: "rgb(var(--slate-800) / <alpha-value>)",
          900: "rgb(var(--slate-900) / <alpha-value>)",
        },
      },
    },
  },
  plugins: [],
};
