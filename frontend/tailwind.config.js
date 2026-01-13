/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        // Custom colors for crypto vibes
        'sol-purple': '#9945FF',
        'sol-green': '#14F195',
        'sol-blue': '#00FFA3',
      },
    },
  },
  plugins: [],
}
