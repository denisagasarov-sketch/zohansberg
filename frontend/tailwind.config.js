/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        surface: {
          0: '#0a0a0b',
          1: '#111113',
          2: '#18181b',
          3: '#1f1f23',
          4: '#27272c',
          5: '#2e2e35',
        },
        border: {
          dim: '#2a2a31',
          default: '#3a3a44',
          bright: '#52525e',
        },
        text: {
          muted: '#4a4a55',
          dim: '#6b6b7a',
          secondary: '#8b8b9a',
          primary: '#c8c8d4',
          bright: '#e8e8f0',
        },
        accent: {
          green: '#22c55e',
          'green-dim': '#16a34a',
          blue: '#3b82f6',
          'blue-dim': '#2563eb',
          amber: '#f59e0b',
          red: '#ef4444',
          purple: '#a855f7',
        },
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'Consolas', 'monospace'],
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
