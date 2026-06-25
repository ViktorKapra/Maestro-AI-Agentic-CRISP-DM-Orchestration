/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Quicksand"', "ui-rounded", "system-ui", "sans-serif"],
      },
      colors: {
        // 🌸 Lavender-rose light theme — soft, girly, easy on the eyes.
        surface: {
          DEFAULT: "#fdf4ff", // lightest lavender (inputs, code blocks)
          raised: "#ffffff", // cards / header (with a rosy border)
          border: "#f1cde9", // rose-lavender hairline
        },
        accent: {
          DEFAULT: "#d6409f", // rose-fuchsia (buttons, active bits)
          muted: "#9333ea", // deep lavender (readable text links)
        },
        status: {
          running: "#d946ef", // fuchsia sparkle = working
          halted: "#f43f5e", // rose-red = uh oh
          complete: "#a78bfa", // soft lavender = done
        },
        // Slate is used everywhere for text; remap it so the dark-theme
        // utility classes read as dark-on-light plum tones instead.
        slate: {
          100: "#3b1f47", // main body text
          200: "#4a2a57",
          300: "#5d3a6b", // code / transcript text
          400: "#8b6f9e", // muted labels
          500: "#a98fb8", // very muted
          600: "#c9a9d6", // soft borders (flow nodes)
          700: "#b794c9",
          800: "#5d3a6b",
          900: "#3b1f47",
        },
      },
    },
  },
  plugins: [],
};
