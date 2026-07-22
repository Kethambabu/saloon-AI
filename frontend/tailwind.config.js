/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      keyframes: {
        'fade-in': {
          '0%': { opacity: '0', transform: 'translateY(4px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
      animation: {
        // Used across all three dashboards ("animate-fade-in") to soften
        // the swap from loading state to content — was referenced
        // everywhere but never defined, so it was previously a no-op.
        'fade-in': 'fade-in 0.25s ease-out',
      },
    },
  },
  plugins: [],
}
