/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      keyframes: {
        blink: { '50%': { opacity: '0' } },
        fadeSlideIn: {
          '0%': { opacity: '0', transform: 'translateY(-6px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        scaleIn: {
          '0%': { opacity: '0', transform: 'scale(0.97)' },
          '100%': { opacity: '1', transform: 'scale(1)' },
        },
        riseIn: {
          '0%': { opacity: '0', transform: 'translateY(14px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        drawerIn: {
          '0%': { transform: 'translateX(40px)', opacity: '0.4' },
          '100%': { transform: 'translateX(0)', opacity: '1' },
        },
      },
      animation: {
        blink: 'blink 1s step-start infinite',
        'fade-in': 'fadeSlideIn 0.18s ease-out',
        'scale-in': 'scaleIn 0.16s ease-out',
        'rise-in': 'riseIn 0.25s ease-out',
        'drawer-in': 'drawerIn 0.2s ease-out',
      },
      colors: {
        bg: { DEFAULT: '#141312', sunken: '#0f0e0d' },
        header: '#0f0e0d',
        card: '#1b1a18',
        raised: '#232120',
        overlay: '#292623',
        border: { DEFAULT: '#2a2723', strong: '#38342e' },
        text: { DEFAULT: '#ece7df', secondary: '#9c958a', muted: '#6f695f', faint: '#4a463f' },
        accent: { DEFAULT: '#e0a458', light: '#eab26c', deep: '#a97833' },
        ok: '#82a877',
        danger: '#c96f5e',
        priority: {
          high: '#b0684a',
          'high-text': '#d9906e',
          medium: '#8f7a4e',
          'medium-text': '#c2a86e',
          low: '#211f1c',
          'low-text': '#6f695f',
        },
      },
      fontFamily: {
        sans: ['-apple-system', 'BlinkMacSystemFont', 'system-ui', 'sans-serif'],
        mono: ['ui-monospace', 'SF Mono', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      borderRadius: {
        DEFAULT: '10px',
        xl: '14px',
        '2xl': '20px',
      },
    },
  },
  plugins: [],
}
