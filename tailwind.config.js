/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./*.html",
    "./assets/js/**/*.js",
    "./assets/components/**/*.html"
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          dark: "#0f172a",     // Slate 900
          primary: "#2563eb",  // Blue 600
          accent: "#1d4ed8",   // Blue 700
          light: "#f8fafc",    // Slate 50
          surface: "#0b1120"   // Slate 950-ish
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
