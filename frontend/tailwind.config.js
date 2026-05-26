/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      keyframes: {
        blink: { '50%': { opacity: '0' } },
      },
      animation: {
        blink: 'blink 1s step-start infinite',
      },
      colors: {
        bg: '#181818',
        header: '#141414',
        card: '#1c1c1c',
        border: '#252525',
        text: { DEFAULT: '#f0f0f0', secondary: '#666', muted: '#383838' },
        accent: { DEFAULT: '#5060a0', light: '#8090c8' },
        priority: {
          high: '#6a3030',
          'high-text': '#b07070',
          medium: '#4a3a1e',
          'medium-text': '#a08850',
          low: '#222',
          'low-text': '#555',
        },
      },
      fontFamily: {
        sans: ['-apple-system', 'BlinkMacSystemFont', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
