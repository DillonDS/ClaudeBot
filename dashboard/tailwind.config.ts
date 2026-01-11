import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './src/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        coral: {
          DEFAULT: '#d97757',
          50: '#fdf6f4',
          100: '#fbeae4',
          200: '#f7d4c9',
          300: '#f0b5a0',
          400: '#e58e6e',
          500: '#d97757',
          600: '#c45a3a',
          700: '#a4472d',
          800: '#873c29',
          900: '#703527',
        },
        dark: {
          DEFAULT: '#262624',
          50: '#f6f6f5',
          100: '#e7e7e6',
          200: '#d1d1d0',
          300: '#b1b1af',
          400: '#8a8a87',
          500: '#6f6f6c',
          600: '#5e5e5b',
          700: '#50504d',
          800: '#454543',
          900: '#262624',
          950: '#1a1a19',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Consolas', 'monospace'],
      },
    },
  },
  plugins: [
    require('@tailwindcss/forms'),
  ],
}

export default config
