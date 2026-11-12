// tailwind.config.cjs
module.exports = {
  content: [
    './index.html',
    './src/**/*.{js,jsx,ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        navy: {
          DEFAULT: '#0f1729',
          50: '#e8eaf0',
          100: '#c5c9d6',
          200: '#9ea5ba',
          300: '#77809e',
          400: '#596589',
          500: '#3b4a74',
          600: '#33406a',
          700: '#28335b',
          800: '#1e274d',
          900: '#0f1729',
          950: '#080d18',
        },
        accent: {
          DEFAULT: '#3b82f6',
          light: '#60a5fa',
          dark: '#2563eb',
        },
        surface: {
          DEFAULT: '#f8fafc',
          50: '#ffffff',
          100: '#f8fafc',
          200: '#f1f5f9',
          300: '#e2e8f0',
          400: '#cbd5e1',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
    },
  },
  plugins: [],
};
