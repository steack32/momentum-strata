/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./**/*.html",               // ← scanne TOUTES les pages HTML
    "./assets/js/**/*.js",       // ← scanne ton JS
    "./assets/components/**/*.html", // ← navbar, footer, etc.
    "./assets/css/**/*.css"      // ← indispensable pour les @apply
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          dark: "#0f172a",
          primary: "#2563eb",
          accent: "#1d4ed8",
          light: "#f8fafc",
          surface: "#0b1120"
        }
      },
      boxShadow: {
        premium: "0 18px 45px rgba(15,23,42,0.9)"
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "sans-serif"]
      }
    }
  },
  plugins: []
};
