/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        // Xbox-ish palette
        gp: {
          green: "#107C10",
          glow: "#39d353",
          ink: "#0b0f0c",
          panel: "#14181a",
          card: "#1b2124",
          line: "#2a3236",
          muted: "#8b9aa0",
        },
      },
      fontFamily: {
        sans: ["Inter", "Segoe UI", "system-ui", "sans-serif"],
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(57,211,83,0.25), 0 8px 40px -8px rgba(16,124,16,0.45)",
      },
    },
  },
  plugins: [],
};
