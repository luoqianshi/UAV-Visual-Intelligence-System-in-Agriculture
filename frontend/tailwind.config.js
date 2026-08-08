/** @type {import('tailwindcss').Config} */
// V0.4 色板：brand 绿色系 / ink 文本 / surface 表面
export default {
  content: ['./index.html', './src/**/*.{vue,js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#E8F5E9',
          100: '#C8E6C9',
          300: '#81C784',
          500: '#4CAF50',
          700: '#2F7D32',
          900: '#1B5E20',
        },
        ink: {
          primary: '#37352F',
          secondary: '#787774',
          tertiary: '#9B9A97',
        },
        surface: {
          bg: '#FAFAF9',
          border: '#E9E9E7',
          hover: '#F1F1EF',
        },
      },
      borderRadius: {
        card: '8px',
        btn: '6px',
      },
    },
  },
  plugins: [],
}
