/** @type {import('tailwindcss').Config} */
module.exports = {
  mode: "jit", // Commentez cette ligne temporairement
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        "blue-night": {
          DEFAULT: "#0f172a",
          lighter: "#1e293b",
          light: "#334155",
        },
      },
      backgroundImage: {
        "auth-gradient": "linear-gradient(45deg, #1e3c72, #2a5298, #7303c0)",
      },
    },
  },
  plugins: [],
};
