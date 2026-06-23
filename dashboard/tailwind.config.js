/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        surface: {
          DEFAULT: "#0f1419",
          raised: "#1a2332",
          border: "#2d3a4f",
        },
        accent: {
          DEFAULT: "#3b82f6",
          muted: "#60a5fa",
        },
        status: {
          running: "#22c55e",
          halted: "#ef4444",
          complete: "#94a3b8",
        },
      },
    },
  },
  plugins: [],
};
