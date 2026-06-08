/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        // Refined dark palette: near-black neutral surfaces + a single confident green accent.
        gp: {
          green: "#16a34a", // primary action
          glow: "#4ade80", // accent / highlight
          ink: "#0a0c0d", // page background
          panel: "#101315", // inputs / subtle fills
          card: "#14181a", // raised surfaces
          line: "#232a2e", // hairline borders
          muted: "#8a979d", // secondary text
        },
      },
      fontFamily: {
        sans: ["Inter", "Segoe UI", "system-ui", "sans-serif"],
      },
      boxShadow: {
        // Softer, more modern elevation than a hard glow ring.
        soft: "0 1px 2px rgba(0,0,0,0.3), 0 12px 32px -12px rgba(0,0,0,0.55)",
        glow: "0 0 0 1px rgba(74,222,128,0.18), 0 16px 50px -16px rgba(22,163,74,0.5)",
      },
      keyframes: {
        fadeUp: {
          "0%": { opacity: "0", transform: "translateY(10px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        fadeIn: {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        scaleIn: {
          "0%": { opacity: "0", transform: "scale(0.97)" },
          "100%": { opacity: "1", transform: "scale(1)" },
        },
        shimmer: {
          "100%": { transform: "translateX(100%)" },
        },
      },
      animation: {
        // Expressive ease-out (cubic-bezier 0.16,1,0.3,1) for a smooth, settled feel.
        "fade-up": "fadeUp 0.5s cubic-bezier(0.16,1,0.3,1) both",
        "fade-in": "fadeIn 0.4s ease-out both",
        "scale-in": "scaleIn 0.4s cubic-bezier(0.16,1,0.3,1) both",
        shimmer: "shimmer 1.6s infinite",
      },
    },
  },
  plugins: [],
};
