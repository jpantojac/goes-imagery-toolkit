/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        goes: {
          bg: "#0B0F19",
          panel: "#111827",
          border: "#1F2937",
          accent: "#0284C7",
          accentHover: "#0369A1"
        }
      }
    },
  },
  plugins: [],
}
